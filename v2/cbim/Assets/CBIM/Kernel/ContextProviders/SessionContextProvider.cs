using System;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.AI;
using CBIM.AgentSystem;
using CBIM.Kernel.TaskScheduler;

namespace CBIM.Kernel.ContextProviders
{
    /// <summary>
    /// Session 维度 ContextProvider 工厂。
    ///
    /// 数据源：构造期注入的 <see cref="IAgentSystemSessionWriter"/>（读侧 ReadSessionTail）。
    /// For(task) 产出一个轻量子类，调用时拿 task 对应的 Agent.InstanceId，读末 N=20 条
    /// SessionEvent，每条按子类型摘成一行注入。
    ///
    /// InstanceId 来源约定：Microsoft AIAgent 抽象没有 CBIM Agent.InstanceId 字段，
    /// 所以从 task.Params["InstanceId"] 取（字符串 Guid）。缺失时 fallback 到
    /// task.TaskId——TODO: 后续 TaskScheduler 切片应在派发时把真正的 InstanceId 注入 Params，
    /// 届时移除此 fallback。
    /// </summary>
    public sealed class SessionContextProvider : ISessionContextProvider
    {
        /// <summary>task.Params 里 InstanceId 的标准键名。装配方按此约定写入。</summary>
        public const string InstanceIdParamKey = "InstanceId";

        private const int DefaultTailN = 20;

        private readonly IAgentSystemSessionWriter _sessionWriter;

        public SessionContextProvider(IAgentSystemSessionWriter sessionWriter)
        {
            _sessionWriter = sessionWriter ?? throw new ArgumentNullException(nameof(sessionWriter));
        }

        public AIContextProvider For(CbimTask task)
        {
            if (task is null) throw new ArgumentNullException(nameof(task));
            return new Provider(_sessionWriter, task);
        }

        private sealed class Provider : AIContextProvider
        {
            private readonly IAgentSystemSessionWriter _sessionWriter;
            private readonly CbimTask                  _task;

            public Provider(IAgentSystemSessionWriter sessionWriter, CbimTask task)
            {
                _sessionWriter = sessionWriter;
                _task = task;
            }

            protected override ValueTask<AIContext> ProvideAIContextAsync(
                InvokingContext context, CancellationToken cancellationToken = default)
            {
                string text = BuildInstructions();
                return new ValueTask<AIContext>(new AIContext { Instructions = text });
            }

            private string BuildInstructions()
            {
                string instanceId = ResolveInstanceId(out bool isFallback);
                if (string.IsNullOrEmpty(instanceId))
                {
                    return "[CBIM Session] 无可用 InstanceId，跳过 Session 上下文。";
                }

                var events = _sessionWriter.ReadSessionTail(instanceId, DefaultTailN);
                if (events is null || events.Count == 0)
                {
                    return isFallback
                        ? $"[CBIM Session] (fallback to TaskId={instanceId}) 无历史事件。"
                        : "[CBIM Session] 无历史事件。";
                }

                var sb = new StringBuilder();
                sb.Append("[CBIM Session] 末 ").Append(events.Count).AppendLine(" 条事件：");
                if (isFallback)
                {
                    sb.AppendLine("  (注: 当前以 TaskId 兜底——调用方未在 task.Params 注入 InstanceId)");
                }

                foreach (var ev in events)
                {
                    sb.Append("- ").Append(ev.Timestamp.ToString("HH:mm:ss")).Append(' ')
                      .AppendLine(SummarizeEvent(ev));
                }
                return sb.ToString();
            }

            private string ResolveInstanceId(out bool isFallback)
            {
                isFallback = false;
                if (_task.Params != null
                    && _task.Params.TryGetValue(InstanceIdParamKey, out var raw)
                    && raw is string s
                    && !string.IsNullOrWhiteSpace(s))
                {
                    return s;
                }

                // TODO: 等 TaskScheduler 派发时把真正的 InstanceId 注入 Params 后移除此分支。
                isFallback = true;
                return _task.TaskId;
            }

            private static string SummarizeEvent(SessionEvent ev)
            {
                return ev switch
                {
                    UserInputEvent u      => $"UserInput: {u.UserMessage}",
                    LlmCallEvent l        => $"LlmCall: {l.PromptSummary} → {l.ResponseSummary}",
                    ToolInvocationEvent t => $"Tool({t.ToolName}, ok={t.Succeeded}): {t.ArgumentsSummary} → {t.ResultSummary}",
                    OutputEvent o         => $"Output: {o.OutputText}",
                    ErrorEvent e          => $"Error@{e.Stage} {e.ExceptionType}: {e.Message}",
                    _                     => $"{ev.GetType().Name} #{ev.EventId}",
                };
            }
        }
    }
}
