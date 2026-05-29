#if UNITY_INCLUDE_TESTS
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.AI;
using NUnit.Framework;
using CBIM.AgentSystem;
using CBIM.AgentSystem.Brain;
using CBIM.AgentSystem.Kernel.Neuron;
using CBIM.AgentSystem.Kernel.Synapse;
using CBIM.AgentSystem.Kernel.Synapse.Compiler;
using CBIM.AgentSystem.Brain.Tests;
using CBIM.Memory;

namespace CBIM.AgentSystem.Kernel.Synapse.Compiler.Tests
{
    /// <summary>
    /// T10 CompilerToolFactory 测试——覆盖：
    ///   - Build 产 6 个工具且命名固定 (__circuit_start / __circuit_add_call_brain / ...)
    ///   - __circuit_start 幂等护栏：commit 后再 start 抛
    ///   - __circuit_add_call_brain：targetBrainId 不在 palette 抛 ToolException（InvalidOperationException）
    ///   - __circuit_add_call_brain：合法 target 落到 builder 并返新 nodeId
    ///   - __circuit_add_branch：condition 不符合正则抛
    ///   - __circuit_commit：失败包 InvalidOperationException
    ///   - __circuit_commit：成功返「committed circuit ...」描述串
    ///   - builderProvider 返 null 时所有工具抛
    ///   - callableBrains 含 null 项抛；重复 BrainId 抛
    /// </summary>
    [TestFixture]
    public sealed class CompilerToolFactoryTests
    {
        // ===== (1) Build 产 6 个工具 + 命名 =====

        [Test]
        public void Build_returns_6_tools_with_fixed_names_in_fixed_order()
        {
            var builder = new NeuralCircuitBuilder("cid", "x");
            var tools = CompilerToolFactory.Build(() => builder, Array.Empty<BrainBase>());

            Assert.That(tools.Count, Is.EqualTo(6),
                "应产 6 个工具 (start / add_call_brain / add_branch / add_return / add_edge / commit)。");

            var names = tools.OfType<AIFunction>().Select(t => t.Name).ToList();
            Assert.That(names, Is.EqualTo(new[]
            {
                "__circuit_start",
                "__circuit_add_call_brain",
                "__circuit_add_branch",
                "__circuit_add_return",
                "__circuit_add_edge",
                "__circuit_commit",
            }), "工具名 + 顺序固定（LLM 按描述自然推断使用顺序）。");
        }

        // ===== (2) Build 构造期校验 =====

        [Test]
        public void Build_rejects_null_builderProvider()
        {
            Assert.Throws<ArgumentNullException>(() =>
                CompilerToolFactory.Build(builderProvider: null!, callableBrains: Array.Empty<BrainBase>()));
        }

        [Test]
        public void Build_rejects_null_callableBrains()
        {
            Assert.Throws<ArgumentNullException>(() =>
                CompilerToolFactory.Build(() => new NeuralCircuitBuilder("cid", "x"), callableBrains: null!));
        }

        [Test]
        public void Build_rejects_null_item_in_callableBrains()
        {
            Assert.Throws<ArgumentException>(() =>
                CompilerToolFactory.Build(
                    () => new NeuralCircuitBuilder("cid", "x"),
                    callableBrains: new BrainBase?[] { null }!));
        }

        [Test]
        public void Build_rejects_duplicate_BrainId_in_callableBrains()
        {
            var p1 = BuildParietal("parietal-lobe");
            var p2 = BuildParietal("parietal-lobe");

            Assert.Throws<InvalidOperationException>(() =>
                CompilerToolFactory.Build(
                    () => new NeuralCircuitBuilder("cid", "x"),
                    callableBrains: new BrainBase[] { p1, p2 }));
        }

        // ===== (3) builderProvider 返 null → 工具调用抛 =====

        [Test]
        public async Task Tool_invocation_throws_when_builderProvider_returns_null()
        {
            var tools = CompilerToolFactory.Build(
                builderProvider: () => null!,
                callableBrains: Array.Empty<BrainBase>());
            var startTool = tools.OfType<AIFunction>().Single(t => t.Name == "__circuit_start");

            var ex = await AssertToolThrowsAsync(startTool,
                new Dictionary<string, object?> { ["sourceRequest"] = "x" });
            StringAssert.Contains("No active NeuralCircuitBuilder", ex.Message);
        }

