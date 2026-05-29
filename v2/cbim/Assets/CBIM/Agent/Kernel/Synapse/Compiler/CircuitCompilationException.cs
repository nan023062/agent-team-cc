using System;

namespace CBIM.AgentSystem.Kernel.Synapse.Compiler
{
    /// <summary>
    /// 神经回路编译失败——由 <see cref="NeuralCircuitBuilder.Commit"/> 在整体校验
    /// （≥1 ReturnNode / 连通性 / 无环 / Branch 出度 + BranchLabel）任一项失败时抛出。
    ///
    /// <para>C3 铁律：校验失败必回滚——主脑 <c>PrefrontalCortex.InvokeAsync</c>（T14）捕获本异常后
    /// 应丢弃当次 <see cref="NeuralCircuitBuilder"/>、回退到无图流（或重新规划），而不能让半成品
    /// 神经回路流入 Orchestrator。</para>
    ///
    /// <para>本异常仅用于「编译期整体校验失败」；Builder Add* 即时校验（节点不存在 / BranchLabel
    /// 错配 / commit 后再修改）走 <see cref="InvalidOperationException"/> / <see cref="ArgumentException"/>，
    /// 由 T10 的 AITool handler 转包为 ToolException 回 LLM——两条路径不混。</para>
    /// </summary>
    public sealed class CircuitCompilationException : Exception
    {
        /// <summary>失败原因的纯文本短语（不含前缀）——供日志 / 审计 / 主脑回退判断使用。</summary>
        public string Reason { get; }

        public CircuitCompilationException(string reason)
            : base($"NeuralCircuit 编译失败：{reason}")
        {
            Reason = reason;
        }
    }
}
