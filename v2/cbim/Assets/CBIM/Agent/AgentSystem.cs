using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using CBIM.AgentSystem.Brain;
using CBIM.AgentSystem.Brain.ClaudeCode;
using CBIM.Memory;
using CBIM.Memory.Bridge;
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

        /// <summary>
        /// 本次实例的 workspaceRoot（= task.Where）。MCP server 启动 / ExternalMotorCortex
        /// subprocess 工作目录均以此为锚。装配期校验：
        /// <list type="bullet">
        ///   <item>若 <see cref="AgentDescription.McpList"/> 非空 → 必填，否则抛 <see cref="InvalidOperationException"/>。</item>
        ///   <item>若 BrainConfig 含 ExternalMotorCortex 且 ShareMode==McpServer → 必填，否则抛 <see cref="InvalidOperationException"/>。</item>
        /// </list>
        /// </summary>
        public string TaskWhere { get; init; }

        /// <summary>
        /// 单次调用覆盖的记忆工厂——优先级高于 <see cref="AgentDescription.MemoryFactory"/>。
        /// 入参为新生成的 instanceId。
        /// </summary>
        public Func<string, IMemoryService> MemoryFactoryOverride { get; init; }
    }

    /// <summary>
    /// AgentSystem 服务（能力维度门面）——CBIM 能力侧的总入口。
    ///
    /// <para>类比：HR + 调度员的合体。</para>
    /// <list type="bullet">
    ///   <item>静态侧：管理「公司里都有哪些人」（AgentDescription 注册表）</item>
    ///   <item>动态侧：派工时「实例化某个人到岗」（OpenInstance）和「下班释放资源」（CloseInstance）</item>
    /// </list>
    ///
    /// <para>职责（清晰边界）：</para>
    /// <list type="number">
    ///   <item>维护 AgentDescription 注册表（构造时注入，查找按 Id）</item>
    ///   <item>装配 Agent 实例：按 BrainConfig 编织 N 个脑区，主脑最后构造（Prefrontal 需要 CallableBrains 已就绪）</item>
    ///   <item>跟踪活动实例（ListActiveInstances）</item>
    ///   <item>释放实例时确保 MotorCortex / 其他脑区 / Prefrontal / Memory / MCP / Session 资源都关</item>
    ///   <item>实现 <see cref="IAgentSystemSessionWriter"/> ——本轮以 jsonl 落盘</item>
    /// </list>
    ///
    /// <para>本轮 (task-5) 装配胶水重写：从「单一 AIAgent」改为「五源装配 + Brain 编织」。</para>
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
        /// 按 AgentDescription 装配一个 Agent（薄包装重载）。
        /// 详细装配步骤见 <see cref="OpenInstanceAsync(string, OpenInstanceOptions)"/>。
        /// </summary>
        public Task<Agent> OpenInstanceAsync(
            string descriptionId,
            string activatedByTaskId = null)
            => OpenInstanceAsync(descriptionId, new OpenInstanceOptions { ActivatedByTaskId = activatedByTaskId });

        /// <summary>
        /// 五源装配重载——按 BrainConfig 编织 N 个脑区。
        ///
        /// <para>五源装配序：</para>
        /// <list type="number">
        ///   <item>Source 0 · BrainConfig 选定（<c>desc.BrainConfig ?? BrainConfig.Default(desc.Name)</c>）</item>
        ///   <item>Source 1 · Memory 选定（<c>options.Override ?? desc.MemoryFactory ?? Default</c>）</item>
        ///   <item>Source 2 · StandardTools 装配（当前 v1 stub 可空——预留位）</item>
        ///   <item>Source 3 · McpList 装配（当前 v1 stub 可空——预留位）</item>
        ///   <item>Source 4 · Brain 编织（三构造期铁律：先非主脑，主脑最后；ExternalMotor 走 ClaudeCode 桥）</item>
        /// </list>
        ///
        /// <para>TaskWhere 必填校验：</para>
        /// <list type="bullet">
        ///   <item>desc.McpList 非空 → 必填</item>
        ///   <item>BrainConfig 含 ExternalMotorCortex 且 ShareMode==McpServer → 必填</item>
        /// </list>
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

            var instanceId = Guid.NewGuid().ToString();
            var mcpHandles = new List<IAsyncDisposable>();

            // ─── 源 0：BrainConfig 选定（缺省 fallback 4 脑装载） ──────────────────────
            var brainConfig = desc.BrainConfig ?? BrainConfig.Default(desc.Name);

            // ─── TaskWhere 必填校验（在动手装任何东西前做完所有校验） ────────────────
            ValidateTaskWhere(desc, brainConfig, options?.TaskWhere);

            // ─── 源 1：Memory 选定（优先级：override → description → 默认） ──────────
            Func<string, IMemoryService> factory =
                options?.MemoryFactoryOverride
                ?? desc.MemoryFactory
                ?? DefaultMemoryFactory();
            IMemoryService memory = factory(instanceId);

            // ─── 源 2：StandardTools 装配（v1 stub 空集合——预留位） ─────────────────
            // 未来：sandbox = BuildSandbox(workspaceRoot, instanceRunDir);
            //       stdFns = StandardToolsService.CreateFamilies(desc.SystemTools, sandbox);
            //       挂载到 NativeMotorCortex.Agent.ChatOptions.Tools（按铁律「默认能力下发到 NativeMotorCortex」）。
            // 本切片不动 StandardTools——desc.SystemTools 当前为空集合。

            // ─── 源 3：McpList 装配（v1 stub 空集合——预留位） ──────────────────────
            // 未来：foreach descriptor in desc.McpList: handle = await StartMcpAsync(...);
            //       mcpHandles.Add(handle); 工具同样下发到 NativeMotorCortex.Agent.ChatOptions.Tools。
            // 本切片不动 MCP runtime——desc.McpList 当前为空集合。

            // ─── 源 4：Brain 编织（核心新逻辑） ──────────────────────────────────────
            // 先准备 PrefrontalCallback 适配器——子脑区 ctor 强制 non-null callback。
            // v1 实施为 no-op stub（见类注释）；Prefrontal 是装配最后一步，此时主脑句柄未生成，
            // 适配器内部以 Lazy 模式延迟引用——本切片不消费该 Lazy（no-op），但模式已就位。
            var callbackAdapter = new PrefrontalCallbackAdapter();
            var brainRegistry = new InMemoryBrainRegistry();
            var brains = new List<BrainBase>(brainConfig.Brains.Count);

            // PHASE A：非 Prefrontal 脑区先构造
            StandardBrainDescriptor prefrontalDesc = null;
            foreach (var d in brainConfig.Brains)
            {
                if (d is StandardBrainDescriptor std && std.IsPrefrontal)
                {
                    prefrontalDesc = std;   // 记录，Phase B 用
                    continue;
                }

                BrainBase brain = BuildSubBrain(d, memory, callbackAdapter, options, mcpHandles);
                brainRegistry.RegisterBrain(brain);
                brains.Add(brain);
            }

            if (prefrontalDesc == null)
                throw new InvalidOperationException(
                    "BrainConfig 校验通过但未找到 Prefrontal 描述符——内部不变量违反。");

            // PHASE B：Prefrontal 最后构造（需 CallableBrains 已就绪）
            var prefrontal = new PrefrontalCortex(
                descriptor: prefrontalDesc,
                memory: memory,
                chatClient: _chatClient,
                callableBrains: brains);
            brainRegistry.RegisterBrain(prefrontal);
            brains.Add(prefrontal);

            // 回填 callback adapter（v1 no-op 但模式已就位）
            callbackAdapter.AttachPrefrontal(prefrontal);

            // ─── Session：由主脑 AIAgent 生成（agent.RunAsync 投递目标 = prefrontal.Agent） ──
            var session = await prefrontal.Agent.CreateSessionAsync().ConfigureAwait(false);

            // ─── 包成 Agent + 注册 ───────────────────────────────────────────────────
            var instance = new Agent(
                instanceId: instanceId,
                description: desc,
                brains: brains,
                prefrontal: prefrontal,
                session: session,
                brainRegistry: brainRegistry,
                mcpHandles: mcpHandles,
                activatedByTaskId: options?.ActivatedByTaskId,
                memory: memory);

            lock (_instancesLock)
            {
                _activeInstances[instanceId] = instance;
            }

            return instance;
        }

        /// <summary>
        /// 按描述符子类分派构造一个非 Prefrontal 脑区——Phase A 内部使用。
        /// ExternalMotorCortex 路径在此启 memory-bridge MCP（如 ShareMode==McpServer）
        /// 并把句柄登记到 mcpHandles。
        /// </summary>
        private BrainBase BuildSubBrain(
            BrainDescriptor d,
            IMemoryService memory,
            IPrefrontalCallback callback,
            OpenInstanceOptions options,
            List<IAsyncDisposable> mcpHandles)
        {
            switch (d)
            {
                case StandardBrainDescriptor std:
                    return BuildStandardBrain(std, memory, callback);

                case ExternalMotorCortexDescriptor ext:
                    return BuildExternalBrain(ext, memory, callback, options, mcpHandles);

                default:
                    throw new InvalidOperationException(
                        $"未识别的 BrainDescriptor 子类: {d.GetType().FullName}");
            }
        }

        /// <summary>
        /// 构造 4 种标准脑区——按 <see cref="StandardBrainKind"/> 派发。
        /// PrefrontalCortex 由 Phase B 单独处理（需 CallableBrains），不进入本方法。
        /// </summary>
        private BrainBase BuildStandardBrain(
            StandardBrainDescriptor std,
            IMemoryService memory,
            IPrefrontalCallback callback)
        {
            switch (std.Kind)
            {
                case StandardBrainKind.ParietalLobe:
                    return new ParietalLobe(std, memory, _chatClient, callback);

                case StandardBrainKind.Hippocampus:
                    return new Hippocampus(std, memory, _chatClient, callback);

                case StandardBrainKind.NativeMotorCortex:
                    // 铁律：AgentDescription.SystemTools / McpList 默认全部下发到 NativeMotorCortex。
                    // 本切片 stdFns / mcpFns 暂为空集合（v1 StandardTools / Mcp runtime 未实装）；
                    // 后续切片在此处把工具挂到 brain.Agent.ChatOptions.Tools（msai ChatClientAgent
                    // 不可变 → 需重建 Agent，见 PrefrontalCortex.ctor 同款模式）。
                    return new NativeMotorCortex(std, memory, _chatClient, callback);

                case StandardBrainKind.PrefrontalCortex:
                    throw new InvalidOperationException(
                        "BuildStandardBrain 不处理 PrefrontalCortex——主脑由 OpenInstanceAsync 的 Phase B 装配。");

                default:
                    throw new InvalidOperationException(
                        $"未识别的 StandardBrainKind: {std.Kind}");
            }
        }

        /// <summary>
        /// 构造 ExternalMotorCortex——首发桥接 ClaudeCode；其他 EngineKind 抛 NotImplementedException。
        /// 若 ShareMode == McpServer：启动 memory-bridge MCP server 并登记到 mcpHandles 生命周期。
        /// </summary>
        private BrainBase BuildExternalBrain(
            ExternalMotorCortexDescriptor ext,
            IMemoryService memory,
            IPrefrontalCallback callback,
            OpenInstanceOptions options,
            List<IAsyncDisposable> mcpHandles)
        {
            // EngineKind 路由（仅 ClaudeCode 实施）
            if (ext.EngineKind != ExternalEngineKind.ClaudeCode)
                throw new NotImplementedException(
                    $"ExternalEngineKind '{ext.EngineKind}' 在 v1 未实施——首发仅 ClaudeCode。");

            // ShareMode 路由（仅 McpServer 实施）
            string memoryMcpEndpoint = null;
            if (ext.MemoryShareMode == MemoryShareMode.McpServer)
            {
                // 启动 in-proc memory-bridge MCP server——把 IAsyncDisposable 登记到 mcpHandles，
                // CloseInstance 期会通过 Agent.DisposeAsync 收尾。
                //
                // v1 已知妥协：Unity asmdef 不支持独立 ConsoleApp entry point，
                // 当前 server 仅以 in-proc 对象形式构造，没有把 stdio bridge 接到 ClaudeCode subprocess
                // 的 stdin/stdout——因此 ClaudeCodeAdapterConfig.MemoryMcpEndpoint 暂留 null，
                // ClaudeCode subprocess 在 v1 不会通过 MCP 看到 memory_* 工具。
                // 后续切片若需打通：派生 ConsoleApp 项目 / 用 NamedPipe 把 in-proc server 桥到子进程 stdio。
                var bridge = new MemoryBridgeMcpServer(memory);
                mcpHandles.Add(bridge);
                // memoryMcpEndpoint = "<待 v2 切片注入 stdio 子进程命令>";
            }
            else if (ext.MemoryShareMode != MemoryShareMode.None)
            {
                throw new NotSupportedException(
                    $"MemoryShareMode '{ext.MemoryShareMode}' 在 v1 未实施——仅 McpServer。");
            }

            // 解析 AdapterConfig 中的 cli-path / extra-args（key 由约定，无强制 schema）
            string cliPath = "claude-code";
            if (ext.AdapterConfig.TryGetValue("cli-path", out var cliObj) && cliObj is string cliStr)
                cliPath = cliStr;

            IReadOnlyList<string> extraArgs = Array.Empty<string>();
            if (ext.AdapterConfig.TryGetValue("extra-args", out var argsObj))
            {
                if (argsObj is string[] arr) extraArgs = arr;
                else if (argsObj is IReadOnlyList<string> list) extraArgs = list;
            }

            var adapterConfig = new ClaudeCodeAdapterConfig
            {
                CliPath = cliPath,
                ExtraArgs = extraArgs,
                WorkspaceRoot = options.TaskWhere,   // 校验已在 ValidateTaskWhere 完成
                MemoryMcpEndpoint = memoryMcpEndpoint,
            };

            return new ClaudeCodeMotorCortex(ext, memory, adapterConfig, callback);
        }

        /// <summary>
        /// TaskWhere 必填校验——发现违反铁律即抛 <see cref="InvalidOperationException"/>。
        /// 在动手装配任何资源前完成所有校验（fail-fast，避免半装态泄漏）。
        /// </summary>
        private static void ValidateTaskWhere(
            AgentDescription desc,
            BrainConfig brainConfig,
            string taskWhere)
        {
            bool requireForMcp = desc.McpList != null && desc.McpList.Count > 0;
            bool requireForExternal = false;

            foreach (var d in brainConfig.Brains)
            {
                if (d is ExternalMotorCortexDescriptor ext &&
                    ext.MemoryShareMode == MemoryShareMode.McpServer)
                {
                    requireForExternal = true;
                    break;
                }
            }

            if ((requireForMcp || requireForExternal) && string.IsNullOrWhiteSpace(taskWhere))
            {
                var reason = requireForExternal
                    ? "BrainConfig 含 ExternalMotorCortex 且 ShareMode==McpServer"
                    : "AgentDescription.McpList 非空";
                throw new InvalidOperationException(
                    $"OpenInstanceOptions.TaskWhere 必须非空（原因：{reason}）。");
            }
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
        /// 关闭一个 Agent：释放其持有的脑区 / Memory / MCP / Session。
        /// 释放顺序由 <see cref="Agent.DisposeAsync"/> 负责（MotorCortex → 其他脑区 →
        /// Prefrontal → Memory → McpHandles → Session）。多次调用幂等。
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

        // ===== PrefrontalCallbackAdapter =====

        /// <summary>
        /// <see cref="IPrefrontalCallback"/> 适配器——子脑区强制需要 non-null callback，
        /// 但 Prefrontal 是装配最后一步（需要 CallableBrains 已就绪），所以本适配器先以
        /// 「空壳」形式构造、注入子脑区，等 Prefrontal 构造完毕后回填引用。
        ///
        /// <para><b>v1 实施为 no-op stub</b>——本切片不路由 SessionEvent；
        /// 行为正确性由 PrefrontalCortex 默认 InvokeAsync 通过 Tool return value 路径保证；
        /// 本 callback 是预留扩展通道（后续切片可在 ReportProgress/ReportOutcome 路由到
        /// Session jsonl / Channel.OnOutput 等）。</para>
        /// </summary>
        internal sealed class PrefrontalCallbackAdapter : IPrefrontalCallback
        {
            // Lazy 模式——Phase A 构造子脑区时主脑还没建好；Phase B 完成后由 AttachPrefrontal 回填。
            // 当前 v1 不消费该引用（no-op）；保留字段是为后续 SessionEvent 路由切片预备。
            private PrefrontalCortex _prefrontal;

            /// <summary>Phase B 构造完毕后由装配胶水回填。多次调用以最后一次为准（防御性）。</summary>
            public void AttachPrefrontal(PrefrontalCortex prefrontal)
            {
                _prefrontal = prefrontal;
            }

            /// <inheritdoc/>
            public void ReportProgress(string brainId, string message)
            {
                // v1 no-op——后续切片在此路由进度到 Channel.OnOutput / Session jsonl。
            }

            /// <inheritdoc/>
            public void ReportOutcome(string brainId, BrainOutcome outcome)
            {
                // v1 no-op——后续切片在此把子脑区结果合入主脑下一轮上下文。
            }
        }
    }
}
