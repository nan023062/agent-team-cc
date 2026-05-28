using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using CBIM.Memory;
using Microsoft.Agents.AI;

namespace CBIM.AgentSystem
{
    /// <summary>
    /// Agent 实例——一份 AgentDescription 在某次 Task 装配后的运行态对象。
    ///
    /// 类比："一个人"：
    ///   AIAgent (MS)                = 大脑（决策思考）
    ///   Description.Soul / Identity = 人格 / 身份（性格与角色）
    ///   Description.Skills          = 经验技能（会做的事）
    ///   Description.SystemTools     = 随身工具（笔记本 / IDE）
    ///   Description.McpList         = 协作能力（接外部系统的本事）
    ///   Session                     = 当下思考记录（这次对话的脑中状态）
    ///   McpHandles                  = 启动中的工具进程（运行中的 MCP server）
    ///   DisposeAsync                = 下班关电脑（释放资源）
    ///
    /// 与 Workspace.Module（办公位）对偶——人 + 办公位 = 一次任务的完整场景。
    ///
    /// 静态 vs 运行时（描述符 / 实例对偶）：
    ///   AgentDescription = 静态类型声明（这是哪种人，他会什么）
    ///   Agent            = 运行时具体实例（这一次出现的某个人，含 AIAgent / Session / MCP handles）
    ///
    /// 生命周期：
    ///   - 由 AgentSystem.OpenInstanceAsync(descriptionId, taskId) 创建
    ///   - Task 期内持续，被 Channel / FlowGraph 重复使用
    ///   - Task 结束由 AgentSystem.CloseInstanceAsync() 或 DisposeAsync() 关闭
    ///     - 关闭时 Microsoft AgentSession 自动清理
    ///     - 启动的 MCP server 进程通过 McpHandles 关闭
    ///
    /// 与 Module 完全对偶：
    ///   - 都持 Description（静态对应）
    ///   - 都有 InstanceId（运行时唯一标识）
    ///   - 都有 ActivatedByTaskId（哪个任务激活的，可空）
    ///   - Agent 多一份 CreatedAt + 资源（AIAgent / Session / McpHandles）；Module 仅多一份 WorkspaceRoot
    /// </summary>
    public sealed class Agent : IAsyncDisposable
    {
        /// <summary>实例唯一 ID（Guid 字符串）。Session 写日志时作为 actor 标识。</summary>
        public string InstanceId { get; }

        /// <summary>静态描述符。运行时不变。</summary>
        public AgentDescription Description { get; }

        /// <summary>Microsoft AIAgent 实例——装配完成后的可调用对象（"大脑"）。</summary>
        public AIAgent AIAgent { get; }

        /// <summary>
        /// Microsoft AgentSession——agent 调用历史 / 状态。
        /// 多轮对话共享同一 Session 维持 context。
        /// </summary>
        public AgentSession Session { get; }

        /// <summary>
        /// 已启动的 MCP server handles（来自 Agent.McpList + 关联 Module.McpList）。
        /// 关闭时遍历释放 server 进程。
        /// 当前 v1 阶段 McpRuntime 未实装，此列表为空——预留字段。
        /// </summary>
        public IReadOnlyList<IAsyncDisposable> McpHandles { get; }

        /// <summary>
        /// CBIM Agent 的记忆实例——本 Agent 持一个 <see cref="IMemoryService"/>，
        /// 同一 Agent 内 N 个 <see cref="AIAgent"/>（同质子代理）共享此实例
        /// （per-Agent，非 per-AIAgent）。
        /// 由 <c>AgentSystem.OpenInstance</c> 注入；调用方应保证非 null，
        /// 字段层为容错允许 null。
        /// </summary>
        public IMemoryService Memory { get; }

        /// <summary>激活时间戳。</summary>
        public DateTimeOffset CreatedAt { get; }

        /// <summary>触发本次激活的 Task ID。可空（如 AgentSystemService 提前预热的实例）。</summary>
        public string ActivatedByTaskId { get; }

        public Agent(
            string instanceId,
            AgentDescription description,
            AIAgent aiAgent,
            AgentSession session,
            IReadOnlyList<IAsyncDisposable> mcpHandles = null,
            string activatedByTaskId = null,
            IMemoryService memory = null)
        {
            if (string.IsNullOrWhiteSpace(instanceId))
                throw new ArgumentException("Agent.InstanceId 不能为空", nameof(instanceId));
            if (description == null)
                throw new ArgumentNullException(nameof(description));
            if (aiAgent == null)
                throw new ArgumentNullException(nameof(aiAgent));
            if (session == null)
                throw new ArgumentNullException(nameof(session));

            InstanceId = instanceId;
            Description = description;
            AIAgent = aiAgent;
            Session = session;
            McpHandles = mcpHandles ?? Array.Empty<IAsyncDisposable>();
            Memory = memory;
            CreatedAt = DateTimeOffset.UtcNow;
            ActivatedByTaskId = activatedByTaskId;
        }

        /// <summary>
        /// 释放本实例占用的所有资源：
        ///   1. 关闭所有启动的 MCP server handles（subprocess kill / connection close）
        ///   2. 释放 Memory 实例（如第三方后端 client 需异步断开）
        ///   3. 释放 AgentSession（Microsoft 框架处理）
        /// 各步以 try/catch 隔离——单点失败不阻断后续清理。多次调用幂等。
        /// </summary>
        public async ValueTask DisposeAsync()
        {
            // 1) 先释放外部句柄 MCP handles
            foreach (var handle in McpHandles)
            {
                try { await handle.DisposeAsync().ConfigureAwait(false); }
                catch { /* 单个 handle 关闭失败不影响其他 */ }
            }

            // 2) 释放 Memory（IMemoryService : IAsyncDisposable）
            if (Memory != null)
            {
                try { await Memory.DisposeAsync().ConfigureAwait(false); }
                catch { /* 单点失败不阻断 Session 关闭 */ }
            }

            // 3) 最后关 Session
            if (Session is IAsyncDisposable disposableSession)
            {
                try { await disposableSession.DisposeAsync().ConfigureAwait(false); }
                catch { /* 隔离 */ }
            }
        }

        public override string ToString()
        {
            var idShort = InstanceId.Length > 8 ? InstanceId.Substring(0, 8) : InstanceId;
            return $"Agent({idShort}.., desc={Description.Id}, task={ActivatedByTaskId ?? "<none>"})";
        }
    }
}
