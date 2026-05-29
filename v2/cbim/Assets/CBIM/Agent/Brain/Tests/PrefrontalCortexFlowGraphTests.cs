#if UNITY_INCLUDE_TESTS
using System;
using System.Collections.Generic;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Agents.AI;
using NUnit.Framework;
using CBIM.AgentSystem;
using CBIM.AgentSystem.Brain;
using CBIM.AgentSystem.Kernel.Neuron;
using CBIM.AgentSystem.Kernel.Synapse;
using CBIM.AgentSystem.Kernel.Synapse.Compiler;
using CBIM.Memory;

namespace CBIM.AgentSystem.Brain.Tests
{
    /// <summary>
    /// T14 PrefrontalCortex FlowGraph 路径端到端测试——覆盖：
    ///   - 退化路径：Neuron 不动 ActiveBuilder → builder.Compiled == null → 返 Neuron outcome 原文
    ///   - FlowGraph 路径：Neuron 模拟 LLM 调 __circuit_* 编完图并 commit → JSON 落盘到
    ///     <c>{projectRoot}/.cbim/agentsystem/sessions/{instanceId}/circuits/{circuitId}.json</c> →
    ///     CBIMOrchestrator 跑图 → 返 ReturnNode 模板渲染结果
    ///   - InvokeAsync 出口处 ActiveBuilder 必被清回 null（即使中途抛错）
    ///
    /// 由于 PrefrontalCortex.ActiveBuilder 是 internal，本测试通过 InternalsVisibleTo 直读字段。
    /// </summary>
    [TestFixture]
    public sealed class PrefrontalCortexFlowGraphTests
    {
        private string _tempRoot = string.Empty;

