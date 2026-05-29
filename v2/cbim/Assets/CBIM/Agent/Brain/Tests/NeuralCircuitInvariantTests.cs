#if UNITY_INCLUDE_TESTS
using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using NUnit.Framework;
using CBIM.AgentSystem.Kernel.Synapse.Compiler;

namespace CBIM.AgentSystem.Kernel.Synapse.Compiler.Tests
{
    /// <summary>
    /// T8 IR 不变量测试——覆盖：
    ///   - NeuralCircuit 构造期非空/非空白校验（CircuitId / SourceRequest / StartNodeId / nodes / edges）
    ///   - CallBrainNode / BranchNode / ReturnNode / CallToolNode 子类构造期字段校验
    ///   - CircuitEdge 构造期校验
    ///   - Nodes / Edges 是只读集合（防御性包装）
    /// </summary>
    [TestFixture]
    public sealed class NeuralCircuitInvariantTests
    {
        // ===== (1) NeuralCircuit 构造期非空校验 =====

        [Test]
        public void NeuralCircuit_rejects_blank_CircuitId()
        {
            Assert.Throws<ArgumentException>(() => new NeuralCircuit(
                circuitId: "   ",
                sourceRequest: "do x",
                startNodeId: "n01",
                nodes: Array.Empty<CircuitNode>(),
                edges: Array.Empty<CircuitEdge>(),
                compiledAt: DateTimeOffset.UtcNow));
        }

        [Test]
        public void NeuralCircuit_rejects_blank_SourceRequest()
        {
            Assert.Throws<ArgumentException>(() => new NeuralCircuit(
                circuitId: "cid-1",
                sourceRequest: "",
                startNodeId: "n01",
                nodes: Array.Empty<CircuitNode>(),
                edges: Array.Empty<CircuitEdge>(),
                compiledAt: DateTimeOffset.UtcNow));
        }

        [Test]
        public void NeuralCircuit_rejects_blank_StartNodeId()
        {
            Assert.Throws<ArgumentException>(() => new NeuralCircuit(
                circuitId: "cid-1",
                sourceRequest: "do x",
                startNodeId: " ",
                nodes: Array.Empty<CircuitNode>(),
                edges: Array.Empty<CircuitEdge>(),
                compiledAt: DateTimeOffset.UtcNow));
        }

        [Test]
        public void NeuralCircuit_rejects_null_nodes()
        {
            Assert.Throws<ArgumentNullException>(() => new NeuralCircuit(
                circuitId: "cid-1",
                sourceRequest: "do x",
                startNodeId: "n01",
                nodes: null!,
                edges: Array.Empty<CircuitEdge>(),
                compiledAt: DateTimeOffset.UtcNow));
        }

        [Test]
        public void NeuralCircuit_rejects_null_edges()
        {
            Assert.Throws<ArgumentNullException>(() => new NeuralCircuit(
                circuitId: "cid-1",
                sourceRequest: "do x",
                startNodeId: "n01",
                nodes: Array.Empty<CircuitNode>(),
                edges: null!,
                compiledAt: DateTimeOffset.UtcNow));
        }

        // ===== (2) Nodes/Edges 是只读集合 =====

        [Test]
        public void NeuralCircuit_Nodes_and_Edges_are_ReadOnly()
        {
            var node = new ReturnNode("n01", "ret", "{previous.summary}");
            var circuit = new NeuralCircuit(
                circuitId: "cid-1",
                sourceRequest: "do x",
                startNodeId: "n01",
                nodes: new CircuitNode[] { node },
                edges: Array.Empty<CircuitEdge>(),
                compiledAt: DateTimeOffset.UtcNow);

            Assert.That(circuit.Nodes, Is.InstanceOf<ReadOnlyCollection<CircuitNode>>(),
                "Nodes 必须是 ReadOnlyCollection 的物理护栏，C1 / K7 铁律。");
            Assert.That(circuit.Edges, Is.InstanceOf<ReadOnlyCollection<CircuitEdge>>(),
                "Edges 必须是 ReadOnlyCollection 的物理护栏。");
        }

