using System;

namespace CBIM.AgentSystem.Brain
{
    /// <summary>
    /// 副作用审计记录——MotorCortex 家族脑区在 <see cref="BrainOutcome.SideEffects"/> 中
    /// 必填的结构化记账条目。其他脑区的 SideEffects 列表通常为空。
    ///
    /// 设计意图：把「世界状态变化」从自然语言摘要中剥离出来，给上游主脑 / 治理审计
    /// 一份可结构化扫描的清单。
    /// </summary>
    /// <param name="Kind">副作用种类。常见值：<c>file-write</c> / <c>mcp-call</c> / <c>http</c> / <c>process-spawn</c> / <c>memory-write</c>。</param>
    /// <param name="Target">受影响目标的标识——文件路径 / MCP server id / URL 等。</param>
    /// <param name="Detail">可选补充信息（diff 摘要 / HTTP 状态码等）。</param>
    /// <param name="At">副作用发生时间。用 <see cref="DateTimeOffset"/> 避开时区歧义。</param>
    public sealed class SideEffect
    {
        public string Kind { get; }
        public string Target { get; }
        public string? Detail { get; }
        public DateTimeOffset At { get; }

        public SideEffect(
            string Kind,
            string Target,
            string? Detail,
            DateTimeOffset At)
        {
            this.Kind = Kind;
            this.Target = Target;
            this.Detail = Detail;
            this.At = At;
        }
    }
}