        [SetUp]
        public void SetUp()
        {
            _tempRoot = Path.Combine(Path.GetTempPath(),
                "cbim-pfc-flowgraph-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(_tempRoot);
        }

        [TearDown]
        public void TearDown()
        {
            if (Directory.Exists(_tempRoot))
            {
                try { Directory.Delete(_tempRoot, recursive: true); }
                catch (IOException) { /* 测试机偶发占用，忽略 */ }
            }
        }

        // ===== (1) 退化路径：Neuron 不编图 → 返 Neuron outcome 原文 =====

        [Test]
        public async Task InvokeAsync_returns_Neuron_outcome_when_builder_was_not_committed()
        {
            var instanceId = "test-instance-deg-" + Guid.NewGuid().ToString("N");
            var memory = new InMemoryFakeMemoryService();

            // Neuron 拿到 invocation 后什么都不做——不动 ActiveBuilder——直接返自然语言。
            var neuron = new FlowGraphFakeNeuron(
                neuronId: "prefrontal-cortex",
                onInvoke: _ => new BrainOutcome(
                    Summary: "llm-says-degraded-path",
                    StructuredOutput: null,
                    SideEffects: Array.Empty<SideEffect>(),
                    IsError: false,
                    ErrorMessage: null));

            var pfcDesc = BuildPrefrontalDescriptor();
            var pfc = new PrefrontalCortex(
                descriptor: pfcDesc,
                memory: memory,
                neuron: neuron,
                callback: null,
                callableBrains: Array.Empty<BrainBase>(),
                brainRegistry: new InMemoryBrainRegistry(),
                instanceId: instanceId,
                projectRoot: _tempRoot);

            var invocation = new BrainInvocation(
                CorrelationId: "corr-deg",
                Intent: "请告诉我现在几点",
                StructuredInput: null,
                Context: new Dictionary<string, object>());

            var outcome = await pfc.InvokeAsync(invocation, CancellationToken.None);

            Assert.That(outcome.IsError, Is.False);
            Assert.That(outcome.Summary, Is.EqualTo("llm-says-degraded-path"),
                "退化路径：builder.Compiled == null → 直接返 Neuron 结果。");
            Assert.That(pfc.ActiveBuilder, Is.Null,
                "InvokeAsync 出口必清回 ActiveBuilder=null。");

            // 退化路径不落 JSON 文件——目录可能根本未创建。
            string circuitsDir = Path.Combine(_tempRoot, ".cbim", "agentsystem", "sessions", instanceId, "circuits");
            Assert.That(Directory.Exists(circuitsDir), Is.False,
                "退化路径不应触发 JSON 落盘。");
        }

        // ===== (2) FlowGraph 路径：编图 + commit → JSON 落盘 + Orchestrator 跑出结果 =====

        [Test]
        public async Task InvokeAsync_runs_FlowGraph_path_persists_JSON_and_returns_Orchestrator_outcome()
        {
            var instanceId = "test-instance-fg-" + Guid.NewGuid().ToString("N");
            var memory = new InMemoryFakeMemoryService();

            // 准备一个子脑区——FlowGraph 中 CallBrainNode 的 target。
            var sub = BuildParietalWithFixedSummary("parietal-lobe", "sub-says-hello");

            // Neuron 拿到 invocation 后通过捕获的 callback 操作 ActiveBuilder：
            //   1) AddCallBrain → 2) AddReturn → 3) AddEdge → 4) Commit
            // 然后返一段无关文本（FlowGraph 路径会忽略此 outcome，最终结果来自 Orchestrator 跑图）。
            PrefrontalCortex? pfcRef = null;
            var neuron = new FlowGraphFakeNeuron(
                neuronId: "prefrontal-cortex",
                onInvoke: _ =>
                {
                    var builder = pfcRef!.ActiveBuilder
                        ?? throw new InvalidOperationException("ActiveBuilder 应在 InvokeAsync 窗口内非 null。");
                    string nCall = builder.AddCallBrain("call", "parietal-lobe", "do sub task", null);
                    string nRet = builder.AddReturn("ret", "wrapped: {previous.summary}");
                    builder.AddEdge(nCall, nRet, null);
                    builder.Commit();
                    return new BrainOutcome(
                        Summary: "llm-says-ignored-because-flowgraph-takes-over",
                        StructuredOutput: null,
                        SideEffects: Array.Empty<SideEffect>(),
                        IsError: false,
                        ErrorMessage: null);
                });

            var pfcDesc = BuildPrefrontalDescriptor();
            var pfc = new PrefrontalCortex(
                descriptor: pfcDesc,
                memory: memory,
                neuron: neuron,
                callback: null,
                callableBrains: new BrainBase[] { sub },
                brainRegistry: new InMemoryBrainRegistry(),
                instanceId: instanceId,
                projectRoot: _tempRoot);
            pfcRef = pfc;   // 闭包此刻拿到非 null 引用

            var invocation = new BrainInvocation(
                CorrelationId: "corr-fg",
                Intent: "请编一张图调子脑区",
                StructuredInput: null,
                Context: new Dictionary<string, object>());

            var outcome = await pfc.InvokeAsync(invocation, CancellationToken.None);

            Assert.That(outcome.IsError, Is.False, "FlowGraph 路径正常执行不应 IsError。");
            Assert.That(outcome.Summary, Is.EqualTo("wrapped: sub-says-hello"),
                "FlowGraph 路径 Summary 应等于 ReturnNode 模板渲染结果——上游 sub 返 'sub-says-hello' → 模板 'wrapped: {previous.summary}' → 'wrapped: sub-says-hello'。");

            Assert.That(pfc.ActiveBuilder, Is.Null,
                "InvokeAsync 出口必清回 ActiveBuilder=null。");

            // JSON 落盘——验证完整路径 D3 决策。
            string circuitsDir = Path.Combine(_tempRoot, ".cbim", "agentsystem", "sessions", instanceId, "circuits");
            Assert.That(Directory.Exists(circuitsDir), Is.True,
                "FlowGraph 路径必落盘 JSON 目录。");
            var files = Directory.GetFiles(circuitsDir, "*.json");
            Assert.That(files.Length, Is.EqualTo(1),
                "应恰好落 1 份 JSON——本轮一个 InvokeAsync。");
            string content = File.ReadAllText(files[0]);
            StringAssert.Contains("\"circuitId\"", content);
            StringAssert.Contains("\"callBrain\"", content);
            StringAssert.Contains("\"return\"", content);
            StringAssert.Contains("parietal-lobe", content);
        }

        // ===== (3) ActiveBuilder 异常路径清零 =====

        [Test]
        public async Task InvokeAsync_clears_ActiveBuilder_even_when_Neuron_throws()
        {
            var instanceId = "test-instance-throw-" + Guid.NewGuid().ToString("N");
            var memory = new InMemoryFakeMemoryService();
            var neuron = new FlowGraphFakeNeuron(
                neuronId: "prefrontal-cortex",
                onInvoke: _ => throw new InvalidOperationException("intentional throw"));

            var pfcDesc = BuildPrefrontalDescriptor();
            var pfc = new PrefrontalCortex(
                descriptor: pfcDesc,
                memory: memory,
                neuron: neuron,
                callback: null,
                callableBrains: Array.Empty<BrainBase>(),
                brainRegistry: new InMemoryBrainRegistry(),
                instanceId: instanceId,
                projectRoot: _tempRoot);

            var invocation = new BrainInvocation(
                CorrelationId: "corr-throw",
                Intent: "ignored",
                StructuredInput: null,
                Context: new Dictionary<string, object>());

            Assert.ThrowsAsync<InvalidOperationException>(async () =>
                await pfc.InvokeAsync(invocation, CancellationToken.None));

            Assert.That(pfc.ActiveBuilder, Is.Null,
                "Neuron 抛错时 InvokeAsync 仍必通过 finally 清回 ActiveBuilder=null。");
            await Task.CompletedTask;
        }

        // ===== helpers =====

        private static StandardBrainDescriptor BuildPrefrontalDescriptor()
        {
            return new StandardBrainDescriptor(
                brainId: "prefrontal-cortex",
                role: "prefrontal",
                soul: "主脑魂",
                kind: StandardBrainKind.PrefrontalCortex,
                capability: new AgentDescription(
                    id: "stub", name: "Stub", soul: "soul", identity: "id"))
            {
                IsPrefrontal = true,
            };
        }

        private static ParietalLobe BuildParietalWithFixedSummary(string brainId, string summary)
        {
            var memory = new InMemoryFakeMemoryService();
            var callback = new FakePrefrontalCallback();
            var neuron = new StubNeuron(brainId, new BrainOutcome(
                Summary: summary,
                StructuredOutput: null,
                SideEffects: Array.Empty<SideEffect>(),
                IsError: false,
                ErrorMessage: null));
            var desc = new StandardBrainDescriptor(
                brainId: brainId,
                role: "parietal",
                soul: "顶叶",
                kind: StandardBrainKind.ParietalLobe,
                capability: new AgentDescription(
                    id: "stub", name: "Stub", soul: "soul", identity: "id"));
            return new ParietalLobe(desc, memory, neuron, callback);
        }

        /// <summary>
        /// 测试用 Neuron——onInvoke 委托被调时表现 LLM 的行为（操作 ActiveBuilder / 返自然语言）。
        /// <see cref="INeuron.UnderlyingAgent"/> 恒 null——FlowGraph 路径不需要 msai 句柄。
        /// </summary>
        private sealed class FlowGraphFakeNeuron : INeuron
        {
            private readonly Func<BrainInvocation, BrainOutcome> _onInvoke;
            public string NeuronId { get; }
            public NeuronKind Kind => NeuronKind.Msai;
            public AIAgent? UnderlyingAgent => null;

            public FlowGraphFakeNeuron(string neuronId, Func<BrainInvocation, BrainOutcome> onInvoke)
            {
                NeuronId = neuronId;
                _onInvoke = onInvoke;
            }

            public Task<BrainOutcome> InvokeAsync(BrainInvocation invocation, CancellationToken ct)
            {
                var outcome = _onInvoke(invocation);
                return Task.FromResult(outcome);
            }

            public ValueTask DisposeAsync() => default;
        }
    }
}
#endif
