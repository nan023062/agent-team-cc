using System;

namespace CBIM.AgentSystem.Kernel.Synapse.Compiler
{
    /// <summary>
    /// Branch 节点——条件分支（出边带 <c>BranchLabel</c>，由 Orchestrator 在执行期解析
    /// <see cref="ConditionExpression"/> 选择走哪条边）。
    ///
    /// <para>v1 仅支持极简 <c>contains</c> / <c>equals</c> 表达式（形如
    /// <c>previous.outcome.summary contains "approved"</c>）；表达式语法在本切片不校验，
    /// 由 Orchestrator 执行时解析失败抛错——属 Compiler/.dna Non-Goals 列出的「不做表达式语言」。</para>
    ///
    /// <para>BranchNode 必须有 ≥2 条出边、且每条 BranchLabel 非空——这两条结构校验由
    /// <c>NeuralCircuitBuilder.Commit</c>（T9）在产出 <see cref="NeuralCircuit"/> 前完成。</para>
    /// </summary>
    public sealed class BranchNode : CircuitNode
    {
        /// <summary>条件表达式——非空字符串；语法由 Orchestrator 执行期校验。</summary>
        public string ConditionExpression { get; }

        public BranchNode(string nodeId, string label, string conditionExpression)
            : base(nodeId, label)
        {
            if (string.IsNullOrWhiteSpace(conditionExpression))
                throw new ArgumentException("BranchNode.ConditionExpression 不能为空。", nameof(conditionExpression));

            ConditionExpression = conditionExpression;
        }
    }
}
