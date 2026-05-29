using System;
using System.Diagnostics;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Agents.AI;
using Microsoft.Agents.AI.Workflows;
using CBIM.AgentSystem;
using CBIM.TaskScheduler;

namespace CBIM.FlowGraph
{
    /// <summary>
    /// 把一条 CbimTask 转一次 AIAgent.RunAsync 的 Executor。
    ///
    /// 仅做三件事：
    ///   1. 写一条 UserInputEvent（task.What 作为用户消息）
    ///   2. 调 task.Who.AIAgent.RunAsync(task.What, task.Who.Session, options:null, ct)
    ///   3. 写一条 OutputEvent（response.Text 作为输出）
    ///
    /// 关键约束：
    ///   - Session 写侧的 instanceId 永远取 task.Who.InstanceId（CBIM GUID），
    ///     不可用 task.Who.AIAgent.Id（Microsoft GUID，每次 AsAIAgent 重生）。
    ///   - 写 Session 失败按 swallow + log 降级——主路径（RunAsync）不能被审计/落盘失败拖崩。
    ///   - 不做工具/MCP 装配——task.Who.AIAgent 进场时已装好。
    /// </summary>
    public sealed class CbimTaskExecutor : Executor<CbimTask, AgentResponse>
    {
        private readonly IAgentSystemSessionWriter _sessionWriter;

        public CbimTaskExecutor(string id, IAgentSystemSessionWriter sessionWriter)
            : base(id)
        {
            if (sessionWriter is null) throw new ArgumentNullException(nameof(sessionWriter));
            _sessionWriter = sessionWriter;
        }

        public override async ValueTask<AgentResponse> HandleAsync(
            CbimTask task,
            IWorkflowContext context,
            CancellationToken cancellationToken = default)
        {
            if (task is null) throw new ArgumentNullException(nameof(task));
            if (task.Who is null) throw new ArgumentException("CbimTask.Who 不能为空", nameof(task));

            string instanceId = task.Who.InstanceId;

            TryAppend(instanceId, new UserInputEvent(
                eventId: Guid.NewGuid().ToString("N"),
                timestamp: DateTime.UtcNow,
                userMessage: task.What));

            AgentResponse response = await task.Who.AIAgent
                .RunAsync(task.What, task.Who.Session, options: null, cancellationToken)
                .ConfigureAwait(false);

            TryAppend(instanceId, new OutputEvent(
                eventId: Guid.NewGuid().ToString("N"),
                timestamp: DateTime.UtcNow,
                outputText: response?.Text ?? string.Empty));

            return response;
        }

        private void TryAppend(string instanceId, SessionEvent ev)
        {
            try
            {
                _sessionWriter.AppendSessionEvent(instanceId, ev);
            }
            catch (Exception ex)
            {
                // swallow + log：审计落盘失败不能拖崩主路径
                Trace.WriteLine(
                    $"[CbimTaskExecutor] AppendSessionEvent 失败（已忽略）：instanceId={instanceId}, eventType={ev.GetType().Name}, error={ex.GetType().Name}: {ex.Message}");
            }
        }
    }
}
