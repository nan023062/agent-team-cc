using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using CBIM.Memory;
using CBIM.Storage;

namespace CBIM.AgentSystem
{
    /// <summary>
    /// <see cref="AgentSystem.OpenInstanceAsync(string, OpenInstanceOptions)"/>
    /// 的可选装配参数。所有字段可空（null = 走默认逻辑）。
    ///
    /// <see cref="MemoryFactoryOverride"/> 优先级最高（per-call 覆盖）；
    /// 其次是 <see cref="AgentDescription.MemoryFactory"/>（per-description 默认）；
    /// 最后落到 <see cref="AgentSystem"/> 的默认工厂（要求构造时注入了 FileBackend）。
    /// </summary>
    public sealed record OpenInstanceOptions
    {
        /// <summary>触发本次激活的 Task ID。透传给 <see cref="Agent.ActivatedByTaskId"/>。</summary>
        public string ActivatedByTaskId { get; init; }

        /// <summary>预留：本次实例参与的 Task where 条件（用于未来上下文过滤）。</summary>
        public IReadOnlyList<string> TaskWhere { get; init; }

        /// <summary>
        /// 单次调用覆盖的记忆工厂——优先级高于 <see cref="AgentDescription.MemoryFactory"/>。
        /// 入参为新生成的 instanceId。
        /// </summary>
        public Func<string, IMemoryService> MemoryFactoryOverride { get; init; }
    }

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
    ///   5. 实现 <see cref="IAgentSystemSessionWriter"/> ——本轮以 jsonl 落盘
    ///      （&lt;root&gt;/.cbim/agentsystem/sessions/&lt;instanceId&gt;.jsonl 一行一条 JSON envelope）
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
    public sealed class AgentSystem : IAgentSystemSessionWriter
    {
        private const string SessionsRelDir = ".cbim/agentsystem/sessions";

        private static readonly JsonSerializerOptions JsonOptions = new JsonSerializerOptions
        {
            WriteIndented = false,
        };

        private static readonly UTF8Encoding Utf8NoBom = new UTF8Encoding(false);

        private readonly Dictionary<string, AgentDescription> _descriptions;
        private readonly Dictionary<string, Agent> _activeInstances;
        private readonly IChatClient _chatClient;
        private readonly FileBackend _fileBackend;
        private readonly object _instancesLock = new object();
        private readonly object _sessionLock = new object();

        /// <summary>
        /// 构造 AgentSystem（无 Session 落盘）。Session 写入将抛
        /// <see cref="InvalidOperationException"/>——需 jsonl 持久化时改用带
        /// <see cref="FileBackend"/> 的重载。
        /// </summary>
        public AgentSystem(IEnumerable<AgentDescription> descriptions, IChatClient chatClient)
            : this(descriptions, chatClient, fileBackend: null)
        {
        }

        /// <summary>
        /// 构造 AgentSystem。
        /// </summary>
        /// <param name="descriptions">已知的 AgentDescription 集合（按 Id 索引）。</param>
        /// <param name="chatClient">所有 agent 共用的 IChatClient 后端（OpenAI / Anthropic 等）。
        /// 未来如需按 agent 切换 provider，改为 IChatClientFactory 注入。</param>
        /// <param name="fileBackend">可选——共享的 <see cref="FileBackend"/>。传入则
        /// <see cref="AppendSessionEvent"/> / <see cref="ReadSessionTail"/> 落 jsonl；
        /// null 时这两个方法将抛 <see cref="InvalidOperationException"/>。</param>
        public AgentSystem(
            IEnumerable<AgentDescription> descriptions,
            IChatClient chatClient,
            FileBackend fileBackend)
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
            _fileBackend = fileBackend;
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
        public Task<Agent> OpenInstanceAsync(
            string descriptionId,
            string activatedByTaskId = null)
            => OpenInstanceAsync(descriptionId, new OpenInstanceOptions { ActivatedByTaskId = activatedByTaskId });

