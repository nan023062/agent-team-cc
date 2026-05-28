namespace CBIM.AgentSystem.Brain
{
    /// <summary>
    /// PrefrontalCortex 把子脑区结果回传给用户时的合并策略。
    /// 由装配方在构造 <see cref="PrefrontalCortex"/> 时通过 init-only 设定。
    /// </summary>
    public enum PrefrontalAggregationStrategy
    {
        /// <summary>
        /// 默认——拿到子脑区结果后再走一轮 LLM 汇总后输出。
        /// 用于「主脑要把多脑区结果消化为统一答复」的标准场景。
        /// </summary>
        SummarizeBeforeReturn,

        /// <summary>
        /// 子脑区结果直接作为主脑输出，不再过一轮 LLM。
        /// 适合「镜像型」调度——主脑只是中继，子脑区已给出最终答案。
        /// </summary>
        Passthrough
    }
}
