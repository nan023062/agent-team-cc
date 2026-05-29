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
using CBIM.AgentSystem.Kernel.Neuron;
using CBIM.AgentSystem.Kernel.Synapse;
using CBIM.AgentSystem.Kernel.Synapse.Compiler;
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
    public sealed class OpenInstanceOptions
    {
        /// <summary>触发本次激活的 Task ID。透传给 <see cref="Agent.ActivatedByTaskId"/>。</summary>
        public string ActivatedByTaskId { get; set; }

        /// <summary>
        /// 本次实例的 workspaceRoot（= task.Where）。MCP server 启动 / ExternalMotorCortex
        /// subprocess 工作目录均以此为锚。装配期校验：
        /// <list type="bullet">
        ///   <item>若 <see cref="AgentDescription.McpList"/> 非空 → 必填，否则抛 <see cref="InvalidOperationException"/>。</item>
        ///   <item>若 BrainConfig 含 ExternalMotorCortex 且 ShareMode==McpServer → 必填，否则抛 <see cref="InvalidOperationException"/>。</item>
        /// </list>
        /// </summary>
        public string TaskWhere { get; set; }

        /// <summary>
        /// 单次调用覆盖的记忆工厂——优先级高于 <see cref="AgentDescription.MemoryFactory"/>。
        /// 入参为新生成的 instanceId。
        /// </summary>
        public Func<string, IMemoryService> MemoryFactoryOverride { get; set; }
    }

    /// <summary>
    /// AgentSystem 服务（能力维度门面）——CBIM 能力侧的总入口。
    ///
    /// <para>类比：HR + 调度员的合体。</para>
    /// <list type="bullet">
    ///   <item>静态侧：管理「公司里都有哪些人」（AgentDescription 注册表）</item>
    ///   <item>动态侧:派工时「实例化某个人到岗」（OpenInstance）和「下班释放资源」（CloseInstance）</item>
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
    /// <para>本轮（T5）装配胶水重写：从「Brain 内嵌 msai 装配」改为「NeuronFactory + SynapseToolFactory 双轨」。</para>
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
        /// 双轨装配——按 BrainConfig 编织 N 个脑区。
        ///
        /// <para>装配总序（T5 双轨重写）：</para>
        /// <list type="number">
        ///   <item>Source 0 · BrainConfig 选定（<c>desc.BrainConfig ?? BrainConfig.Default(desc.Name)</c>）</item>
        ///   <item>Source 1 · Memory 选定（<c>options.Override ?? desc.MemoryFactory ?? Default</c>）</item>
        ///   <item>Source 2 · StandardTools 装配（v1 stub 空集合——预留位）</item>
        ///   <item>Source 3 · McpList 装配（v1 stub 空集合——预留位）</item>
        ///   <item>Source 4 · Brain 编织——两阶段：
        ///     <list type="bullet">
        ///       <item>Phase 1: 为每个非主脑 descriptor 构造 <see cref="NeuronAssemblyContext"/>，
        ///             调 <see cref="NeuronFactory.Create"/> 拿 <see cref="INeuron"/>，
        ///             按 BrainKind 选择子类构造 <see cref="BrainBase"/>。</item>
        ///       <item>Phase 2: 拿 callableBrains（=已装好的非主脑），调 <see cref="SynapseToolFactory.Build"/>
        ///             拿 brainCallTools 装入主脑 <see cref="NeuronAssemblyContext.SynapseAITools"/>，
        ///             调 <see cref="NeuronFactory.Create"/> 拿主脑 Neuron，构造
        ///             <see cref="PrefrontalCortex"/> 实例。</item>
        ///     </list>
        ///   </item>
        /// </list>
        ///
        /// <para>TaskWhere 必填校验：</para>
        /// <list type="bullet">
        ///   <item>desc.McpList 非空 → 必填</item>
        ///   <item>BrainConfig 含 ExternalMotorCortex 且 ShareMode==McpServer → 必填</item>
        /// </list>
        ///
        /// <para>BrainConfig 三铁律（主脑唯一 / 至少一个 MotorCortex / BrainId 唯一）由
        /// <see cref="BrainConfig"/> 构造期校验，本方法不重复。</para>
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
            //       铁律「默认能力下发到 NativeMotorCortex」由 Phase 1 内 stdFnsForBrain 区分实现。
            // 本切片不动 StandardTools——desc.SystemTools 当前为空集合。

            // ─── 源 3：McpList 装配（v1 stub 空集合——预留位） ──────────────────────
            // 未来：foreach descriptor in desc.McpList: handle = await StartMcpAsync(...);
            //       mcpHandles.Add(handle); 工具同样下发到 NativeMotorCortex.NeuronAssemblyContext.StandardAITools。
            // 本切片不动 MCP runtime——desc.McpList 当前为空集合。

            // ─── 源 4：Brain 编织（双轨装配） ────────────────────────────────────────
            // 子脑区 ctor 强制 non-null callback——v1 用 no-op fire-and-forget 委托占位；
            // 后续切片可在 onOutcome / onProgress 中路由到 Session jsonl / Channel.OnOutput。
            var callbackAdapter = new PrefrontalCallbackAdapter(
                onOutcome: (brainId, outcome) => Task.CompletedTask,
                onProgress: (brainId, message) => Task.CompletedTask);

            var brainRegistry = new InMemoryBrainRegistry();
            var brains = new List<BrainBase>(brainConfig.Brains.Count);

            // ─── Phase 1：非主脑先装 ────────────────────────────────────────────────
            // BrainConfig 三铁律已保证恰有一个主脑，此处按 IsPrefrontal 过滤即可。
            StandardBrainDescriptor prefrontalDesc = null;
            foreach (var bd in brainConfig.Brains)
            {
                if (bd is StandardBrainDescriptor std && std.IsPrefrontal)
                {
                    prefrontalDesc = std;
                    continue;
                }

                BrainBase brain = BuildNonPrefrontalBrain(bd, memory, callbackAdapter, options, mcpHandles);
                brainRegistry.RegisterBrain(brain);
                brains.Add(brain);
            }

            if (prefrontalDesc == null)
                throw new InvalidOperationException(
                    "BrainConfig 校验通过但未找到 Prefrontal 描述符——内部不变量违反。");

            // ─── Phase 2：主脑最后装（需 callableBrains 已就绪） ────────────────────
            // 双工厂并排：
            //   - SynapseToolFactory.Build 产 __brain_call_* AITool 集——退化路径用（K3 铁律）。
            //   - CompilerToolFactory.Build 产 __circuit_* AITool 集——FlowGraph 编图路径用（T14）。
            //   两者拼到主脑 NeuronAssemblyContext.StandardAITools（DNA Brain.PrefrontalCortex
            //   FlowGraph 重定义节伪代码：synapseTools.Concat(compilerTools)）；
            //   SynapseAITools 字段在 T14 后退化为「为兼容老 Neuron 装配路径保留」位。
            //
            // CompilerToolFactory 接受 Func<NeuralCircuitBuilder> 委托——因 builder 是 per-invocation
            // 的（PrefrontalCortex.InvokeAsync 每轮 new），装配期 builder 还不存在；委托捕获
            // 「主脑实例字段读取」闭包，工具每次调用时读最新值。装配顺序约束：committee 必须
            // 先声明 prefrontal 局部变量持后续 new 的实例，闭包才能在调用时拿到。
            PrefrontalCortex? prefrontalRef = null;
            Func<NeuralCircuitBuilder> activeBuilderProvider = () =>
            {
                var current = prefrontalRef?.ActiveBuilder;
                if (current == null)
                    throw new InvalidOperationException(
                        "__circuit_* 工具在 PrefrontalCortex.InvokeAsync 窗口外被调——契约违反。");
                return current;
            };

            IReadOnlyList<AITool> brainCallTools = SynapseToolFactory.Build(brains);
            IReadOnlyList<AITool> compilerTools = CompilerToolFactory.Build(activeBuilderProvider, brains);
            var combinedMainBrainTools = new List<AITool>(brainCallTools.Count + compilerTools.Count);
            combinedMainBrainTools.AddRange(brainCallTools);
            combinedMainBrainTools.AddRange(compilerTools);

            var prefrontalCtx = new NeuronAssemblyContext(
                ChatClient: _chatClient,
                Memory: memory,
                StandardAITools: combinedMainBrainTools,   // T14：__brain_call_* + __circuit_* 合并
                SynapseAITools: Array.Empty<AITool>(),     // T14：原 SynapseAITools 字段退化为预留位
                ExternalAdapter: null);                    // 主脑必 Native，外部 adapter 必 null
            INeuron prefrontalNeuron = NeuronFactory.Create(prefrontalDesc, prefrontalCtx);

            var prefrontal = new PrefrontalCortex(
                descriptor: prefrontalDesc,
                memory: memory,
                neuron: prefrontalNeuron,
                callback: null,                              // 主脑回调恒为 null（自己不回报自己）
                callableBrains: brains,
                brainRegistry: brainRegistry,
                instanceId: instanceId,
                projectRoot: null);                          // null = 进程 cwd（FileBackend 同一惯例）
            prefrontalRef = prefrontal;                      // 闭包此刻看到非 null 实例
            brainRegistry.RegisterBrain(prefrontal);
            brains.Add(prefrontal);

            // ─── Session：由主脑 Neuron 的底层 msai AIAgent 生成 ─────────────────────
            // 主脑必走 MsaiNeuron 路径——UnderlyingAgent 必非 null。
            AIAgent prefrontalAgent = prefrontal.Agent
                ?? throw new InvalidOperationException(
                    "Prefrontal.Agent (= Neuron.UnderlyingAgent) 为 null——主脑必须走 MsaiNeuron 路径。");
            var session = await prefrontalAgent.CreateSessionAsync().ConfigureAwait(false);

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
        /// 按描述符子类 + 语义 Kind/EngineKind 分派构造一个非主脑脑区（Phase 1 内部使用）。
        ///
        /// <para>装配步骤：</para>
        /// <list type="number">
        ///   <item>按描述符子类构造 <see cref="NeuronAssemblyContext"/>——
        ///         为 ExternalMotor 装配 adapter，为 NativeMotor 准备 stdTools 通道（v1 留空）。</item>
        ///   <item>调 <see cref="NeuronFactory.Create"/> 拿 <see cref="INeuron"/>。</item>
        ///   <item>按 BrainKind / EngineKind 走 <see cref="ConstructBrainByKind"/> 构造具体 <see cref="BrainBase"/>。</item>
        /// </list>
        /// </summary>
        private BrainBase BuildNonPrefrontalBrain(
            BrainDescriptor d,
            IMemoryService memory,
            IPrefrontalCallback callback,
            OpenInstanceOptions options,
            List<IAsyncDisposable> mcpHandles)
        {
            // ── 准备 NeuronAssemblyContext ──────────────────────────────────────────
            IReadOnlyList<AITool> stdToolsForBrain = Array.Empty<AITool>();

            // 铁律「默认能力下发到 NativeMotorCortex」——v1 stub 空集合，结构就位等后续切片填。
            // 后续切片在此处：if (d is StandardBrainDescriptor s && s.Kind == NativeMotorCortex)
            //   stdToolsForBrain = stdFns_plus_mcpFns;

            IExternalEngineAdapter externalAdapter = null;
            if (d is ExternalMotorCortexDescriptor ext)
            {
                externalAdapter = BuildExternalAdapter(ext, memory, options, mcpHandles);
            }

            var ctx = new NeuronAssemblyContext(
                ChatClient: _chatClient,
                Memory: memory,
                StandardAITools: stdToolsForBrain,
                SynapseAITools: Array.Empty<AITool>(),    // 非主脑不挂 __brain_call_*
                ExternalAdapter: externalAdapter);

            INeuron neuron = NeuronFactory.Create(d, ctx);

            return ConstructBrainByKind(d, memory, neuron, callback);
        }

        /// <summary>
        /// 按描述符子类型 + 语义 Kind/EngineKind 选择具体 <see cref="BrainBase"/> 子类构造。
        /// 本方法不消费 LLM / Adapter 等运行资源——只是「描述符 → 子类」的纯派发。
        /// PrefrontalCortex 不在本方法内构造（由 Phase 2 单独装配）。
        /// </summary>
        private static BrainBase ConstructBrainByKind(
            BrainDescriptor d,
            IMemoryService memory,
            INeuron neuron,
            IPrefrontalCallback callback)
        {
            switch (d)
            {
                case StandardBrainDescriptor std:
                    switch (std.Kind)
                    {
                        case StandardBrainKind.ParietalLobe:
                            return new ParietalLobe(std, memory, neuron, callback);
                        case StandardBrainKind.Hippocampus:
                            return new Hippocampus(std, memory, neuron, callback);
                        case StandardBrainKind.NativeMotorCortex:
                            return new NativeMotorCortex(std, memory, neuron, callback);
                        case StandardBrainKind.PrefrontalCortex:
                            throw new InvalidOperationException(
                                "ConstructBrainByKind 不处理 PrefrontalCortex——主脑由 OpenInstanceAsync 的 Phase 2 装配。");
                        default:
                            throw new InvalidOperationException(
                                $"未识别的 StandardBrainKind: {std.Kind}");
                    }

                case ExternalMotorCortexDescriptor ext:
                    switch (ext.EngineKind)
                    {
                        case ExternalEngineKind.ClaudeCode:
                            return new ClaudeCodeMotorCortex(ext, memory, neuron, callback);
                        default:
                            throw new NotImplementedException(
                                $"ExternalEngineKind '{ext.EngineKind}' 在 v1 未实施——首发仅 ClaudeCode。");
                    }

                default:
                    throw new InvalidOperationException(
                        $"未识别的 BrainDescriptor 子类: {d.GetType().FullName}");
            }
        }

        /// <summary>
        /// 为 ExternalMotorCortex 路径构造 <see cref="IExternalEngineAdapter"/>。
        /// 仅 ClaudeCode 实施；其他 EngineKind 抛 <see cref="NotImplementedException"/>。
        /// 若 ShareMode == McpServer：启动 memory-bridge MCP server 并登记到 mcpHandles 生命周期。
        /// </summary>
        private IExternalEngineAdapter BuildExternalAdapter(
            ExternalMotorCortexDescriptor ext,
            IMemoryService memory,
            OpenInstanceOptions options,
            List<IAsyncDisposable> mcpHandles)
        {
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

            return new ClaudeCodeEngineAdapter(adapterConfig);
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
    }
}
