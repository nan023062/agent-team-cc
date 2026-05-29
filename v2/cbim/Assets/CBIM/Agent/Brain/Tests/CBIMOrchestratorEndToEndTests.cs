#if UNITY_INCLUDE_TESTS
using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using NUnit.Framework;
using CBIM.AgentSystem;
using CBIM.AgentSystem.Brain;
using CBIM.AgentSystem.Brain.Tests;
using CBIM.AgentSystem.Kernel.Neuron;
using CBIM.AgentSystem.Kernel.Synapse;
using CBIM.AgentSystem.Kernel.Synapse.Compiler;
using CBIM.AgentSystem.Kernel.Synapse.Orchestrator;
using CBIM.Memory;

namespace CBIM.AgentSystem.Kernel.Synapse.Orchestrator.Tests
{
    /// <summary>
    /// T13 CBIMOrchestrator 端到端测试——通过 MAF Workflow 引擎实际跑节点：
    ///   - 3-node 直线 [CallBrain → Return] 返回 Summary
    ///   - Branch 双出口：condition 真走分支 A，结果含上游模板渲染
    ///   - BrainOutcome.IsError=true 端到端返 IsError=true
    ///   - 参数 null 校验 / Nodes 空校验
    ///   - CompileToMafWorkflow debug 路径返非 null
    /// </summary>
    [TestFixture]
    public sealed class CBIMOrchestratorEndToEndTests
    {
        // ===== (1) 线性 [CallBrain → Return] =====

        [Test]
        public async Task RunAsync_executes_linear_CallBrain_Return_and_returns_Summary()
        {
            var brain = BuildBrainWithFixedOutcome("brain-x", summary: "task-done");
            var circuit = BuildLinearCircuit("brain-x", returnTemplate: "result: {previous.summary}");

            var orchestrator = new CBIMOrchestrator();
            var outcome = await orchestrator.RunAsync(
                circuit, new BrainBase[] { brain },
                new FakePrefrontalCallback(),
                CancellationToken.None);

            Assert.That(outcome.IsError, Is.False, "正常路径不应 IsError。");
            Assert.That(outcome.Summary, Is.EqualTo("result: task-done"),
                "Summary 应等于 ReturnNode 模板渲染结果——{previous.summary} 替换为 brain 的 outcome.Summary。");
        }

        // ===== (2) Branch 双出口——condition 真路径 =====

        [Test]
        public async Task RunAsync_executes_Branch_picks_true_edge_when_contains_matches()
        {
            // CallBrain 返 "approved-by-reviewer"，分支条件 contains "approved" → true 走 retYes。
            var brain = BuildBrainWithFixedOutcome("brain-x", summary: "approved-by-reviewer");
            var circuit = BuildBranchCircuit("brain-x");

            var orchestrator = new CBIMOrchestrator();
            var outcome = await orchestrator.RunAsync(
                circuit, new BrainBase[] { brain },
                new FakePrefrontalCallback(),
                CancellationToken.None);

            Assert.That(outcome.IsError, Is.False);
            Assert.That(outcome.Summary, Does.StartWith("yes:"),
                "branchLabel='true' 出边应路由到 retYes，模板前缀 'yes:'。");
            Assert.That(outcome.Summary, Does.Contain("approved-by-reviewer"));
        }

        // ===== (3) Branch 双出口——condition 假路径 =====

        [Test]
        public async Task RunAsync_executes_Branch_picks_false_edge_when_contains_does_not_match()
        {
            var brain = BuildBrainWithFixedOutcome("brain-x", summary: "rejected-by-reviewer");
            var circuit = BuildBranchCircuit("brain-x");

            var orchestrator = new CBIMOrchestrator();
            var outcome = await orchestrator.RunAsync(
                circuit, new BrainBase[] { brain },
                new FakePrefrontalCallback(),
                CancellationToken.None);

            Assert.That(outcome.IsError, Is.False);
            Assert.That(outcome.Summary, Does.StartWith("no:"),
                "branchLabel='false' 出边应路由到 retNo，模板前缀 'no:'。");
        }

        // ===== (4) BrainOutcome.IsError=true 端到端返 IsError=true =====

        [Test]
        public async Task RunAsync_returns_IsError_true_when_brain_returns_IsError_outcome()
        {
            var brain = BuildBrainWithFixedOutcome("brain-x",
                outcome: new BrainOutcome(
                    Summary: string.Empty,
                    StructuredOutput: null,
                    SideEffects: Array.Empty<SideEffect>(),
                    IsError: true,
                    ErrorMessage: "intentional test failure"));
            var circuit = BuildLinearCircuit("brain-x", returnTemplate: "{previous.summary}");

            var orchestrator = new CBIMOrchestrator();
            var outcome = await orchestrator.RunAsync(
                circuit, new BrainBase[] { brain },
                new FakePrefrontalCallback(),
                CancellationToken.None);

            Assert.That(outcome.IsError, Is.True,
                "brain outcome.IsError=true 应端到端传成 BrainOutcome.IsError=true。");
            StringAssert.Contains("intentional test failure", outcome.ErrorMessage ?? string.Empty);
        }

