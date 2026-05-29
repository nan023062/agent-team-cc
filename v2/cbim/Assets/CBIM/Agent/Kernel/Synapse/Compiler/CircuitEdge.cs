using System;

namespace CBIM.AgentSystem.Kernel.Synapse.Compiler
{
    /// <summary>
    /// 回路边——只持 From/To NodeId，分支由 <see cref="BranchNode"/> 出多条边、
    /// 每条带 <see cref="BranchLabel"/>（与 <c>BranchNode.ConditionExpression</c> 对齐）实现。
    ///
    /// <para><see cref="BranchLabel"/> 语义：</para>
    /// <list type="bullet">
    ///   <item>当 <see cref="FromNodeId"/> 对应 <see cref="BranchNode"/> 时，必填——
    ///         Orchestrator 据此与 <c>ConditionExpression</c> 求值结果对齐选边。</item>
    ///   <item>当 <see cref="FromNodeId"/> 对应非 BranchNode（CallBrain / CallTool）时，必为 <c>null</c>——
    ///         非分支节点出单边，无标签语义。</item>
    /// </list>
    /// <para>上述「与节点类型对齐」校验由 <c>NeuralCircuitBuilder.AddEdge</c>（T9）即时完成；
    /// 本类型自身只做字段非空校验。</para>
    /// </summary>
    public sealed class CircuitEdge
    {
        /// <summary>源节点 Id——非空白；Builder.AddEdge 即时校验对应节点已声明。</summary>
        public string FromNodeId { get; }

        /// <summary>目标节点 Id——非空白；Builder.AddEdge 即时校验对应节点已声明。</summary>
        public string ToNodeId { get; }

        /// <summary>分支标签——null 表示非分支边（见类型文档）。</summary>
        public string? BranchLabel { get; }

        public CircuitEdge(string fromNodeId, string toNodeId, string? branchLabel)
        {
            if (string.IsNullOrWhiteSpace(fromNodeId))
                throw new ArgumentException("CircuitEdge.FromNodeId 不能为空。", nameof(fromNodeId));
            if (string.IsNullOrWhiteSpace(toNodeId))
                throw new ArgumentException("CircuitEdge.ToNodeId 不能为空。", nameof(toNodeId));

            FromNodeId = fromNodeId;
            ToNodeId = toNodeId;
            BranchLabel = branchLabel;
        }
    }
}
