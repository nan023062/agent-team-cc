using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

namespace CBIM.AgentSystem
{
    /// <summary>
    /// AgentSystem 服务（能力维度门面）——CBIM 能力侧的总入口。
    ///
    /// 类比：HR + 调度员的合体。
    ///   - 静态侧：管理"公司里都有哪些人"（AgentDescription 注册表）
    ///   - 动态侧：派工时"实例化某个人到岗"（OpenInstance）和"下班释放资源"（CloseInstance）
    ///
    /// 职责（清晰边界）：
    ///   1. 维护 AgentDescription 注册表（构造时注入，查找按 Id）
    ///   2. 装配 AIAgent 实例：用 Microsoft.Agents.AI 的 AsAIAgent 工厂，
    ///      把 AgentDescription.Soul/Identity 装进 ChatClientAgentOptions
    ///   3. 跟踪活动实例（ListActiveInstances）
    ///   4. 释放实例时确保 MCP / Session 资源都关
    ///
    /// 不做的事（其他模块的责任）：
    ///   - SystemTools 工厂调用 → 由 Tools/Standard 接管，OpenInstance 调用 StandardToolsService
    ///   - MCP server 启动 → 等 Mcp/McpRuntime 实现后由它做
    ///   - AIContextProvider 注入 → 由 Kernel/ContextProviders 负责
    ///   - Skills 注入到上下文 → 由 Microsoft AgentSkillsProvider 接管
    ///
    /// 当前 v1：OpenInstance 仅做最基础装配（IChatClient → AsAIAgent + CreateSessionAsync）。
    /// 工具 / Provider / MCP 装配在后续切片里增量补全。
    /// </summary>
    public sealed class AgentSystem
    {
        private readonly Dictionary<string, AgentDescription> _descriptions;
        private readonly Dictionary<string, Agent> _activeInstances;
        private readonly IChatClient _chatClient;
        private readonly object _instancesLock = new object();

        /// <summary>
        /// 构造 AgentSystem。
        /// </summary>
        /// <param name="descriptions">已知的 AgentDescription 集合（按 Id 索引）。</param>
        /// <param name="chatClient">所有 agent 共用的 IChatClient 后端（OpenAI / Anthropic 等）。
        /// 未来如需按 agent 切换 provider，改为 IChatClientFactory 注入。</param>
        public AgentSystem(IEnumerable<AgentDescription> descriptions, IChatClient chatClient)
        {
            if (descriptions == null) throw new ArgumentNullException(nameof(descriptions));
            if (chatClient == null) throw new ArgumentNullException(nameof(chatClient));

            _descriptions = new Dictionary<string, AgentDescription>();
            foreach (var d in descriptions)
            {
                if (_descriptions.ContainsKey(d.Id))
                    throw new ArgumentException($"AgentDescription.Id 重复：{d.Id}", nameof(descriptions));
                _descriptions[d.Id] = d;
            }

            _chatClient = chatClient;
            _activeInstances = new Dictionary<string, Agent>();
        }

        // ===== 静态侧：AgentDescription 注册表 =====

        /// <summary>列出全部已注册的 AgentDescription。</summary>
        public IReadOnlyList<AgentDescription> ListDescriptions()
        {
            return new List<AgentDescription>(_descriptions.Values);
        }

        /// <summary>按 Id 找 AgentDescription。找不到返 null。</summary>
        public AgentDescription GetDescription(string id)
        {
            if (string.IsNullOrWhiteSpace(id)) return null;
            return _descriptions.TryGetValue(id, out var d) ? d : null;
        }

        /// <summary>判断指定 Id 的 AgentDescription 是否已注册。</summary>
        public bool ContainsDescription(string id) =>
            !string.IsNullOrWhiteSpace(id) && _descriptions.ContainsKey(id);

        // ===== 动态侧：Agent 生命周期 =====

        /// <summary>
        /// 按 AgentDescription 装配一个 Agent。
        ///
        /// 装配步骤（v1 最小版）：
        ///   1. 找 AgentDescription
        ///   2. 拼 ChatClientAgentOptions（Name / Description / Instructions）
        ///   3. IChatClient.AsAIAgent(opts) → AIAgent
        ///   4. agent.CreateSessionAsync() → AgentSession
        ///   5. 包成 Agent + 加入 _activeInstances
        ///
        /// 未来补全（按需切片）：
        ///   - SystemTools 装配：Tools/Standard.StandardToolsService 按家族 + sandbox 实例化 AIFunction
        ///   - MCP 装配：Mcp/McpRuntime 启动 server + tools/list + 包 AIFunction
        ///   - Skills 注入：Microsoft AgentSkillsProvider
        ///   - ContextProviders：Kernel/ContextProviders 注入 Workspace / Memory / Session 上下文
        /// </summary>
        public async Task<Agent> OpenInstanceAsync(
            string descriptionId,
            string activatedByTaskId = null)
        {
            var desc = GetDescription(descriptionId);
            if (desc == null)
                throw new ArgumentException($"未找到 AgentDescription: {descriptionId}", nameof(descriptionId));

            // 1. 装配 ChatClientAgentOptions
            var opts = new ChatClientAgentOptions
            {
                Name = desc.Name,
                Description = desc.Identity,
                Instructions = desc.Soul,
                // ChatOptions.Tools - 未来填充（SystemTools + MCP 工具合并）
            };

            // 2. 构造 AIAgent（IChatClient.AsAIAgent 扩展方法，来自 Microsoft.Agents.AI）
            var aiAgent = _chatClient.AsAIAgent(opts);

            // 3. 创建 Session（agent 用 ValueTask 返回，await 自动适配）
            var session = await aiAgent.CreateSessionAsync().ConfigureAwait(false);

            // 4. 包成 Agent
            var instanceId = Guid.NewGuid().ToString();
            var instance = new Agent(
                instanceId: instanceId,
                description: desc,
                aiAgent: aiAgent,
                session: session,
                mcpHandles: null,
                activatedByTaskId: activatedByTaskId);

            lock (_instancesLock)
            {
                _activeInstances[instanceId] = instance;
            }

            return instance;
        }

        /// <summary>
        /// 关闭一个 Agent：释放其持有的 MCP handles + Session。
        /// 已关闭的实例再次调用幂等。
        /// </summary>
        public async ValueTask CloseInstanceAsync(Agent instance)
        {
            if (instance == null) return;

            lock (_instancesLock)
            {
                _activeInstances.Remove(instance.InstanceId);
            }

            await instance.DisposeAsync().ConfigureAwait(false);
        }

        /// <summary>列出当前活动中的 Agent（已 OpenInstance 但未 Close）。</summary>
        public IReadOnlyList<Agent> ListActiveInstances()
        {
            lock (_instancesLock)
            {
                return new List<Agent>(_activeInstances.Values);
            }
        }

        /// <summary>按 InstanceId 查活动实例。找不到返 null。</summary>
        public Agent GetActiveInstance(string instanceId)
        {
            if (string.IsNullOrWhiteSpace(instanceId)) return null;
            lock (_instancesLock)
            {
                return _activeInstances.TryGetValue(instanceId, out var i) ? i : null;
            }
        }
    }
}