        // ===== (4) __circuit_start 幂等护栏 =====

        [Test]
        public async Task Start_tool_succeeds_on_first_call()
        {
            var b = new NeuralCircuitBuilder("cid", "x");
            var tools = CompilerToolFactory.Build(() => b, Array.Empty<BrainBase>());
            var startTool = tools.OfType<AIFunction>().Single(t => t.Name == "__circuit_start");

            var result = await startTool.InvokeAsync(
                new AIFunctionArguments(new Dictionary<string, object?> { ["sourceRequest"] = "x" }),
                CancellationToken.None);
            Assert.That(result?.ToString(), Is.EqualTo("started"));
        }

        [Test]
        public async Task Start_tool_throws_after_Commit_succeeded()
        {
            var b = new NeuralCircuitBuilder("cid", "x");
            b.AddReturn("ret", "{previous.summary}");
            b.Commit();

            var tools = CompilerToolFactory.Build(() => b, Array.Empty<BrainBase>());
            var startTool = tools.OfType<AIFunction>().Single(t => t.Name == "__circuit_start");

            var ex = await AssertToolThrowsAsync(startTool,
                new Dictionary<string, object?> { ["sourceRequest"] = "x" });
            StringAssert.Contains("Builder 已冻结", ex.Message);
        }

        // ===== (5) __circuit_add_call_brain 校验 =====

        [Test]
        public async Task AddCallBrain_tool_throws_when_target_not_in_palette()
        {
            var p = BuildParietal("parietal-lobe");
            var b = new NeuralCircuitBuilder("cid", "x");
            var tools = CompilerToolFactory.Build(() => b, new BrainBase[] { p });
            var tool = tools.OfType<AIFunction>().Single(t => t.Name == "__circuit_add_call_brain");

            var ex = await AssertToolThrowsAsync(tool, new Dictionary<string, object?>
            {
                ["label"] = "step",
                ["targetBrainId"] = "non-existent-brain",
                ["intent"] = "do x",
                ["structuredInputJson"] = null,
            });
            StringAssert.Contains("不在可调脑区集合", ex.Message);
            StringAssert.Contains("parietal-lobe", ex.Message,
                "异常信息应列出可选 brain ids，便于 LLM 重试。");
        }

        [Test]
        public async Task AddCallBrain_tool_succeeds_and_returns_new_node_id()
        {
            var p = BuildParietal("parietal-lobe");
            var b = new NeuralCircuitBuilder("cid", "x");
            var tools = CompilerToolFactory.Build(() => b, new BrainBase[] { p });
            var tool = tools.OfType<AIFunction>().Single(t => t.Name == "__circuit_add_call_brain");

            var result = await tool.InvokeAsync(
                new AIFunctionArguments(new Dictionary<string, object?>
                {
                    ["label"] = "step",
                    ["targetBrainId"] = "parietal-lobe",
                    ["intent"] = "do x",
                    ["structuredInputJson"] = null,
                }), CancellationToken.None);

            Assert.That(result?.ToString(), Is.EqualTo("n01"),
                "成功时返回新 nodeId 以便后续 AddEdge 引用。");
        }

        // ===== (6) __circuit_add_branch 极简正则校验 =====

        [Test]
        public async Task AddBranch_tool_throws_when_condition_does_not_match_regex()
        {
            var b = new NeuralCircuitBuilder("cid", "x");
            var tools = CompilerToolFactory.Build(() => b, Array.Empty<BrainBase>());
            var tool = tools.OfType<AIFunction>().Single(t => t.Name == "__circuit_add_branch");

            // 不带引号字面量——不符合 'token (contains|equals) "value"' 形式。
            var ex = await AssertToolThrowsAsync(tool, new Dictionary<string, object?>
            {
                ["label"] = "br",
                ["conditionExpression"] = "previous.summary equals approved",
            });
            StringAssert.Contains("conditionExpression", ex.Message);
        }

