namespace CBIM.AgentSystem.Brain
{
    /// <summary>
    /// 主脑（<c>PrefrontalCortex</c>）暴露给其他脑区的回调面。
    ///
    /// 极小化设计——只允许「回报」，不允许「反向调度」。这是
    /// 「主脑唯一通路」铁律的物理护栏：子脑区永远不能通过本接口
    /// 反向调起兄弟脑区。
    ///
    /// 主脑自身的 <see cref="BrainBase.PrefrontalCallback"/> 字段恒为 <c>null</c>
    /// （自己不回报自己）。
    /// </summary>
    public interface IPrefrontalCallback
    {
        /// <summary>
        /// 上报中间状态（如长任务进度）。
        /// 主脑可选择透传到 <c>Channel.OnOutput</c>，也可丢弃。
        /// </summary>
        /// <param name="brainId">回报方脑区 Id。</param>
        /// <param name="message">进度信息。</param>
        void ReportProgress(string brainId, string message);

        /// <summary>
        /// 上报最终产出。
        /// 主脑默认把结果合入下一轮 LLM 上下文。
        /// </summary>
        /// <param name="brainId">回报方脑区 Id。</param>
        /// <param name="outcome">最终结果。</param>
        void ReportOutcome(string brainId, BrainOutcome outcome);
    }
}
