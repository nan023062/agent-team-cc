#if UNITY_INCLUDE_TESTS
using System;
using NUnit.Framework;
using CBIM.AgentSystem.Kernel.Synapse.Compiler;

namespace CBIM.AgentSystem.Kernel.Synapse.Compiler.Tests
{
    /// <summary>
    /// T9 NeuralCircuitBuilder 测试——覆盖：
    ///   - 构造期非空校验
    ///   - Add* 即时校验（节点字段空白 / AddEdge 引用未声明节点 / BranchLabel 错配）
    ///   - Commit 4 项整体校验：≥1 ReturnNode / 连通性 / 无环 / Branch 出度 ≥2
    ///   - Commit 后再 Add* 抛 InvalidOperationException
    ///   - StartNodeId = 首个 Add 节点
    ///   - NodeId 分配规则 n01 / n02 / ...
    /// </summary>
    [TestFixture]
    public sealed class NeuralCircuitBuilderTests
    {
        // ===== (1) 构造期非空校验 =====

        [Test]
        public void Builder_rejects_blank_CircuitId()
        {
            Assert.Throws<ArgumentException>(() => new NeuralCircuitBuilder(circuitId: "  ", sourceRequest: "x"));
        }

        [Test]
        public void Builder_rejects_blank_SourceRequest()
        {
            Assert.Throws<ArgumentException>(() => new NeuralCircuitBuilder(circuitId: "cid", sourceRequest: ""));
        }

        // ===== (2) Add* 返回 n01 / n02 序列；StartNodeId = 首节点 =====

        [Test]
        public void Builder_allocates_node_ids_in_n01_n02_sequence_and_StartNodeId_is_first()
        {
            var b = new NeuralCircuitBuilder("cid", "do x");
            string n1 = b.AddCallBrain("call brain", "brain-x", "intent", null);
            string n2 = b.AddReturn("ret", "{previous.summary}");

            Assert.That(n1, Is.EqualTo("n01"));
            Assert.That(n2, Is.EqualTo("n02"));

            b.AddEdge(n1, n2, null);
            var circuit = b.Commit();
            Assert.That(circuit.StartNodeId, Is.EqualTo("n01"),
                "StartNodeId 应等于第一个 Add 创建的节点 Id。");
        }

        // ===== (3) Add* 即时校验：空白字段 =====

        [Test]
        public void Builder_AddCallBrain_rejects_blank_target()
        {
            var b = new NeuralCircuitBuilder("cid", "x");
            Assert.Throws<ArgumentException>(() => b.AddCallBrain("l", targetBrainId: "  ", intent: "i", structuredInputJson: null));
        }

        // ===== (4) AddEdge：节点未声明 =====

        [Test]
        public void Builder_AddEdge_rejects_unknown_source()
        {
            var b = new NeuralCircuitBuilder("cid", "x");
            b.AddReturn("ret", "{previous.summary}");
            Assert.Throws<InvalidOperationException>(() => b.AddEdge("nXX", "n01", null));
        }

        [Test]
        public void Builder_AddEdge_rejects_unknown_target()
        {
            var b = new NeuralCircuitBuilder("cid", "x");
            string n1 = b.AddCallBrain("l", "brain", "intent", null);
            Assert.Throws<InvalidOperationException>(() => b.AddEdge(n1, "nXX", null));
        }

        // ===== (5) AddEdge：BranchLabel 错配 =====

        [Test]
        public void Builder_AddEdge_rejects_missing_BranchLabel_on_BranchNode_source()
        {
            var b = new NeuralCircuitBuilder("cid", "x");
            string nb = b.AddBranch("br", "previous.summary contains \"x\"");
            string nr = b.AddReturn("ret", "{previous.summary}");
            Assert.Throws<InvalidOperationException>(() => b.AddEdge(nb, nr, branchLabel: null),
                "源为 BranchNode 时 BranchLabel 必填。");
        }

        [Test]
        public void Builder_AddEdge_rejects_BranchLabel_on_non_BranchNode_source()
        {
            var b = new NeuralCircuitBuilder("cid", "x");
            string n1 = b.AddCallBrain("l", "brain", "intent", null);
            string n2 = b.AddReturn("ret", "{previous.summary}");
            Assert.Throws<InvalidOperationException>(() => b.AddEdge(n1, n2, branchLabel: "true"),
                "源非 BranchNode 时 BranchLabel 必须为 null。");
        }

        // ===== (6) Commit 校验：≥1 ReturnNode =====

        [Test]
        public void Commit_fails_when_no_ReturnNode()
        {
            var b = new NeuralCircuitBuilder("cid", "x");
            b.AddCallBrain("l", "brain", "intent", null);
            var ex = Assert.Throws<CircuitCompilationException>(() => b.Commit());
            StringAssert.Contains("ReturnNode", ex!.Reason);
        }

        [Test]
        public void Commit_fails_on_empty_builder()
        {
            var b = new NeuralCircuitBuilder("cid", "x");
            Assert.Throws<CircuitCompilationException>(() => b.Commit());
        }