        /// <summary>
        /// 完整装配重载：除常规字段外允许 per-call 覆盖记忆工厂。
        ///
        /// 记忆工厂选择优先级：
        ///   1. <see cref="OpenInstanceOptions.MemoryFactoryOverride"/>（本次调用显式给的）
        ///   2. <see cref="AgentDescription.MemoryFactory"/>（描述符自带）
        ///   3. AgentSystem 默认工厂——按 <c>memory/&lt;instanceId&gt;</c> 子目录新建
        ///      <see cref="FileMemoryBackend"/>，要求构造 AgentSystem 时注入 <see cref="FileBackend"/>
        /// </summary>
        public async Task<Agent> OpenInstanceAsync(
            string descriptionId,
            OpenInstanceOptions options)
        {
            if (string.IsNullOrWhiteSpace(descriptionId))
                throw new ArgumentException("descriptionId 不能为空", nameof(descriptionId));

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

            // 4. 选定记忆工厂并实例化（优先级：override → description → 默认）
            var instanceId = Guid.NewGuid().ToString();
            Func<string, IMemoryService> factory =
                options?.MemoryFactoryOverride
                ?? desc.MemoryFactory
                ?? DefaultMemoryFactory();
            IMemoryService memory = factory(instanceId);

            // 5. 包成 Agent
            var instance = new Agent(
                instanceId: instanceId,
                description: desc,
                aiAgent: aiAgent,
                session: session,
                mcpHandles: null,
                activatedByTaskId: options?.ActivatedByTaskId,
                memory: memory);

            lock (_instancesLock)
            {
                _activeInstances[instanceId] = instance;
            }

            return instance;
        }

