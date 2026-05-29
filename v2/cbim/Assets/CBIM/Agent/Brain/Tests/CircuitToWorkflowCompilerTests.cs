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
    /// T12 CircuitToWorkflowCompiler 测试——覆盖：
    ///   - null 参数 → ArgumentNullException
    ///   - palette 缺 brain（CallBrainNode.TargetBrainId 不在 palette）→ CircuitExecutionException
    ///   - CallToolNode 出现 → NotSupportedException（v1 未实装）
    ///   - 正常 3-node 线性图 build 通过返非 null Workflow
    ///   - Branch 双出口 build 通过
    /// </summary>
    [TestFixture]
    public sealed class CircuitToWorkflowCompilerTests
    {
        // ===== (1) null 参数 =====

        [Test]
        public void Compile_rejects_null_circuit()
        {
            Assert.Throws<ArgumentNullException>(() =>
                CircuitToWorkflowCompiler.Compile(
                    circuit: null!,
                    brainPalette: Array.Empty<BrainBase>(),
                    callback: new FakePrefrontalCallback()));
        }

        [Test]
        public void Compile_rejects_null_palette()
        {
            var circuit = BuildLinearCircuit("brain-x");
            Assert.Throws<ArgumentNullException>(() =>
                CircuitToWorkflowCompiler.Compile(
                    circuit,
                    brainPalette: null!,
                    callback: new FakePrefrontalCallback()));
        }

        [Test]
        public void Compile_rejects_null_callback()
        {
            var circuit = BuildLinearCircuit("brain-x");
            Assert.Throws<ArgumentNullException>(() =>
                CircuitToWorkflowCompiler.Compile(
                    circuit,
                    brainPalette: Array.Empty<BrainBase>(),
                    callback: null!));
        }

        // ===== (2) palette 缺 brain → CircuitExecutionException =====

        [Test]
        public void Compile_throws_CircuitExecutionException_when_target_brain_missing_from_palette()
        {
            var circuit = BuildLinearCircuit("brain-x");
            var ex = Assert.Throws<CircuitExecutionException>(() =>
                CircuitToWorkflowCompiler.Compile(
                    circuit,
                    brainPalette: Array.Empty<BrainBase>(),   // 空 palette
                    callback: new FakePrefrontalCallback()));
            StringAssert.Contains("brain-x", ex!.Message);
            StringAssert.Contains("BrainPalette", ex.Message);
        }

        // ===== (3) CallToolNode → NotSupportedException =====

        [Test]
        public void Compile_throws_NotSupported_for_CallToolNode_in_v1()
        {
            // 手工构造一个 NeuralCircuit 含 CallToolNode（绕过 Builder——Builder 不暴露 AddCallTool）。
            var callTool = new CallToolNode("n01", "tool", "system.read_file", "{}");
            var ret = new ReturnNode("n02", "ret", "{previous.summary}");
            var edges = new[] { new CircuitEdge("n01", "n02", null) };
            var circuit = new NeuralCircuit(
                circuitId: "cid",
                sourceRequest: "x",
                startNodeId: "n01",
                nodes: new CircuitNode[] { callTool, ret },
                edges: edges,
                compiledAt: DateTimeOffset.UtcNow);

            Assert.Throws<NotSupportedException>(() =>
                CircuitToWorkflowCompiler.Compile(
                    circuit,
                    brainPalette: Array.Empty<BrainBase>(),
                    callback: new FakePrefrontalCallback()));
        }

        // ===== (4) 正常 build 通过 =====

        [Test]
        public void Compile_succeeds_for_linear_two_node_graph()
        {
            var brain = BuildParietal("brain-x");
            var circuit = BuildLinearCircuit("brain-x");

            var workflow = CircuitToWorkflowCompiler.Compile(
                circuit,
                brainPalette: new BrainBase[] { brain },
                callback: new FakePrefrontalCallback());

            Assert.That(workflow, Is.Not.Null,
                "线性 2-node 图应能装配出 Workflow。");
        }

        [Test]
        public void Compile_succeeds_for_branch_two_outcomes_graph()
        {
            var brain = BuildParietal("brain-x");
            var branchCircuit = BuildBranchCircuit("brain-x");

            var workflow = CircuitToWorkflowCompiler.Compile(
                branchCircuit,
                brainPalette: new BrainBase[] { brain },
                callback: new FakePrefrontalCallback());

            Assert.That(workflow, Is.Not.Null,
                "Branch 双出口图应能装配出 Workflow。");
        }

        // ===== (5) StartNode 不在 Nodes 中 → CircuitExecutionException（兜底）=====

        [Test]
        public void Compile_throws_when_StartNodeId_not_in_Nodes()
        {
            // 构造一个 StartNodeId 指向不存在节点的 NeuralCircuit（构造期不校验，靠 Compiler 兜底）。
            var ret = new ReturnNode("n01", "ret", "{previous.summary}");
            var circuit = new NeuralCircuit(
                circuitId: "cid",
                sourceRequest: "x",
                startNodeId: "nXX",   // 不存在
                nodes: new CircuitNode[] { ret },
                edges: Array.Empty<CircuitEdge>(),
                compiledAt: DateTimeOffset.UtcNow);

            var ex = Assert.Throws<CircuitExecutionException>(() =>
                CircuitToWorkflowCompiler.Compile(
                    circuit,
                    brainPalette: Array.Empty<BrainBase>(),
                    callback: new FakePrefrontalCallback()));
            StringAssert.Contains("nXX", ex!.Message);
        }

        // ===== helpers =====

        private static NeuralCircuit BuildLinearCircuit(string targetBrainId)
        {
            var b = new NeuralCircuitBuilder("cid-linear", "x");
            string n1 = b.AddCallBrain("call", targetBrainId, "do", null);
            string n2 = b.AddReturn("ret", "{previous.summary}");
            b.AddEdge(n1, n2, null);
            return b.Commit();
        }

        private static NeuralCircuit BuildBranchCircuit(string targetBrainId)
        {
            var b = new NeuralCircuitBuilder("cid-branch", "x");
            string n1 = b.AddCallBrain("call", targetBrainId, "do", null);
            string nb = b.AddBranch("br", "previous.summary contains \"approved\"");
            string nrY = b.AddReturn("ret-yes", "yes: {previous.summary}");
            string nrN = b.AddReturn("ret-no", "no: {previous.summary}");
            b.AddEdge(n1, nb, null);
            b.AddEdge(nb, nrY, branchLabel: "true");
            b.AddEdge(nb, nrN, branchLabel: "false");
            return b.Commit();
        }

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
