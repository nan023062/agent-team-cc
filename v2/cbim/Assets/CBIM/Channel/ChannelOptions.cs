namespace CBIM.Channel
{
    /// <summary>
    /// <see cref="ChannelService.OpenChannelAsync"/> 的入参——本 Channel 一次开通需要的
    /// 业务参数集。Channel 不再持任何 Workspace / Memory 配置，所有上下文均通过
    /// 「打开本 Channel 时的 Agent 实例」携带。
    ///
    /// <para>本轮（task-6）字段定型：</para>
    /// <list type="bullet">
    ///   <item><see cref="WorkspaceRoot"/>——单一字符串，直接透传给
    ///   <c>AgentSystem.OpenInstanceOptions.TaskWhere</c>（task-5 已把后者类型由
    ///   <c>IReadOnlyList&lt;string&gt;</c> 改为 <c>string</c>，本 Channel 层无需 wrap）。</item>
    ///   <item><see cref="ActivatedByTaskId"/>——可空；用于 Session 写日志时归因到具体
    ///   上层任务，Channel 自身不消费该字段，仅向下透传。</item>
    /// </list>
    /// </summary>
    public sealed class ChannelOptions
    {
        /// <summary>
        /// 本 Channel 绑定的 Agent 实例工作目录（task.Where）——MCP server 启动 /
        /// ExternalMotorCortex subprocess 工作目录均以此为锚。<b>必填</b>，由
        /// <see cref="ChannelService.OpenChannelAsync"/> 校验非空白。
        /// </summary>
        public string WorkspaceRoot { get; set; }

        /// <summary>
        /// 触发本 Channel 开通的上层 Task ID（可空）——透传给
        /// <c>OpenInstanceOptions.ActivatedByTaskId</c>，最终落到 <c>Agent.ActivatedByTaskId</c>。
        /// </summary>
        public string ActivatedByTaskId { get; set; } = null;
    }
}
