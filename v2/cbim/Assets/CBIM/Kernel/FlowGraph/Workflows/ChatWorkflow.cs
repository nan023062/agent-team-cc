using System;
using Microsoft.Agents.AI.Workflows;
using CBIM.AgentSystem;

namespace CBIM.FlowGraph.Workflows
{
    /// <summary>
    /// 首版 Chat 业务拓扑：classify → respond 单向直边。
    ///
    /// 端到端示范用：
    ///   - 不写任何业务路由条件（无 Edge.Condition）。
    ///   - 拓扑写死两个 CbimTaskExecutor 节点；后续 DispatchWorkflow / ArchExecWorkflow
    ///     复用同一 Build 范式（静态方法 + WorkflowBuilder + 直边装配）。
    ///
    /// 入参约束：
    ///   - classifyAgent / respondAgent 在进场前已由 AgentSystem.OpenInstanceAsync 装配完成
    ///     （AIAgent + Session + 工具 / MCP 已挂）。本类不负责装配，仅做拓扑接线。
    ///   - sessionWriter 由 AgentSystem 实现，传给两个 Executor 用于写 Session 事件。
    /// </summary>
    public static class ChatWorkflow
    {
        public static Workflow Build(
            Agent classifyAgent,
            Agent respondAgent,
            IAgentSystemSessionWriter sessionWriter)
        {
            if (classifyAgent is null) throw new ArgumentNullException(nameof(classifyAgent));
            if (respondAgent is null) throw new ArgumentNullException(nameof(respondAgent));
            if (sessionWriter is null) throw new ArgumentNullException(nameof(sessionWriter));

            var classify = new CbimTaskExecutor("classify", sessionWriter);
            var respond = new CbimTaskExecutor("respond", sessionWriter);

            return new WorkflowBuilder(classify)
                .AddEdge(classify, respond)
                .Build();
        }
    }
}