        /// <summary>
        /// 默认记忆工厂——按 instanceId 隔离的 <see cref="FileMemoryBackend"/>。
        /// 要求构造 AgentSystem 时注入了 <see cref="FileBackend"/>；否则在调用点抛
        /// <see cref="InvalidOperationException"/>，强制 Composition Root 显式选择策略。
        /// </summary>
        private Func<string, IMemoryService> DefaultMemoryFactory()
        {
            if (_fileBackend == null)
                throw new InvalidOperationException(
                    "AgentSystem cannot construct default Memory: " +
                    "no FileBackend was injected, and neither AgentDescription.MemoryFactory " +
                    "nor OpenInstanceOptions.MemoryFactoryOverride was provided. " +
                    "Composition Root must explicitly choose a MemoryFactory.");
            return instanceId => new FileMemoryBackend(_fileBackend, $"memory/{instanceId}");
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

        // ===== Session 写侧（IAgentSystemSessionWriter） =====

        /// <inheritdoc />
        public void AppendSessionEvent(string instanceId, SessionEvent ev)
        {
            if (string.IsNullOrWhiteSpace(instanceId))
                throw new ArgumentException("instanceId 不能为空", nameof(instanceId));
            if (ev == null)
                throw new ArgumentNullException(nameof(ev));
            EnsureFileBackend();

            string envelope = SerializeEnvelope(ev);
            string path = ResolveSessionPath(instanceId);

            lock (_sessionLock)
            {
                _fileBackend.AppendLine(path, envelope);
            }
        }

        /// <inheritdoc />
        public IReadOnlyList<SessionEvent> ReadSessionTail(string instanceId, int n)
        {
            if (string.IsNullOrWhiteSpace(instanceId))
                throw new ArgumentException("instanceId 不能为空", nameof(instanceId));
            if (n <= 0) return Array.Empty<SessionEvent>();
            EnsureFileBackend();

            string path = ResolveSessionPath(instanceId);
            if (!_fileBackend.Exists(path)) return Array.Empty<SessionEvent>();

            // 末 N 行：先 ring-buffer 收集所有行（jsonl 每实例文件通常不会很大；
            // 若未来出现 GB 级文件，再切换为反向流式读取）。
            var ring = new string[n];
            int count = 0, head = 0;

            lock (_sessionLock)
            {
                using (var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
                using (var sr = new StreamReader(fs, Utf8NoBom))
                {
                    string line;
                    while ((line = sr.ReadLine()) != null)
                    {
                        if (line.Length == 0) continue;
                        ring[head] = line;
                        head = (head + 1) % n;
                        count++;
                    }
                }
            }

            int kept = Math.Min(count, n);
            int start = count > n ? head : 0;
            var result = new List<SessionEvent>(kept);
            for (int i = 0; i < kept; i++)
            {
                string line = ring[(start + i) % n];
                var ev = TryDeserializeEnvelope(line);
                if (ev != null) result.Add(ev);
            }
            return result;
        }

        private void EnsureFileBackend()
        {
            if (_fileBackend == null)
                throw new InvalidOperationException(
                    "Session 落盘需注入 FileBackend——请使用带 FileBackend 的 AgentSystem 构造重载。");
        }

        private string ResolveSessionPath(string instanceId)
        {
            // FileBackend.ResolveCbimPath 仅按段拼接，目录由其内部 EnsureParent 创建。
            return _fileBackend.ResolveCbimPath(SessionsRelDir, instanceId + ".jsonl");
        }

        // ===== Envelope 序列化：{"type":"LlmCall","data":{...}} =====
        // 用显式 switch 派发避免依赖 System.Text.Json 多态特性（跨版本稳定）。

        private static string SerializeEnvelope(SessionEvent ev)
        {
            string typeName;
            string dataJson;
            switch (ev)
            {
                case UserInputEvent e:
                    typeName = "UserInput";
                    dataJson = JsonSerializer.Serialize(e, JsonOptions);
                    break;
                case LlmCallEvent e:
                    typeName = "LlmCall";
                    dataJson = JsonSerializer.Serialize(e, JsonOptions);
                    break;
                case ToolInvocationEvent e:
                    typeName = "ToolInvocation";
                    dataJson = JsonSerializer.Serialize(e, JsonOptions);
                    break;
                case OutputEvent e:
                    typeName = "Output";
                    dataJson = JsonSerializer.Serialize(e, JsonOptions);
                    break;
                case ErrorEvent e:
                    typeName = "Error";
                    dataJson = JsonSerializer.Serialize(e, JsonOptions);
                    break;
                default:
                    throw new NotSupportedException(
                        $"未知 SessionEvent 子类型：{ev.GetType().FullName}——请在 SerializeEnvelope/TryDeserializeEnvelope 同步登记。");
            }
            // 手拼 envelope 避免再分配一个 wrapper 对象。
            return "{\"type\":\"" + typeName + "\",\"data\":" + dataJson + "}";
        }

        private static SessionEvent TryDeserializeEnvelope(string line)
        {
            try
            {
                using var doc = JsonDocument.Parse(line);
                var root = doc.RootElement;
                if (!root.TryGetProperty("type", out var typeProp)) return null;
                if (!root.TryGetProperty("data", out var dataProp)) return null;
                string typeName = typeProp.GetString();
                if (string.IsNullOrEmpty(typeName)) return null;
                string dataJson = dataProp.GetRawText();

                switch (typeName)
                {
                    case "UserInput":
                        return JsonSerializer.Deserialize<UserInputEvent>(dataJson, JsonOptions);
                    case "LlmCall":
                        return JsonSerializer.Deserialize<LlmCallEvent>(dataJson, JsonOptions);
                    case "ToolInvocation":
                        return JsonSerializer.Deserialize<ToolInvocationEvent>(dataJson, JsonOptions);
                    case "Output":
                        return JsonSerializer.Deserialize<OutputEvent>(dataJson, JsonOptions);
                    case "Error":
                        return JsonSerializer.Deserialize<ErrorEvent>(dataJson, JsonOptions);
                    default:
                        return null;   // 未知类型跳过——单行坏数据不拖垮整次读取
                }
            }
            catch (JsonException)
            {
                return null;   // 单行 JSON 损坏直接跳过
            }
        }
    }
}
