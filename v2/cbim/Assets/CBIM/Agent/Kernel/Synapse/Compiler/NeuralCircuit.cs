using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;

namespace CBIM.AgentSystem.Kernel.Synapse.Compiler
{
    /// <summary>
    /// 神经回路——FlowGraph 编译产物（IR 顶层）。
    ///
    /// <para>一次 user request 编译产出 1 个 <see cref="NeuralCircuit"/>；其后交给 Orchestrator
    /// 执行。执行完归档（由主脑写入
    /// <c>.cbim/agentsystem/sessions/{instanceId}/circuits/{circuitId}.json</c>），本类型自身不感知落盘。</para>
    ///
    /// <para>C1 / K7 铁律：commit 后所有字段冻结——<see cref="Nodes"/> / <see cref="Edges"/>
    /// 通过 <see cref="ReadOnlyCollection{T}"/> 物理护栏，下游消费者（Orchestrator / 序列化器）
    /// 无法回头修改图本身。需「重规划」时主脑发起新一轮编译产出新 <see cref="CircuitId"/>。</para>
    ///
    /// <para>本构造器只做字段非空 / 非空白校验与不可变包装。图结构语义校验（连通性 / 无环 /
    /// Branch 出度 / Return 可达）由 <c>NeuralCircuitBuilder.Commit</c>（T9）在构造前完成。</para>
    /// </summary>
    public sealed class NeuralCircuit
    {
        /// <summary>回路 Id——Guid 字符串，编译期由 Builder 生成。</summary>
        public string CircuitId { get; }

        /// <summary>原始 user NL——保留供审计 / 重放 / prompt 复盘。</summary>
        public string SourceRequest { get; }

        /// <summary>入口节点 Id——必为 <see cref="Nodes"/> 中某个节点的 NodeId。</summary>
        public string StartNodeId { get; }

        /// <summary>全部节点——只读视图。Builder 内部 list 在此处一次性包装为
        /// <see cref="ReadOnlyCollection{T}"/>，外部无法转回可写。</summary>
        public IReadOnlyList<CircuitNode> Nodes { get; }

        /// <summary>全部边——只读视图，同 <see cref="Nodes"/>。</summary>
        public IReadOnlyList<CircuitEdge> Edges { get; }

        /// <summary>编译完成时刻——统一存 UTC（<see cref="DateTimeOffset.UtcDateTime"/>），
        /// 避免本地时区参与审计比较。</summary>
        public DateTimeOffset CompiledAt { get; }

        public NeuralCircuit(
            string circuitId,
            string sourceRequest,
            string startNodeId,
            IReadOnlyList<CircuitNode> nodes,
            IReadOnlyList<CircuitEdge> edges,
            DateTimeOffset compiledAt)
        {
            if (string.IsNullOrWhiteSpace(circuitId))
                throw new ArgumentException("NeuralCircuit.CircuitId 不能为空。", nameof(circuitId));
            if (string.IsNullOrWhiteSpace(sourceRequest))
                throw new ArgumentException("NeuralCircuit.SourceRequest 不能为空。", nameof(sourceRequest));
            if (string.IsNullOrWhiteSpace(startNodeId))
                throw new ArgumentException("NeuralCircuit.StartNodeId 不能为空。", nameof(startNodeId));
            if (nodes == null)
                throw new ArgumentNullException(nameof(nodes));
            if (edges == null)
                throw new ArgumentNullException(nameof(edges));

            CircuitId = circuitId;
            SourceRequest = sourceRequest;
            StartNodeId = startNodeId;
            Nodes = new ReadOnlyCollection<CircuitNode>(new List<CircuitNode>(nodes));
            Edges = new ReadOnlyCollection<CircuitEdge>(new List<CircuitEdge>(edges));
            CompiledAt = compiledAt.ToUniversalTime();
        }
    }
}