        [Test]
        public async Task AddBranch_tool_accepts_valid_contains_expression()
        {
            var b = new NeuralCircuitBuilder("cid", "x");
            var tools = CompilerToolFactory.Build(() => b, Array.Empty<BrainBase>());
            var tool = tools.OfType<AIFunction>().Single(t => t.Name == "__circuit_add_branch");

            var result = await tool.InvokeAsync(
                new AIFunctionArguments(new Dictionary<string, object?>
                {
                    ["label"] = "br",
                    ["conditionExpression"] = "previous.summary contains \"approved\"",
                }), CancellationToken.None);
            Assert.That(result?.ToString(), Is.EqualTo("n01"));
        }

        // ===== (7) __circuit_commit 失败包成 InvalidOperationException =====

        [Test]
        public async Task Commit_tool_wraps_CircuitCompilationException_as_InvalidOperationException()
        {
            var b = new NeuralCircuitBuilder("cid", "x");
            // 没加任何节点——commit 会抛 CircuitCompilationException("图未声明任何节点")。
            var tools = CompilerToolFactory.Build(() => b, Array.Empty<BrainBase>());
            var tool = tools.OfType<AIFunction>().Single(t => t.Name == "__circuit_commit");

            var ex = await AssertToolThrowsAsync(tool, new Dictionary<string, object?>());
            StringAssert.Contains("commit 失败", ex.Message);
            StringAssert.Contains("未声明任何节点", ex.Message);
        }

        [Test]
        public async Task Commit_tool_succeeds_for_minimal_graph_and_returns_description()
        {
            var b = new NeuralCircuitBuilder("cid", "x");
            b.AddReturn("ret", "{previous.summary}");

            var tools = CompilerToolFactory.Build(() => b, Array.Empty<BrainBase>());
            var tool = tools.OfType<AIFunction>().Single(t => t.Name == "__circuit_commit");

            var result = await tool.InvokeAsync(
                new AIFunctionArguments(new Dictionary<string, object?>()), CancellationToken.None);
            var text = result?.ToString() ?? string.Empty;
            StringAssert.Contains("committed circuit cid", text);
            StringAssert.Contains("1 nodes", text);
            StringAssert.Contains("0 edges", text);
        }

        // ===== helpers =====

        /// <summary>
        /// 调一个 AIFunction 并断言它抛了一个异常；返回该异常以便进一步断言其 Message。
        /// AIFunction 包装层在不同 MAF 版本下可能透传 / 包装为 TargetInvocationException /
        /// AggregateException——这里 unwrap 多层以让断言聚焦内部 message。
        /// </summary>
        private static async Task<Exception> AssertToolThrowsAsync(
            AIFunction tool, IDictionary<string, object?> args)
        {
            try
            {
                await tool.InvokeAsync(new AIFunctionArguments(args), CancellationToken.None);
            }
            catch (Exception ex)
            {
                Exception inner = ex;
                // 反射 / 函数调度层可能裹一层；逐层剥到第一个非容器异常。
                while ((inner is System.Reflection.TargetInvocationException tie && tie.InnerException != null) ||
                       (inner is AggregateException agg && agg.InnerException != null))
                {
                    inner = inner.InnerException!;
                }
                return inner;
            }
            Assert.Fail("预期工具调用抛出异常，但未抛。");
            return null!;
        }

        private static ParietalLobe BuildParietal(string brainId)
        {
            var memory = new InMemoryFakeMemoryService();
            var callback = new FakePrefrontalCallback();
            var neuron = new StubNeuron(brainId, BuildOkOutcome());
            var desc = new StandardBrainDescriptor(
                brainId: brainId,
                role: "parietal",
                soul: "顶叶",
                kind: StandardBrainKind.ParietalLobe,
                capability: BuildStubCapability());
            return new ParietalLobe(desc, memory, neuron, callback);
        }

        private static AgentDescription BuildStubCapability()
        {
            return new AgentDescription(
                id: "brain-stub.test",
                name: "Test",
                soul: "stub-soul",
                identity: "stub identity");
        }

        private static BrainOutcome BuildOkOutcome()
        {
            return new BrainOutcome(
                Summary: "ok",
                StructuredOutput: null,
                SideEffects: Array.Empty<SideEffect>(),
                IsError: false,
                ErrorMessage: null);
        }
    }
}
#endif
