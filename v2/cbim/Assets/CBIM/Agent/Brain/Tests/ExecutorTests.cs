#if UNITY_INCLUDE_TESTS
using System;
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
    /// T11 Executor 构造期单元测试——业务行为（BrainCallExecutor outcome.IsError →
    /// RequestHalt / ReturnExecutor RenderTemplate / BranchExecutor 设 BranchLabel）
    /// 在 CBIMOrchestratorEndToEndTests 中通过实际 MAF Workflow 执行覆盖（IWorkflowContext
    /// 是 MAF 抽象层接口，单测里直接 stub 反而脆弱）。
    ///
    /// 本套件聚焦：
    ///   - 构造期 nodeId / node / brain / callback 非空校验
    ///   - BrainCallExecutor 装配期 brain.BrainId 必须与 node.TargetBrainId 对齐（fail-fast）
    /// </summary>
    [TestFixture]
    public sealed class ExecutorTests
    {
        // ===== BrainCallExecutor 构造校验 =====

        [Test]
        public void BrainCallExecutor_rejects_blank_nodeId()
        {
            var node = new CallBrainNode("n01", "label", "brain-x", "intent", null);
            var brain = BuildParietal("brain-x");
            var callback = new FakePrefrontalCallback();

            Assert.Throws<ArgumentException>(() =>
                new BrainCallExecutor(nodeId: "  ", node, brain, callback));
        }

        [Test]
        public void BrainCallExecutor_rejects_null_node()
        {
            var brain = BuildParietal("brain-x");
            var callback = new FakePrefrontalCallback();

            Assert.Throws<ArgumentNullException>(() =>
                new BrainCallExecutor("n01", node: null!, brain, callback));
        }

        [Test]
        public void BrainCallExecutor_rejects_null_brain()
        {
            var node = new CallBrainNode("n01", "label", "brain-x", "intent", null);
            var callback = new FakePrefrontalCallback();

            Assert.Throws<ArgumentNullException>(() =>
                new BrainCallExecutor("n01", node, brain: null!, callback));
        }

        [Test]
        public void BrainCallExecutor_rejects_null_callback()
        {
            var node = new CallBrainNode("n01", "label", "brain-x", "intent", null);
            var brain = BuildParietal("brain-x");

            Assert.Throws<ArgumentNullException>(() =>
                new BrainCallExecutor("n01", node, brain, callback: null!));
        }

        [Test]
        public void BrainCallExecutor_rejects_mismatched_brain_target()
        {
            // node.TargetBrainId='brain-a' 但 brain.BrainId='brain-b'——T12 装配期最后一道护栏。
            var node = new CallBrainNode("n01", "label", "brain-a", "intent", null);
            var brain = BuildParietal("brain-b");
            var callback = new FakePrefrontalCallback();

            Assert.Throws<CircuitExecutionException>(() =>
                new BrainCallExecutor("n01", node, brain, callback));
        }

        // ===== BranchExecutor 构造校验 =====

        [Test]
        public void BranchExecutor_rejects_blank_nodeId()
        {
            var node = new BranchNode("n01", "br", "previous.summary contains \"x\"");
            Assert.Throws<ArgumentException>(() =>
                new BranchExecutor(nodeId: "", node));
        }

        [Test]
        public void BranchExecutor_rejects_null_node()
        {
            Assert.Throws<ArgumentNullException>(() =>
                new BranchExecutor("n01", node: null!));
        }

        // ===== ReturnExecutor 构造校验 =====

        [Test]
        public void ReturnExecutor_rejects_blank_nodeId()
        {
            var node = new ReturnNode("n01", "ret", "{previous.summary}");
            Assert.Throws<ArgumentException>(() =>
                new ReturnExecutor(nodeId: "", node));
        }

        [Test]
        public void ReturnExecutor_rejects_null_node()
        {
            Assert.Throws<ArgumentNullException>(() =>
                new ReturnExecutor("n01", node: null!));
        }

        // ===== CircuitExecutionException 字段 =====

        [Test]
        public void CircuitExecutionException_stores_NodeId_and_formats_message()
        {
            var ex = new CircuitExecutionException("n03", "boom");
            Assert.That(ex.NodeId, Is.EqualTo("n03"));
            StringAssert.Contains("n03", ex.Message);
            StringAssert.Contains("boom", ex.Message);
        }

        [Test]
        public void CircuitExecutionException_wraps_inner_exception()
        {
            var inner = new InvalidOperationException("root cause");
            var ex = new CircuitExecutionException("n03", "boom", inner);
            Assert.That(ex.InnerException, Is.SameAs(inner));
        }

        // ===== helpers =====

        private static ParietalLobe BuildParietal(string brainId)
        {
            var memory = new InMemoryFakeMemoryService();
            var callback = new FakePrefrontalCallback();
            var neuron = new StubNeuron(brainId, new BrainOutcome(
                Summary: "ok", StructuredOutput: null,
                SideEffects: Array.Empty<SideEffect>(), IsError: false, ErrorMessage: null));
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
