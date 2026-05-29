using System;

namespace CBIM.Channel
{
    /// <summary>
    /// <see cref="Channel.OnOutput"/> 事件载荷——每次 <see cref="Channel.SendAsync"/>
    /// 完成时（不论成功 / 失败）会发射一条。
    ///
    /// <para>Unity 场景层订阅本事件以驱动对话 UI 滚动 / TTS 朗读 / 日志面板等
    /// ——Channel 不感知 UI 实现，仅负责发射「这一轮主脑产出了什么」。</para>
    ///
    /// <para>失败时 <see cref="Text"/> 形如 <c>"[ERROR] &lt;message&gt;"</c>——保持单字段载体，
    /// 订阅方只看 Text 即可决定渲染样式（按前缀过滤）；
    /// 完整结构化错误信息走 <see cref="ChannelOutcome.IsError"/> + <c>ErrorMessage</c>。</para>
    /// </summary>
    public sealed class ChannelOutputEvent
    {
        public string ChannelId { get; }
        public string Text { get; }
        public DateTimeOffset At { get; }

        public ChannelOutputEvent(string channelId, string text, DateTimeOffset at)
        {
            ChannelId = channelId;
            Text = text;
            At = at;
        }
    }
}
