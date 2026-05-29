using System;

namespace CBIM.AgentSystem.Kernel.Synapse.Compiler
{
    /// <summary>
    /// Return 节点——终止节点（产出最终汇总文本回 <c>PrefrontalCortex</c>）。
    ///
    /// <para><see cref="SummaryTemplate"/> 形如 <c>{previous.summary}</c>——占位符由 Orchestrator
    /// 在执行期解析。本切片不校验占位符语法，仅做非空检查（C5 不前置约束模板表达式语法）。</para>
    ///
    /// <para>NeuralCircuit 必须至少含 1 个 <see cref="ReturnNode"/>——由
    /// <c>NeuralCircuitBuilder.Commit</c>（T9）保证。</para>
    /// </summary>
    public sealed class ReturnNode : CircuitNode
    {
        /// <summary>汇总模板——非空字符串；可含 <c>{previous.summary}</c> 等占位符。</summary>
        public string SummaryTemplate { get; }

        public ReturnNode(string nodeId, string label, string summaryTemplate)
            : base(nodeId, label)
        {
            if (string.IsNullOrWhiteSpace(summaryTemplate))
                throw new ArgumentException("ReturnNode.SummaryTemplate 不能为空。", nameof(summaryTemplate));

            SummaryTemplate = summaryTemplate;
        }
    }
}
