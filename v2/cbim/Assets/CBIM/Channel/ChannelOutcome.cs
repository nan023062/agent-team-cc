namespace CBIM.Channel
{
    /// <summary>
    /// <see cref="Channel.SendAsync"/> 的返回值——一次 user → agent 投递的最终结果。
    ///
    /// <para>语义两态：</para>
    /// <list type="bullet">
    ///   <item><b>成功</b>：<see cref="IsError"/>=false，<see cref="ResultText"/>=主脑汇总后文本，<see cref="ErrorMessage"/>=null。</item>
    ///   <item><b>失败</b>：<see cref="IsError"/>=true，<see cref="ResultText"/>=空串，<see cref="ErrorMessage"/>=异常摘要。</item>
    /// </list>
    ///
    /// <para>注意：v1 阶段 Channel 不感知子脑区，仅返回主脑 AIAgent 的最终文本——
    /// 子脑区的调度 / 中间产出由 PrefrontalCortex 内部 LLM × AIFunction 闭环处理，
    /// 不暴露给 Channel 调用方（薄封装铁律 + 主脑唯一通路铁律的共同体现）。</para>
    /// </summary>
    public sealed record ChannelOutcome(
        string ResultText,
        bool IsError,
        string ErrorMessage);
}
