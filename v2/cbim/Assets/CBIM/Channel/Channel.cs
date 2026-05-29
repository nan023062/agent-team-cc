using System;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Agents.AI;

// Alias 消歧——避免在签名 / 字段类型中写 `CBIM.AgentSystem.Agent` 这种长名。
using AgentInstance = CBIM.AgentSystem.Agent;

namespace CBIM.Channel
{
    /// <summary>
    /// CBIM 入口层对象——一个 Channel = 一个用户交互窗口实例，1:1 绑定一个 Agent。
    ///
    /// <para>本类是 Microsoft <see cref="AgentSession"/> 的<b>薄封装</b>——CBIM 的所有
    /// 复杂度（脑区编织 / 工具装配 / Memory 桥接）都在 Agent 层完成；Channel 只暴露
    /// 「四件事」给上层 UI / Unity 场景层：</para>
    /// <list type="number">
    ///   <item><see cref="ChannelService.OpenChannelAsync"/>——开通</item>
    ///   <item><see cref="SendAsync"/>——投递一轮用户消息</item>
    ///   <item><see cref="OnOutput"/>——订阅主脑产出</item>
    ///   <item><see cref="ChannelService.CloseChannelAsync"/>——关闭</item>
    /// </list>
    ///
    /// <para><b>薄封装铁律</b>：Channel 不直接访问 Memory / Workspace / Storage；
    /// 不直接调 IChatClient；不写 Session 日志（CbimTaskExecutor / 业务 Workflow 职责）；
    /// 不加业务路由（业务路由是 Workflow 职责）。
    /// 本 v1 阶段 <see cref="SendAsync"/> 走直调 <see cref="AIAgent.RunAsync(string, AgentThread, AgentRunOptions, CancellationToken)"/>
    /// 路径——Workflow 包装路径见 Kernel/FlowGraph 切片，本类不感知。</para>
    /// </summary>
    public sealed class Channel
    {
        /// <summary>Channel 唯一 ID（Guid）——由 <see cref="ChannelService.OpenChannelAsync"/> 生成。</summary>
        public string ChannelId { get; }

        /// <summary>
        /// 主脑 AIAgent 句柄——<c>= instance.Prefrontal.Agent</c>（≡ <c>instance.AIAgent</c>）。
        /// 「Channel.Agent 实际指向 PrefrontalCortex 的 AIAgent」铁律的物理落地——
        /// 其他脑区（ParietalLobe / Hippocampus / MotorCortex.*）对 Channel 不可见。
        /// </summary>
        public AIAgent Agent { get; }

        /// <summary>
        /// Microsoft AgentSession——多轮对话共享同一 session 维持 context。
        /// 由 <c>AgentSystem.OpenInstanceAsync</c> 在装配期通过
        /// <c>prefrontal.Agent.CreateSessionAsync</c> 生成，Channel 仅读引用不重建。
        /// </summary>
        public AgentSession Session { get; }

        /// <summary>
        /// 每轮 <see cref="SendAsync"/> 完成时（成功 / 失败均）发射一次。
        /// Unity 场景层 / UI 订阅本事件即可获得对话流。
        /// 失败 Text 形如 <c>"[ERROR] &lt;message&gt;"</c>。
        /// </summary>
        public event Action<ChannelOutputEvent> OnOutput;

        /// <summary>
        /// 关联的 Agent 实例引用——<see cref="ChannelService.CloseChannelAsync"/>
        /// 期通过本字段反查并归还 AgentSystem。Channel 不直接调用 Agent 的任何方法
        /// （除了 <see cref="Agent"/> 句柄的 RunAsync 路径）。
        /// </summary>
        internal AgentInstance Instance { get; }

        /// <summary>
        /// 构造 Channel——仅供 <see cref="ChannelService"/> 调用（<c>internal</c>）。
        /// 外部调用方必须走 <see cref="ChannelService.OpenChannelAsync"/>。
        /// </summary>
        internal Channel(string channelId, AgentInstance instance)
        {
            if (string.IsNullOrWhiteSpace(channelId))
                throw new ArgumentException("channelId 不能为空", nameof(channelId));
            if (instance == null)
                throw new ArgumentNullException(nameof(instance));
            if (instance.Prefrontal == null)
                throw new ArgumentException(
                    "Agent.Prefrontal 不能为 null——Channel 必须能拿到主脑 AIAgent 句柄。",
                    nameof(instance));
            if (instance.Prefrontal.Agent == null)
                throw new ArgumentException(
                    "Agent.Prefrontal.Agent 不能为 null——PrefrontalCortex 装配未生成 msai AIAgent。",
                    nameof(instance));
            if (instance.Session == null)
                throw new ArgumentException(
                    "Agent.Session 不能为 null——Channel 需复用主脑 AgentSession 维持多轮上下文。",
                    nameof(instance));

            ChannelId = channelId;
            Instance = instance;
            Agent = instance.Prefrontal.Agent;
            Session = instance.Session;
        }

        /// <summary>
        /// 投递一轮用户消息到主脑 AIAgent，等待汇总文本返回。
        ///
        /// <para>路径（直调，v1）：</para>
        /// <list type="number">
        ///   <item>调 <c>Agent.RunAsync(userMessage, Session, options:null, ct)</c>。</item>
        ///   <item>读 <c>response.Text</c> 作为结果。</item>
        ///   <item>发射 <see cref="OnOutput"/>（成功 Text=结果 / 失败 Text=<c>"[ERROR] ..."</c>）。</item>
        ///   <item>返回 <see cref="ChannelOutcome"/>。</item>
        /// </list>
        ///
        /// <para>错误处理：异常被吞并转译为 <see cref="ChannelOutcome.IsError"/>=true 的结果——
        /// 调用方拿 outcome 即可判定，不必再 try/catch。<see cref="OperationCanceledException"/>
        /// 同样按错误返回（保持「SendAsync 不抛」的契约一致性；调用方仍可检查传入 ct 自行
        /// 处理取消语义）。</para>
        /// </summary>
        public async Task<ChannelOutcome> SendAsync(string userMessage, CancellationToken ct = default)
        {
            if (userMessage == null)
                throw new ArgumentNullException(nameof(userMessage));

            string resultText;
            try
            {
                AgentResponse response = await Agent
                    .RunAsync(userMessage, Session, options: null, ct)
                    .ConfigureAwait(false);
                resultText = response?.Text ?? string.Empty;
            }
            catch (Exception ex)
            {
                // 失败路径：发射 [ERROR] 事件 + 返回 IsError=true outcome
                RaiseOutput("[ERROR] " + ex.Message);
                return new ChannelOutcome(
                    resultText: string.Empty,
                    isError: true,
                    errorMessage: ex.Message);
            }

            RaiseOutput(resultText);
            return new ChannelOutcome(
                resultText: resultText,
                isError: false,
                errorMessage: null);
        }

        /// <summary>
        /// 发射 <see cref="OnOutput"/> 事件——订阅者抛异常时不向上传播
        /// （单订阅者失败不应破坏其他订阅者 + Channel 自身）。
        /// </summary>
        private void RaiseOutput(string text)
        {
            var handler = OnOutput;
            if (handler == null) return;

            var ev = new ChannelOutputEvent(
                channelId: ChannelId,
                text: text,
                at: DateTimeOffset.UtcNow);

            foreach (var subscriber in handler.GetInvocationList())
            {
                try
                {
                    ((Action<ChannelOutputEvent>)subscriber)(ev);
                }
                catch
                {
                    // 订阅者异常隔离——不影响其他订阅者 / Channel 主路径
                }
            }
        }
    }
}
