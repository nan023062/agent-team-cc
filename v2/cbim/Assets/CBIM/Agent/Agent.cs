using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using CBIM.AgentSystem.Brain;
using CBIM.Memory;
using Microsoft.Agents.AI;

namespace CBIM.AgentSystem
{
    /// <summary>
    /// Agent 实例——一份 AgentDescription 在某次 Task 装配后的运行态对象。
    ///
    /// <para>本轮重构（task-5）：从「持单一 AIAgent」改为「持 N 个脑区 BrainBase + 主脑句柄
    /// PrefrontalCortex + Dream 裂变动态注册点 IBrainRegistry」。<see cref="AIAgent"/> 字段
    /// 保留但语义重定义为 <c>= Prefrontal.Agent</c>——不破坏 Channel 等已有调用方。</para>
    ///
    /// <para>类比「一个人」：</para>
    /// <list type="bullet">
    ///   <item><see cref="Brains"/>          = 多脑区编织体（前额叶 / 顶叶 / 海马体 / 运动皮层）</item>
    ///   <item><see cref="Prefrontal"/>      = 主脑（调度中枢 · Channel.SendAsync 实际投递目标）</item>
    ///   <item><see cref="AIAgent"/>         = Prefrontal.Agent（向下兼容字段，运行体 = 主脑的 msai AIAgent）</item>
    ///   <item>Description.Soul / Identity   = 人格 / 身份（性格与角色）</item>
    ///   <item>Description.Skills            = 经验技能（会做的事）</item>
    ///   <item>Description.SystemTools       = 随身工具（笔记本 / IDE）</item>
    ///   <item>Description.McpList           = 协作能力（接外部系统的本事）</item>
    ///   <item><see cref="Session"/>         = 当下思考记录（这次对话的脑中状态）</item>
    ///   <item><see cref="McpHandles"/>      = 启动中的工具进程（运行中的 MCP server / Memory bridge）</item>
    ///   <item><see cref="DisposeAsync"/>    = 下班关电脑（释放资源）</item>
    /// </list>
    ///
    /// <para>与 Workspace.Module（办公位）对偶——人 + 办公位 = 一次任务的完整场景。</para>
    ///
    /// <para>生命周期：</para>
    /// <list type="bullet">
    ///   <item>由 <c>AgentSystem.OpenInstanceAsync</c> 创建</item>
    ///   <item>Task 期内持续，被 Channel / FlowGraph 重复使用</item>
    ///   <item>Task 结束由 <c>AgentSystem.CloseInstanceAsync</c> 或 <see cref="DisposeAsync"/> 关闭</item>
    /// </list>
    ///
    /// <para>释放顺序（task-5 重定义）：
    /// MotorCortex 类 → 其他脑区 → Prefrontal → Memory → McpHandles → Session。</para>
    /// </summary>
    public sealed class Agent : IAsyncDisposable
    {
        /// <summary>实例唯一 ID（Guid 字符串）。Session 写日志时作为 actor 标识。</summary>
        public string InstanceId { get; }

        /// <summary>静态描述符。运行时不变。</summary>
        public AgentDescription Description { get; }

        /// <summary>
        /// 脑区集合——本轮重定义为 Agent 的多脑区编织体。
        /// 顺序：Phase A 非 Prefrontal 脑区先注入，Phase B Prefrontal 最后注入（位于列表尾）。
        /// </summary>
        public IReadOnlyList<BrainBase> Brains { get; }

        /// <summary>
        /// 主脑句柄——类型固定为 <see cref="PrefrontalCortex"/>。
        /// Channel.SendAsync 实际投递的目标 = <c>Prefrontal.Agent</c>。
        /// </summary>
        public PrefrontalCortex Prefrontal { get; }

        /// <summary>Dream 裂变产出新脑区的动态注册点。</summary>
        public IBrainRegistry BrainRegistry { get; }

        /// <summary>
        /// Microsoft AIAgent 实例——本轮语义重定义为 <c>= Prefrontal.Agent</c>，
        /// 不再要求外部传入；保留字段名是为了不破坏 Channel 等已有调用方。
        /// </summary>
        public AIAgent AIAgent { get; }

        /// <summary>
        /// Microsoft AgentSession——agent 调用历史 / 状态。
        /// 由 <c>Prefrontal.Agent.CreateSessionAsync</c> 生成；多轮对话共享同一 Session 维持 context。
        /// </summary>
        public AgentSession Session { get; }

        /// <summary>
        /// 已启动的 MCP server handles（来自 Agent.McpList + 关联 Module.McpList
        /// + ExternalMotorCortex 的 memory-bridge MCP server）。
        /// 关闭时遍历释放 server 进程 / 句柄。
        /// 当前 v1 阶段 McpRuntime 未实装，此列表通常仅含 memory-bridge（如装了 ClaudeCodeMotorCortex）。
        /// </summary>
        public IReadOnlyList<IAsyncDisposable> McpHandles { get; }