        [Test]
        public void NeuralCircuit_defensively_copies_input_lists()
        {
            var node = new ReturnNode("n01", "ret", "{previous.summary}");
            var inputNodes = new List<CircuitNode> { node };
            var inputEdges = new List<CircuitEdge>();

            var circuit = new NeuralCircuit(
                circuitId: "cid-1",
                sourceRequest: "do x",
                startNodeId: "n01",
                nodes: inputNodes,
                edges: inputEdges,
                compiledAt: DateTimeOffset.UtcNow);

            inputNodes.Clear();  // 改外部 list

            Assert.That(circuit.Nodes.Count, Is.EqualTo(1),
                "构造期应做防御性复制——外部 list 修改不影响内部状态。");
        }

        // ===== (3) CompiledAt 转 UTC =====

        [Test]
        public void NeuralCircuit_normalizes_CompiledAt_to_UTC()
        {
            var local = new DateTimeOffset(2026, 1, 1, 8, 0, 0, TimeSpan.FromHours(8));
            var circuit = new NeuralCircuit(
                circuitId: "cid-1",
                sourceRequest: "do x",
                startNodeId: "n01",
                nodes: Array.Empty<CircuitNode>(),
                edges: Array.Empty<CircuitEdge>(),
                compiledAt: local);

            Assert.That(circuit.CompiledAt.Offset, Is.EqualTo(TimeSpan.Zero),
                "CompiledAt 必须归一化到 UTC——避免本地时区参与审计比较。");
        }

        // ===== (4) CircuitNode 派生类构造校验 =====

        [Test]
        public void CallBrainNode_rejects_blank_fields()
        {
            Assert.Throws<ArgumentException>(() =>
                new CallBrainNode("n01", "label", targetBrainId: "  ", intent: "x", structuredInputJson: null));
            Assert.Throws<ArgumentException>(() =>
                new CallBrainNode("n01", "label", targetBrainId: "brain", intent: "", structuredInputJson: null));
            Assert.Throws<ArgumentException>(() =>
                new CallBrainNode(nodeId: " ", label: "l", targetBrainId: "b", intent: "i", structuredInputJson: null));
            Assert.Throws<ArgumentException>(() =>
                new CallBrainNode(nodeId: "n01", label: "", targetBrainId: "b", intent: "i", structuredInputJson: null));
        }

        [Test]
        public void CallBrainNode_accepts_null_structured_input_json()
        {
            // StructuredInputJson 允许 null（CallBrainNode 文档约定）。
            var node = new CallBrainNode("n01", "label", targetBrainId: "brain-x", intent: "do", structuredInputJson: null);
            Assert.That(node.StructuredInputJson, Is.Null);
            Assert.That(node.TargetBrainId, Is.EqualTo("brain-x"));
            Assert.That(node.Intent, Is.EqualTo("do"));
        }

        [Test]
        public void BranchNode_rejects_blank_ConditionExpression()
        {
            Assert.Throws<ArgumentException>(() =>
                new BranchNode("n01", "br", conditionExpression: ""));
            Assert.Throws<ArgumentException>(() =>
                new BranchNode("n01", "br", conditionExpression: "   "));
        }

        [Test]
        public void ReturnNode_rejects_blank_SummaryTemplate()
        {
            Assert.Throws<ArgumentException>(() =>
                new ReturnNode("n01", "ret", summaryTemplate: ""));
        }

        [Test]
        public void CallToolNode_rejects_blank_fields()
        {
            Assert.Throws<ArgumentException>(() =>
                new CallToolNode("n01", "l", toolName: "", argsJson: "{}"));
            Assert.Throws<ArgumentException>(() =>
                new CallToolNode("n01", "l", toolName: "system.read_file", argsJson: ""));
        }

        // ===== (5) CircuitEdge 构造校验 =====

        [Test]
        public void CircuitEdge_rejects_blank_From_or_To()
        {
            Assert.Throws<ArgumentException>(() =>
                new CircuitEdge(fromNodeId: " ", toNodeId: "n02", branchLabel: null));
            Assert.Throws<ArgumentException>(() =>
                new CircuitEdge(fromNodeId: "n01", toNodeId: "", branchLabel: null));
        }

        [Test]
        public void CircuitEdge_accepts_null_BranchLabel()
        {
            // BranchLabel 是 nullable string——「源非 BranchNode 时必为 null」由 Builder 校验，
            // CircuitEdge 自身不感知节点类型。
            var edge = new CircuitEdge("n01", "n02", branchLabel: null);
            Assert.That(edge.BranchLabel, Is.Null);
        }
    }
}
#endif