        // ===== (7) Commit 校验：连通性 =====

        [Test]
        public void Commit_fails_when_ReturnNode_unreachable_from_start()
        {
            var b = new NeuralCircuitBuilder("cid", "x");
            string n1 = b.AddCallBrain("l", "brain", "intent", null);   // n01 start
            string n2 = b.AddCallBrain("l2", "brain2", "intent2", null); // n02 不接边
            string n3 = b.AddReturn("ret", "{previous.summary}");        // n03 仅接 n02

            b.AddEdge(n2, n3, null);
            // 注意：n01 不连任何东西——n03 从 n01 不可达。

            var ex = Assert.Throws<CircuitCompilationException>(() => b.Commit());
            StringAssert.Contains("不可达", ex!.Reason);
        }

        // ===== (8) Commit 校验：无环 =====

        [Test]
        public void Commit_fails_when_cycle_detected()
        {
            var b = new NeuralCircuitBuilder("cid", "x");
            string n1 = b.AddCallBrain("a", "brain1", "i1", null);
            string n2 = b.AddCallBrain("b", "brain2", "i2", null);
            string n3 = b.AddReturn("ret", "{previous.summary}");

            b.AddEdge(n1, n2, null);
            b.AddEdge(n2, n1, null);   // 环 n01 → n02 → n01
            b.AddEdge(n2, n3, null);

            var ex = Assert.Throws<CircuitCompilationException>(() => b.Commit());
            StringAssert.Contains("环", ex!.Reason);
        }

        // ===== (9) Commit 校验：Branch 出度 ≥2 =====

        [Test]
        public void Commit_fails_when_BranchNode_has_less_than_2_outgoing_edges()
        {
            var b = new NeuralCircuitBuilder("cid", "x");
            string nb = b.AddBranch("br", "previous.summary contains \"x\"");
            string nr = b.AddReturn("ret", "{previous.summary}");

            b.AddEdge(nb, nr, branchLabel: "true");
            // 只有 1 条出边——Branch 至少要 2 条

            var ex = Assert.Throws<CircuitCompilationException>(() => b.Commit());
            StringAssert.Contains("2 条出边", ex!.Reason);
        }

        // ===== (10) Commit 成功路径 =====

        [Test]
        public void Commit_succeeds_for_minimal_valid_graph()
        {
            var b = new NeuralCircuitBuilder("cid-ok", "do x");
            string n1 = b.AddCallBrain("call", "brain-x", "do thing", null);
            string n2 = b.AddReturn("ret", "result: {previous.summary}");
            b.AddEdge(n1, n2, null);

            var circuit = b.Commit();

            Assert.That(circuit, Is.Not.Null);
            Assert.That(circuit.CircuitId, Is.EqualTo("cid-ok"));
            Assert.That(circuit.SourceRequest, Is.EqualTo("do x"));
            Assert.That(circuit.StartNodeId, Is.EqualTo("n01"));
            Assert.That(circuit.Nodes.Count, Is.EqualTo(2));
            Assert.That(circuit.Edges.Count, Is.EqualTo(1));
            Assert.That(b.Compiled, Is.SameAs(circuit),
                "Commit 成功后 Compiled 应等于返回值。");
        }

        [Test]
        public void Commit_succeeds_with_branch_two_outcomes()
        {
            var b = new NeuralCircuitBuilder("cid-br", "x");
            string n1 = b.AddCallBrain("a", "brain1", "intent", null);
            string nb = b.AddBranch("br", "previous.summary contains \"approved\"");
            string nrYes = b.AddReturn("ret-yes", "approved: {previous.summary}");
            string nrNo = b.AddReturn("ret-no", "rejected: {previous.summary}");

            b.AddEdge(n1, nb, null);
            b.AddEdge(nb, nrYes, branchLabel: "true");
            b.AddEdge(nb, nrNo, branchLabel: "false");

            var circuit = b.Commit();
            Assert.That(circuit.Nodes.Count, Is.EqualTo(4));
            Assert.That(circuit.Edges.Count, Is.EqualTo(3));
        }

        // ===== (11) Commit 后再 Add → throw =====

        [Test]
        public void Builder_after_Commit_rejects_further_Add_calls()
        {
            var b = new NeuralCircuitBuilder("cid", "x");
            b.AddReturn("ret", "{previous.summary}");
            b.Commit();

            Assert.Throws<InvalidOperationException>(() =>
                b.AddCallBrain("l", "brain", "i", null));
            Assert.Throws<InvalidOperationException>(() =>
                b.AddBranch("l", "previous.summary equals \"x\""));
            Assert.Throws<InvalidOperationException>(() =>
                b.AddReturn("l", "t"));
            Assert.Throws<InvalidOperationException>(() =>
                b.AddEdge("n01", "n01", null));
            Assert.Throws<InvalidOperationException>(() =>
                b.Commit(),
                "二次 Commit 也应被拒。");
        }
    }
}
#endif