        // ===== (5) 参数 / 节点校验 =====

        [Test]
        public void RunAsync_rejects_null_circuit()
        {
            var o = new CBIMOrchestrator();
            Assert.ThrowsAsync<ArgumentNullException>(async () =>
                await o.RunAsync(circuit: null!,
                    brainPalette: Array.Empty<BrainBase>(),
                    callback: new FakePrefrontalCallback(),
                    ct: CancellationToken.None));
        }

        [Test]
        public void RunAsync_rejects_null_palette()
        {
            var o = new CBIMOrchestrator();
            var circuit = BuildLinearCircuit("brain-x", "{previous.summary}");
            Assert.ThrowsAsync<ArgumentNullException>(async () =>
                await o.RunAsync(circuit, brainPalette: null!,
                    callback: new FakePrefrontalCallback(),
                    ct: CancellationToken.None));
        }

        [Test]
        public void RunAsync_rejects_null_callback()
        {
            var o = new CBIMOrchestrator();
            var circuit = BuildLinearCircuit("brain-x", "{previous.summary}");
            Assert.ThrowsAsync<ArgumentNullException>(async () =>
                await o.RunAsync(circuit, brainPalette: Array.Empty<BrainBase>(),
                    callback: null!, ct: CancellationToken.None));
        }

        // ===== (6) CompileToMafWorkflow 返非 null =====

        [Test]
        public void CompileToMafWorkflow_returns_non_null_for_valid_circuit()
        {
            var brain = BuildBrainWithFixedOutcome("brain-x", summary: "x");
            var circuit = BuildLinearCircuit("brain-x", "{previous.summary}");

            var o = new CBIMOrchestrator();
            var workflow = o.CompileToMafWorkflow(
                circuit, new BrainBase[] { brain }, new FakePrefrontalCallback());
            Assert.That(workflow, Is.Not.Null);
        }

        // ===== helpers =====

        private static NeuralCircuit BuildLinearCircuit(string targetBrainId, string returnTemplate)
        {
            var b = new NeuralCircuitBuilder("cid-e2e-linear-" + Guid.NewGuid().ToString("N"), "x");
            string n1 = b.AddCallBrain("call", targetBrainId, "do", null);
            string n2 = b.AddReturn("ret", returnTemplate);
            b.AddEdge(n1, n2, null);
            return b.Commit();
        }

        private static NeuralCircuit BuildBranchCircuit(string targetBrainId)
        {
            var b = new NeuralCircuitBuilder("cid-e2e-branch-" + Guid.NewGuid().ToString("N"), "x");
            string n1 = b.AddCallBrain("call", targetBrainId, "do", null);
            string nb = b.AddBranch("br", "previous.summary contains \"approved\"");
            string nrY = b.AddReturn("ret-yes", "yes: {previous.summary}");
            string nrN = b.AddReturn("ret-no", "no: {previous.summary}");
            b.AddEdge(n1, nb, null);
            b.AddEdge(nb, nrY, branchLabel: "true");
            b.AddEdge(nb, nrN, branchLabel: "false");
            return b.Commit();
        }

        /// <summary>
        /// 用 <see cref="StubNeuron"/> 装配一个返预设 Summary 的 <see cref="ParietalLobe"/>。
        /// ParietalLobe 的默认 InvokeAsync 透传给 Neuron，故 outcome 完全由 StubNeuron 控制。
        /// </summary>
        private static ParietalLobe BuildBrainWithFixedOutcome(string brainId, string summary)
        {
            return BuildBrainWithFixedOutcome(brainId, new BrainOutcome(
                Summary: summary,
                StructuredOutput: null,
                SideEffects: Array.Empty<SideEffect>(),
                IsError: false,
                ErrorMessage: null));
        }

        private static ParietalLobe BuildBrainWithFixedOutcome(string brainId, BrainOutcome outcome)
        {
            var memory = new InMemoryFakeMemoryService();
            var callback = new FakePrefrontalCallback();
            var neuron = new StubNeuron(brainId, outcome);
            var desc = new StandardBrainDescriptor(
                brainId: brainId,
                role: "parietal",
                soul: "顶叶",
                kind: StandardBrainKind.ParietalLobe,
                capability: new AgentDescription(
                    id: "stub", name: "Stub", soul: "soul", identity: "id"));
            return new ParietalLobe(desc, memory, neuron, callback);
        }
    }
}
#endif
