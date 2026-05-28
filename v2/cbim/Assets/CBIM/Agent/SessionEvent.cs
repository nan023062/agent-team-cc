using System;

namespace CBIM.AgentSystem
{
    /// <summary>
    /// Session 事件基类——一条 Session 日志的一个时间点状态。
    ///
    /// 设计要点：
    ///   - abstract record + 子类穷举（UserInput / LlmCall / ToolInvocation / Output / Error）
    ///   - 每条事件自带 EventId + Timestamp 两个共用字段
    ///   - 子类各自声明本类型独有的必需字段（如 LlmCallEvent.PromptSummary）
    ///   - 序列化用「envelope wrapper」格式：{"type":"LlmCall","data":{...}}
    ///     —— 不依赖 System.Text.Json 多态特性，跨版本稳定
    ///
    /// 落盘：&lt;root&gt;/.cbim/agentsystem/sessions/&lt;instanceId&gt;.jsonl
    /// 一行一条 JSON envelope。
    ///
    /// 唯一写入方：CbimTaskExecutor（业务 Workflow 节点适配器）。
    /// 唯一读出方：ContextProviders.SessionContextProvider（把末 N 条注入下一次 RunAsync 上下文）。
    /// </summary>
    public abstract record SessionEvent(string EventId, DateTime Timestamp);

    /// <summary>用户输入事件——用户发给 agent 的一条消息。</summary>
    public sealed record UserInputEvent(
        string EventId,
        DateTime Timestamp,
        string UserMessage)
        : SessionEvent(EventId, Timestamp);

    /// <summary>
    /// LLM 调用事件——一次 IChatClient 调用的元数据。
    /// 不存完整 prompt / response（避免 jsonl 膨胀），由
    /// PromptSummary / ResponseSummary 概括。
    /// </summary>
    public sealed record LlmCallEvent(
        string EventId,
        DateTime Timestamp,
        string PromptSummary,
        string ResponseSummary,
        int? PromptTokens = null,
        int? CompletionTokens = null,
        string Model = null)
        : SessionEvent(EventId, Timestamp);

    /// <summary>工具调用事件——一次 AIFunction（含 MCP 工具）调用记录。</summary>
    public sealed record ToolInvocationEvent(
        string EventId,
        DateTime Timestamp,
        string ToolName,
        string ArgumentsSummary,
        string ResultSummary,
        bool Succeeded)
        : SessionEvent(EventId, Timestamp);

    /// <summary>输出事件——agent 给出的最终回复（一次 Task 结束）。</summary>
    public sealed record OutputEvent(
        string EventId,
        DateTime Timestamp,
        string OutputText)
        : SessionEvent(EventId, Timestamp);

    /// <summary>错误事件——任意阶段抛出的异常元数据。</summary>
    public sealed record ErrorEvent(
        string EventId,
        DateTime Timestamp,
        string Stage,
        string ExceptionType,
        string Message)
        : SessionEvent(EventId, Timestamp);
}