        /// <summary>
        /// CBIM Agent 的记忆实例——本 Agent 持一个 <see cref="IMemoryService"/>，
        /// 所有脑区共享同一实例（「同一具身一份记忆」铁律的物理落地）。
        /// 由 <c>AgentSystem.OpenInstanceAsync</c> 注入；调用方应保证非 null，
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
            IReadOnlyList<BrainBase> brains,
            PrefrontalCortex prefrontal,
            AgentSession session,
            IBrainRegistry brainRegistry,
            IReadOnlyList<IAsyncDisposable> mcpHandles = null,
            string activatedByTaskId = null,
            IMemoryService memory = null)
        {
            if (string.IsNullOrWhiteSpace(instanceId))
                throw new ArgumentException("Agent.InstanceId 不能为空", nameof(instanceId));
            if (description == null)
                throw new ArgumentNullException(nameof(description));
            if (brains == null)
                throw new ArgumentNullException(nameof(brains));
            if (brains.Count == 0)
                throw new ArgumentException("Agent.Brains 不能为空——至少有 1 个脑区。", nameof(brains));
            if (prefrontal == null)
                throw new ArgumentNullException(nameof(prefrontal));
            if (session == null)
                throw new ArgumentNullException(nameof(session));
            if (brainRegistry == null)
                throw new ArgumentNullException(nameof(brainRegistry));

            InstanceId = instanceId;
            Description = description;
            Brains = brains;
            Prefrontal = prefrontal;
            BrainRegistry = brainRegistry;
            AIAgent = prefrontal.Agent
                ?? throw new InvalidOperationException(
                    "Agent.AIAgent 要求 Prefrontal.Agent 非 null——PrefrontalCortex 装配未生成 msai AIAgent。");
            Session = session;
            McpHandles = mcpHandles ?? Array.Empty<IAsyncDisposable>();
            Memory = memory;
            CreatedAt = DateTimeOffset.UtcNow;
            ActivatedByTaskId = activatedByTaskId;
        }

        /// <summary>
        /// 释放本实例占用的所有资源——task-5 重定义顺序：
        /// <list type="number">
        ///   <item>MotorCortex 类脑区（外部副作用）</item>
        ///   <item>其他非 Prefrontal 脑区（ParietalLobe / Hippocampus / Dream 裂变新脑区等）</item>
        ///   <item>Prefrontal（主脑最后释放——子脑区可能在 Dispose 路径上回调主脑收尾）</item>
        ///   <item>Memory（第三方后端如 Pinecone client 需异步断开）</item>
        ///   <item>McpHandles（memory-bridge / 外部 MCP server）</item>
        ///   <item>Session（Microsoft 框架处理）</item>
        /// </list>
        /// 各步以 try/catch 隔离——单点失败不阻断后续清理。多次调用幂等。
        /// </summary>
        public async ValueTask DisposeAsync()
        {
            // 1) MotorCortex 类脑区先释放——外部副作用 / 外部进程需第一时间收尾
            foreach (var motor in Brains.OfType<MotorCortex>())
            {
                try { await motor.DisposeAsync().ConfigureAwait(false); }
                catch { /* 单点失败不阻断 */ }
            }

            // 2) 其他非 Prefrontal 非 MotorCortex 脑区
            foreach (var b in Brains)
            {
                if (b is MotorCortex) continue;
                if (b is PrefrontalCortex) continue;
                try { await b.DisposeAsync().ConfigureAwait(false); }
                catch { /* 单点失败不阻断 */ }
            }

            // 3) Prefrontal 最后释放——它是调度中枢，子脑区释放期可能仍有回调过来
            try { await Prefrontal.DisposeAsync().ConfigureAwait(false); }
            catch { /* 单点失败不阻断 */ }

            // 4) Memory（IMemoryService : IAsyncDisposable）
            if (Memory != null)
            {
                try { await Memory.DisposeAsync().ConfigureAwait(false); }
                catch { /* 单点失败不阻断 */ }
            }

            // 5) MCP handles（memory-bridge / 外部 server）
            foreach (var handle in McpHandles)
            {
                try { await handle.DisposeAsync().ConfigureAwait(false); }
                catch { /* 单 handle 失败不阻断 */ }
            }

            // 6) 最后关 Session
            if (Session is IAsyncDisposable disposableSession)
            {
                try { await disposableSession.DisposeAsync().ConfigureAwait(false); }
                catch { /* 隔离 */ }
            }
        }

        public override string ToString()
        {
            var idShort = InstanceId.Length > 8 ? InstanceId.Substring(0, 8) : InstanceId;
            return $"Agent({idShort}.., desc={Description.Id}, brains={Brains.Count}, task={ActivatedByTaskId ?? "<none>"})";
        }
    }
}
