---
name: cbim-unity-agent-system
owner: architect
description: Agent 层服务门面（v2 三层模型）。本模块是「Agent 虚拟人代理」装配服务层门面，负责 AgentDescription schema + OpenInstance 装配胶水 + Session 写侧 + per-Agent Memory。脑区重构（本轮再次修正 · 合并方案）：Brain 子模块从「拆 7 个 leaf」收敛为「一份 .dna 通览全局」，使用大脑解剖学专业名（PrefrontalCortex 主脑 / ParietalLobe 架构脑 / Hippocampus 记忆学习脑 / MotorCortex 运动皮层）。类型系统重调：BrainBase 已含 msai 装配（所有脑区天生具备 LLM 思维链）；Native/External 分支仅下沉到 MotorCortex 一支（NativeMotorCortex + ExternalMotorCortex，首发桥接 ClaudeCodeMotorCortex）——原 NativeBrain/ExternalBrain 中间抽象层取消。Agent 层服务门面本轮仅接受字段名面变动（AgentInstance.Master → Prefrontal；IBrainRegistry 保留），装配胶水仍按描述符子类分派。
keywords: []
dependencies: []
status: spec
---

## Positioning

**AgentSystem 是 CBIM Agent 层的服务门面**——v2 三层模型下，本模块在「Agent 层（虚拟人代理）」内承担「装配 Agent 实例」的服务层职责。可类比 `PersonnelService 装配 Person` —— AgentSystem 是服务层名（产生 Agent 的家），Agent 是被产生的对象（一个虚拟人代理）。

**v2 三层模型中的位置（本轮 Kernel 物理删除后）**：

```
基建层（Tool / Skill / Mcp / IMemoryService / Storage）
   ↑ 派生 / 持实例
Agent 层：Agent（本模块）+ Channel
   + Agent/Brain（多脑区编织·包含 ExternalMotorCortex/ClaudeCodeMotorCortex 桥接外部 AI 引擎）
   ↑ 不依赖 Workspace 层
Workspace 层（Workspace 模块）
```

**本轮重要变动**：原 `Kernel/` 顶层模块已物理删除（FlowGraph / TaskScheduler / ContextProviders 三子模块连同 .cs / .meta / .dna 整块 git rm）。原 Kernel 两大职责被 Brain 层完全吸收：（1）任务调度协调 → PrefrontalCortex 主脑（铁律 A：唯一通路）；（2）LLM 执行器封装 · 上下文装配 → BrainBase（含 msai）+ ExternalMotorCortex / ClaudeCodeMotorCortex · Brain 内部装配机制。

**职责（本轮明确）**：

1. **AgentDescription**——CBIM 独有的 agent 类型描述 schema，以 C# 类实例化（不是 frontmatter yaml）。本轮增 Memory 配置字段（`MemoryFactory` 或 `MemoryConfig`），与原有 `Skills` / `SystemTools` / `McpList` 并列。
2. **装配胶水（OpenInstance）**——读 AgentDescription → 用 Microsoft `AIAgentBuilder` 装配 `AIAgent`；**本轮增「Memory 绑定」步骤**：调用 `MemoryFactory` 生成 `IMemoryService` 实例，绑定到 Agent 实例。
3. **Session 写侧**——`AppendSessionEvent(instanceId, ev)`；不变。唯一调用方本轮随 Kernel 删除变为 Brain.MotorCortex / Brain 内部装配机制（原 CbimTaskExecutor 职责下沉）。
4. **多脑区装配（本轮耳区项重构后迁移到 `Agent/Brain/`）**——一个 AgentInstance 装配多个 `BrainBase`（PrefrontalCortex + ParietalLobe + Hippocampus + N 个 MotorCortex），这些脑区**共享**该 Agent 的 IMemoryService / Tool / MCP / Skill 资源池。

**外部 AI 引擎装配**（Claude Code / Cursor / Codex 等）本轮重调：**不再为与本模块平级的 `ExternalAdapter` 顶层模块**（原 `ExternalAdapter/` 上轮废弃·目录待物理删除），而是以 `Agent/Brain/MotorCortex` 家族的 **`ExternalMotorCortex` 子类**（首发实现：`ClaudeCodeMotorCortex`）的形式嵌入单个 Agent 的 Brain 内部。依据详见 `Agent/Brain/.dna/module.md`：外部 AI 本质是「会干活的肌肉」（无主脑调度 / 无 Hippocampus 记忆训练 / 不做架构设计），只在皮层适配才符合本质。

## 与 v2 三层模型的关键关系

- **Agent 层 ⊥ Workspace 层**——AgentSystem 不引用任何 Workspace 模块。Agent 进入某 Workspace 模块执行任务时，由 **Agent/Brain 内部装配机制**（本轮 Kernel 删除后，原 Kernel.ContextProvider 职责下沉到 Brain 内部）把 Workspace 模块的 Skill / MCP / Metadata 注入到 Agent 的运行上下文；这是 task 期组合，不是编译期依赖。
- **AgentSystem 依赖基建层**——引用 `CBIM.Tools` / `CBIM.Skills` / `CBIM.Mcp` / `CBIM.Memory.IMemoryService` / `CBIM.Storage`，不反向。**不引用 Kernel**（已不存在）。
- **类型契约共享 / 实例集合独立**——AgentDescription 持 `IReadOnlyList<ToolDescriptor>` / `IReadOnlyList<SkillDescriptor>` / `IReadOnlyList<McpDescriptor>` 三字段是 per-Agent 独立的实例集合；同抽象类型由基建层提供。

## CBIM 核心对偶中的位置

AgentSystem 与 Workspace 是一对正交服务层：

| 维度 | 本服务层 | 对偶服务层 |
|------|---------|----------|
| **能力（Capability）** | **AgentSystem**——管理「能力个体」 | — |
| **业务（Business）** | — | **Workspace**——管理「业务工作区」 |

二者**结构对称**：都以 `Description`（类型描述）+ `Instance`（实例运行态）二元结构组织；都直接依赖 Storage；都不互相依赖；跨维度协同由 **Agent/Brain 内部 PrefrontalCortex 主脑**在 Task 期组合（本轮 Kernel 删除后，原 Kernel.FlowGraph 职责下沉为主脑内部 LLM + AIFunction 闭环，跨脑区协作严格遵循铁律 A：唯一通路）。

**唯一的跨维度共享点 = `McpDescriptor`**——同一份抽象同时被能力维度的 `AgentDescription.McpList` 与业务维度的 `ModuleDescription.McpList` 引用。这是 `Mcp/` 子模块物理位于 AgentSystem 下但对 Workspace 公开 `McpDescriptor` 抽象的**唯一理由**（其余子模块均不被 Workspace 引用）。

## 维度归属（上一轮重大变动）

上一轮设计把「工具能力声明权」放在 `ModuleDescription.standard_tools`——**错**。本轮修正：

| 维度 | 内容 | 归属 |
|------|------|------|
| **能力（Agent）** | **工具 + skill + 专精领域** | AgentDescription（本模块） |
| **业务（Module）** | 工作流程 + 领域知识 | ModuleDescription（Workspace） |

**修正后的维度铁律**：工具属于能力，流程属于业务。

- 「这个 agent 能不能读文件 / 能不能联网 / 能不能调 git CLI」——是 agent 自身的能力构成，写在 `AgentDescription.SystemTools` + `Skills` + `McpList`。
- 「这个 module 在做什么业务流程 / 涉及什么领域知识」——是 module 自身的业务声明，写在 `ModuleDescription` body。
- 工具的「动态注入」属性依然成立：通过「task 选哪个 agent」间接动态（不同任务选不同 agent，agent 自带不同工具集），而非按 module 动态。

## 本轮重要变动：三大扩展抽象平级化

上一轮三大扩展抽象的子模块化程度不一致：

- `StandardTools/` 已是子模块（含 Families / Sandbox / Service）。
- MCP 是独立 `McpAdapter/` 子模块（以 Adapter 装配胶水为主）。
- Skill 完全裸露在 `AgentSystem/Skill.cs`（命名空间 `CBIM.AgentSystem`）。

本轮裁决：**三大扩展抽象平级三足鼎立，都是 AgentSystem leaf 子模块**，同为 `agent 能多会一手` 的扩展通道、同装配点（OpenInstance）、同生命周期（绑 AIAgent 实例）、同被 AgentDescription 声明侧引用。物理动作（已随代码落地）：

- `AgentSystem/Skill.cs` → `AgentSystem/Skills/Skill.cs`，namespace = `CBIM.Skills`。
- 原 `AgentSystem/McpAdapter/` 移除；新建 `AgentSystem/Mcp/`，namespace = `CBIM.Mcp`。`McpDescriptor` 升为 abstract 基类 + `StdioMcpDescriptor` / `HttpMcpDescriptor` 两子类 + `McpTransportKind` 枚举。
- `AgentDescription.cs` using 调为 `CBIM.Skills` + `CBIM.Mcp`；SystemTool 仍位于父命名空间 `CBIM.AgentSystem`（本轮代码现状，后续如需才平移到 `CBIM.Tools.Standard`）。

## Children

AgentSystem 本身不再含「能力维度三大扩展抽象」子模块——Tool / Skill / Mcp 已交由基建层顶层模块负责（`CBIM/Tools/` / `CBIM/Skills/` / `CBIM/Mcp/`）。

**本轮调整 (Brain 重构 + Kernel 中间层析出)**：

| 子模块 | 一句话职责 | 状态 |
|--------|------------|------|
| `Brain/` | Agent 内部脑区组装层——一份 .dna 通览全局；使用大脑解剖学专业名（PrefrontalCortex / ParietalLobe / Hippocampus / MotorCortex）；Native/External 仅在 MotorCortex 下分支 | spec |
| `Kernel/` | Agent 内部运行内核（神经系统层）——**本轮新增中间层**，从 Brain 析出机制。两子模块：`Neuron/`（神经元·AIAgent 封装抽象）与 `Synapse/`（突触·脑区间派发协议）。Brain 仅消费本层抽象，不感知装配 / 跨脑区机制细节 | spec |

### 三层模型表达（含 Kernel 中间层）

```
Agent 层服务门面 (AgentSystem · 本模块)
   ↓ OpenInstance 装配期实例化
Brain 层 (脑区高级职能)
   ├── PrefrontalCortex (主脑 · Channel.SendAsync 投递目标)
   ├── ParietalLobe (架构脑)
   ├── Hippocampus (记忆学习脑)
   └── MotorCortex 家族 (Native + External·ClaudeCode)
   ↓ 依赖
Kernel 层 (神经系统机制)
   ├── Neuron/ (神经元 · INeuron + MsaiNeuron + ExternalEngineNeuron + NeuronFactory)
   └── Synapse/ (突触 · SynapseToolFactory + IPrefrontalCallback + IBrainRegistry)
   ↓ 依赖
基建层 (Tool / Skill / Mcp / IMemoryService / Storage) + Microsoft.Agents.AI / Microsoft.Extensions.AI
```

**Brain → Kernel 依赖单向不反向**——Kernel 不感知任何具体脑区类型，只暴露通用的 `INeuron` / `SynapseToolFactory` 给 Brain 消费。Brain 是「策略层」，Kernel 是「机制层」——策略可以变（脑区分类可演化），机制保持稳定。

**Brain/ 下本轮不再含 leaf 子模块**——上一轮的 7 个 leaf（Base / Master / Architect / MemoryLearning / Motor (parent) / Motor/Default / Motor/ClaudeCode）本轮全部被删除，所有脑区契约合并入 `Brain/.dna/module.md` 通览全局。原因：脑区结构是紧耦合的有机体，不是 7 个独立子系统。

**Kernel/ 下两个 leaf 互不引用**：Neuron 不知道有 Synapse，Synapse 不知道有 Neuron。它们各自被 Brain 层装配点（PrefrontalCortex / 其他脑区构造器）独立调用。

**职责重新分配（上一轮 leaf → 本轮脑区 + Kernel 机制）**：

- Brain/Master → **Brain/PrefrontalCortex**（前额叶 · 主脑）
- Brain/Architect → **Brain/ParietalLobe**（顶叶 · 架构脑）
- Brain/MemoryLearning → **Brain/Hippocampus**（海马体 · 记忆学习）
- Brain/Motor + Default + ClaudeCode → **Brain/MotorCortex + NativeMotorCortex + ExternalMotorCortex · ClaudeCodeMotorCortex**
- Brain/Base 中「msai 装配」责任 → **Kernel/Neuron/MsaiNeuron**
- Brain/Master 中「__brain_call_* 生成」责任 → **Kernel/Synapse/SynapseToolFactory**
- Brain/Base 中「IPrefrontalCallback / IBrainRegistry」接口 → **Kernel/Synapse/**
- HRBrain / AuditorBrain 候选 → **Cerebellum（小脑）/ AnteriorCingulateCortex（前扣带回 · ACC）预留，本轮不实装**

上一轮 「思维对象集合」 预留 (`AgentInstance.AIAgents: IReadOnlyList<AIAgent>`) 本轮以 `Brains: IReadOnlyList<BrainBase>` 实现；Brain parent 负责设计原则与编织铁律，本服务门面负责 OpenInstance 装配胶水中「为多脑区产生 N 个 BrainBase + 调 NeuronFactory 产出 INeuron + 调 SynapseToolFactory 为主脑准备 __brain_call_* AITool + 启动 Memory 桥 MCP」部分。

上一轮「能力维度三大扩展抽象三足鼎立」描述在本轮三层模型下被重表述为「基建层四件套抽象（Tool / Skill / Mcp / Memory）」——同一集抽象、不同层级划分。Memory 作为第四件加入基建集（之前作为三大服务系统之一独立存在）。

## 六脑区编织对本服务门面的增量变更（本轮）

**本节标题保留以便历史可查；下文内容已随 `Agent/Brain/` 本轮重构（合并方案 + 大脑解剖学命名）同步更新**。脑区从「分散 leaf」重走为「一份 .dna 通览全局 + 4 脑初始集」；名字换为大脑解剖学专业名；BrainBase 已含 msai 装配；Native/External 仅在 MotorCortex 下分支。

## Mermaid

```mermaid
flowchart TD
    AS["AgentSystem\n(父服务 · OpenInstance 装配胶水)"]
    AD["AgentDescription\n(Id+Name+Soul+Identity+\nSkills+SystemTools+McpList)"]

    subgraph SUBS ["三大扩展抽象子模块（平级三足鼎立）"]
        SK["Skills/\nSkill"]
        ST["StandardTools/\nSystemTool + AIFunction 家族"]
        MC["Mcp/\nMcpDescriptor (abstract)\n+ Stdio/Http 子类\n+ McpTransportKind 枚举"]
    end

    AI["Microsoft.Agents.AI\n(AIAgent / Builder / Session)"]
    EX["Microsoft.Extensions.AI\n(AIFunction)"]
    MSMCP["Microsoft.Agents.AI.Mcp\n(MCP client)"]
    WS["Workspace.ModuleDescription\n(McpList: McpDescriptor[])"]

    AS --> AD
    AD -- references --> SK
    AD -- references --> ST
    AD -- references --> MC
    WS -. 跨维度共享 .-> MC

    AS -- 读 Skills --> SK
    AS -- 读 SystemTools --> ST
    AS -- 读 McpList --> MC

    AS -. 装配 AIAgent .-> AI
    ST -. AIFunctionFactory .-> EX
    MC -. Microsoft.Agents.AI.Mcp .-> MSMCP

    classDef sub fill:#fffbe6;
    class SK,ST,MC sub;
```

依赖单向：AgentSystem → 三子模块 → Microsoft 包；Workspace → AgentSystem.Mcp（跨维度共享抽象，唯一反向边不存在——Mcp 不反向引 Workspace）。

## Contract Surface

```csharp
namespace CBIM.AgentSystem;

using Microsoft.Agents.AI;
using CBIM.Skills;
using CBIM.Tools;
using CBIM.Mcp;
using CBIM.Memory;
using CBIM.AgentSystem.Brain;

public sealed class AgentSystemService
{
    // AgentDescription（类型）—— 读侧
    IReadOnlyList<AgentDescription> ListDescriptions();
    AgentDescription? GetDescription(string name);
    IReadOnlyList<AgentDescription> MatchDescriptions(string capability, int topK);

    // AgentInstance —— 装配 / 实例查询
    AgentInstance OpenInstance(string descriptionName, OpenInstanceOptions? options = null);
    void CloseInstance(string instanceId);
    AgentInstance? GetInstance(string instanceId);
    IReadOnlyList<AgentInstance> ListInstances();

    // Session —— 写侧 + 读侧
    void AppendSessionEvent(string instanceId, SessionEvent ev);
    IReadOnlyList<SessionEvent> ReadSessionTail(string instanceId, int n);

    AgentStats Stats();
}

/// AgentDescription 为 C# 不可变记录类（以代码为准，不是 frontmatter）
public sealed class AgentDescription
{
    public string Id { get; }
    public string Name { get; }
    public string Soul { get; }
    public string Identity { get; }
    public IReadOnlyList<SkillDescriptor> Skills { get; }
    public IReadOnlyList<ToolDescriptor> SystemTools { get; }
    public IReadOnlyList<McpDescriptor> McpList { get; }

    // Memory 配置工厂
    // null 时默认用 FileMemoryBackend（基建层默认实现）。
    public Func<string, IMemoryService>? MemoryFactory { get; }

    // 脑区编织蓝图 (上中轮新增 · 本轮保留)。
    // null → 单脑区 Agent（向下兼容）
    // non-null → 多脑区 Agent（默认 4 脑）
    public BrainConfig? BrainConfig { get; }
}

/// AgentInstance —— 运行期实例
/// 本轮重要变动：从「持 N 个 AIAgent」重定义为「持 N 个 BrainBase + 1 个 PrefrontalCortex 句柄」。
public sealed class AgentInstance : IAsyncDisposable
{
    public string InstanceId { get; }
    public string DescriptionId { get; }

    // 脑区集合（本轮字段重定义）——一个 Agent 含多个 BrainBase
    public IReadOnlyList<BrainBase> Brains { get; }

    // 主脑句柄（本轮字段重命名）：上中轮 instance.Master → 本轮 instance.Prefrontal
    // 类型固定为 PrefrontalCortex 具体类。
    public PrefrontalCortex Prefrontal { get; }

    // Dream 裂变产出的新脑区动态注册点
    public IBrainRegistry BrainRegistry { get; }

    // Memory 实例（per-Agent）——该 Agent 的记忆资源池，上面多个 BrainBase 共享访问
    public IMemoryService MemoryService { get; }

    // MCP server 句柄绑生命周期
    public IReadOnlyList<IAsyncDisposable> McpHandles { get; }

    public AgentSession Session { get; }

    // 释放顺序：MotorCortex 类 → 其他脑区 → Prefrontal → Memory → McpHandles → Session
    public ValueTask DisposeAsync();
}

public sealed record OpenInstanceOptions(
    IChatClient? ChatClientOverride = null,
    bool? EnableFunctionInvocation = null,
    IReadOnlyList<Microsoft.Extensions.AI.AIFunction>? Tools = null,
    IReadOnlyList<Microsoft.Extensions.AI.AIContextProvider>? Providers = null,
    string? TaskWhere = null,                              // MCP server 启动 workspaceRoot（task.Where）
    Func<string, IMemoryService>? MemoryFactoryOverride = null);  // 覆盖 AgentDescription 中的默认工厂
```

**SessionEvent**：本模块定义薄基类 + 几个子类（UserInput / LlmCall / ToolInvocation / Output / Error），落盘策略可走 Microsoft AgentSession 或本模块直接 jsonl。本轮初期实现可直接 jsonl，待 Microsoft AgentSession API 稳定后切换为 host。

**OpenInstanceOptions.TaskWhere**：MCP server 启动需 workspaceRoot——该值固定取 `task.Where`，由调用方（Channel / Agent/Brain 内部装配机制；原 CbimTaskExecutor 路径本轮随 Kernel 物理删除而废）透传。不允许 agent / OpenInstance 内部猜。若 `McpList` 非空且未传 `TaskWhere` → throw `InvalidOperationException`。

**OpenInstanceOptions.MemoryFactoryOverride**：覆盖 AgentDescription 中的 MemoryFactory。优先级：Override > Description.MemoryFactory > 默认 FileMemoryBackend。这为 Composition Root 在测试 / 开发 / 生产环境不同后端提供了顶层控制。

## Service-Layer Extension Model

OpenInstance 是 **CBIM 装配能力 → Microsoft AIAgent 实例**的唯一胶水点。集中：

- 从 AgentDescription 取 `Soul` / `Identity` / `Name` → `ChatClientAgentOptions` (Instructions / Description / Name)
- 调 `AIAgentBuilder` 装配 `IChatClient`
- 可选 `FunctionInvokingChatClient` 包装
- 挂 Microsoft.Extensions.AI 生态 `AIFunction`（Agent 工具能力）
- 装配默认 Compaction 策略
- **本轮新增**：生成 `IMemoryService` 实例绑定到 AgentInstance

未来新增 Provider / 换 Compaction / 挂新 AIFunction 类 / 换 Memory 后端——只动这一处。

### 四源能力装配总序（本轮从三源扩为四源：增 Memory）

OpenInstance 内部按四源顺序装配，最后合并传给 `AIAgentBuilder`：

```
OpenInstance(descriptionName, options):
  desc = GetDescription(descriptionName)
  workspaceRoot = options.TaskWhere   // 必传当 desc.McpList 非空

  # 源 0：Memory（本轮新增 · per-Agent IMemoryService 实例）
  memoryFactory = options.MemoryFactoryOverride
                  ?? desc.MemoryFactory
                  ?? (root => new FileMemoryBackend(storage, $"memory/{instanceId}"));
  memoryService = memoryFactory(workspaceRoot);

  # 源 1：Skills（语义描述注入）
  skillContent = Skills.Render(desc.Skills)   // AgentSkillsProvider 未来落地
  prompt = desc.Soul + skillContent

  # 源 2：SystemTools（进程内 AIFunction）
  sandbox = BuildSandbox(projectRoot, instanceRunDir)
  stdFns = StandardToolsService.CreateFamilies(desc.SystemTools, sandbox)

  # 源 3：McpList（启 server / 进远端 + 包 AIFunction）
  mcpHandles = []
  foreach descriptor in desc.McpList:
      try:
          handle = await StartMcpAsync(descriptor, workspaceRoot)
          mcpHandles.Add(handle)
      catch e:
          log.warn("MCP start failed: {descriptor.Id}", e)   # 优雅降级
  mcpFns = mcpHandles.SelectMany(h => h.Functions).ToList()

  # 源 4（外插）：options.Tools
  extraFns = options.Tools ?? []

  allFns = stdFns.Concat(mcpFns).Concat(extraFns).ToList()
  aiAgent = AIAgentBuilder.Create(...)
      .UseFunctionInvocation()
      .UseTools(allFns)
      .Build()

  # 本轮新视角：多脑区共享资源
  # 初期实现只装一个 AIAgent；后期如需 Reasoner+Critic+Summarizer 多脑区从同 desc 多次装配，所有 AIAgent 共享
  # 同一 memoryService / mcpHandles / sandbox
  instance = new AgentInstance(
      instanceId, descriptionId,
      aiAgents: [aiAgent],
      memoryService: memoryService,
      mcpHandles: mcpHandles,
      session: aiAgent.CreateSession());

  RegisterInstance(instance)
  return instance

CloseInstance(instanceId):
  inst = LookupInstance(instanceId)
  foreach handle in inst.McpHandles:
      await handle.DisposeAsync()                    # 断 IPC + Kill server 进程 / 断 HTTP
  await inst.MemoryService.DisposeAsync()            # 本轮新增：释放 Memory 后端（如 Pinecone client 需关）
  UnregisterInstance(instanceId)
```

### 四源对齐表

| 来源 | 声明字段 | 装配胶水 | 生命周期释放 |
|------|---------|---------|------------|
| **Memory**（本轮新增） | `desc.MemoryFactory` / `options.MemoryFactoryOverride` | 调工厂生成 `IMemoryService` 实例绑 AgentInstance | **CloseInstance 期 `MemoryService.DisposeAsync` 显式释放**（仅第三方后端需要；FileMemoryBackend 默认空实现） |
| Skills | `desc.Skills` | AgentSkillsProvider（未来落地）注入 LLM 上下文 | 随 AIAgent GC |
| SystemTools | `desc.SystemTools` | `StandardToolsService.CreateFamilies` | 随 AIAgent GC |
| MCP server | `desc.McpList` | `Microsoft.Agents.AI.Mcp` client.StartAsync | **CloseInstance 期 `handle.DisposeAsync` 显式释放** |

**Memory + MCP 是唯二需显式释放的源**——前者可能持外部连接（Pinecone client），后者持外部 server 进程 / 连接。不释放 = 资源泄漏。CloseInstance 接口存在的最强动机是二者。


## 代码与本轮描述的名词对齐（实现备注）

本轮描述用 `AgentSystemService` / `AgentInstance` / `OpenInstance` 等名词表达架构意图。现有代码中的具体类名保持不变：

| 描述名 | 代码名 | 说明 |
|--------|--------|------|
| `AgentSystemService` | `AgentSystem` | Agent 层服务门面（`namespace CBIM.AgentSystem`） |
| `AgentInstance` | `Agent` | 运行期实例（谁 + 状态） |
| `OpenInstance` | `OpenInstanceAsync` | Microsoft AIAgent 装配是异步的，代码加 Async 后缀 |
| `CloseInstance` | `CloseInstanceAsync` | 同上 |
| `MemoryService` （实例字段） | `Memory` | Agent.cs 本轮新增实例字段采用短名 `Memory`，类型 = `CBIM.Memory.IMemoryService` |

下切片只动代码、不动描述名词（描述侧习惯名保留其三层模型可读性）。

### 本轮 OpenInstance API 扩展形态

保留现有重载 `OpenInstanceAsync(string descriptionId, string activatedByTaskId = null)`（默认装配 FileMemoryBackend），**额外引入** `OpenInstanceOptions` 重载供高级召带插 MemoryFactory / TaskWhere：

```csharp
public sealed record OpenInstanceOptions
{
    public string ActivatedByTaskId { get; init; }
    public string TaskWhere { get; init; }                                  // workspaceRoot for MCP (本轮未启用 MCP 可为 null)
    public Func<string, IMemoryService> MemoryFactoryOverride { get; init; } // null 时 fallback Description.MemoryFactory 再 fallback 默认 FileMemoryBackend
}

public Task<Agent> OpenInstanceAsync(string descriptionId, OpenInstanceOptions options);
```

优先级：`options.MemoryFactoryOverride` > `desc.MemoryFactory` > 默认 `instanceId => new FileMemoryBackend(storage, $"memory/{instanceId}")`。

**默认工厂需 storage 注入**——现有 `AgentSystem(IEnumerable<AgentDescription>, IChatClient)` 重载未提供 `FileBackend`，此时若未显式传入 `MemoryFactoryOverride` / `Description.MemoryFactory`——下切片 programmer 应 抛 `InvalidOperationException`（迬迫 Composition Root 明确选择），而不是 silent fallback 到一个空实现。

### Memory 实例字段出口点

`Agent` 类（运行期实例）增实例字段：

```csharp
public IMemoryService Memory { get; }   // 接口字段，不跳出抽象
```

`Agent.DisposeAsync` 释放顺序调为：McpHandles → `Memory.DisposeAsync()` → Session。`Memory` 为 null 时跳过（应不出现但防护性判空）。

## Dependencies

- `CBIM.Storage`——AgentDescription / AgentInstance / Session 元数据 IO。
- **`CBIM.Memory`**（本轮新增）——`IMemoryService` 接口 + `MemoryEntry` 类型 + `FileMemoryBackend` 默认实现。per-Agent 实例绑定。
- `Microsoft.Agents.AI`——`AIAgent` / `AIAgentBuilder` / `ChatClientAgent` / `AgentSession`。
- `Microsoft.Extensions.AI`——`IChatClient` / `AIFunction` / `AIContextProvider`。
- `Microsoft.Agents.AI.Mcp`——MCP client（本模块在 OpenInstance 内使用。接口抽象仅使用 `CBIM.Mcp.McpDescriptor`）。
- **`CBIM.Skills`**（基建）——`SkillDescriptor` 类型。
- **`CBIM.Tools`**（基建）——`ToolDescriptor` 类型 + `Tools/Standard.StandardToolsService.CreateFamilies` 装配内置工具。
- **`CBIM.Mcp`**（基建）——`McpDescriptor` / `McpTransportKind` / `StdioMcpDescriptor` / `HttpMcpDescriptor`。
- **不依赖** Workspace——Agent 层服务层只依赖基建层。Workspace 是平级层（v2 三层模型下），二者不相互依赖。
- **不存在 Kernel 依赖**（原 `CBIM.Kernel` 顶层模块本轮随代码 / .meta / .dna 一同 git rm 物理删除）——原 Kernel 两大职责被吸收入 Agent/Brain：任务调度协调 → PrefrontalCortex（铁律 A）；LLM 执行器封装 · 上下文装配 → BrainBase（含 msai）+ ExternalMotorCortex / ClaudeCodeMotorCortex。

依赖方向：Agent 层服务层 → 基建层（Skills / Tools / Mcp / Memory / Storage） → Microsoft 包，无反向边。

## Agent 裂变规则（铁律）

**不做「全能 agent」，保持专精**。Agent 的工具广度 + skill 广度 + 专精领域跨度共同决定其复杂度上限。

### 裂变触发阈值（任一命中即裂）

| 维度 | 阈值 | 说明 |
|------|------|------|
| **`SystemTools` 家族数** | > 4 | 超过 4 个 AIFunction 家族（Files + Search + Web + Bash + ……）= 工具栏过宽 |
| **`McpList` server 数** | > 3 | 超过 3 个 MCP server = 跨业务面太杂，且每个 server 都是独立外部进程（Stdio），启动成本高 |
| **`Skills` 数** | > 8 | 单 agent 关联超过 8 个 skill = 心智超载 |
| **专精领域跨度** | 跨 2+ 主领域 | 例：Unity + Backend + Blender 三栈混挂——拒绝 |
| **Soul 长度** | > 3000 token | 提示词膨胀通常意味着责任膨胀 |

命中其一 → 立即触发裂变审议（HR 与 architect 协商）。

### 裂变范式

- **按专精领域裂**——`ProgrammerAgent` 一个吃全宇宙 → `UnityProgrammerAgent` / `BlenderArtistAgent` / `BackendProgrammerAgent` 各管一摊。
- **按工具家族裂**——若不同任务需要的工具集互斥（数据科学 vs 游戏开发），按工具集分群裂。
- **按 MCP server 裂**——不同 MCP server 面向不同业务生态（unity-mcp vs blender-mcp vs db-mcp）时，裂为该业务专精 agent。
- **按调用频度裂**——使用频繁但责任窄的部分独立成轻量 agent（auditor / hr / architect 已是此范式）。

### 通用 vs 专精 Agent

| 类别 | 角色 | 典型规模 |
|------|------|---------|
| **通用** | coordinator / hr / architect / auditor——协调与治理角色 | SystemTools ≤ 2、Skills ≤ 4、McpList ≤ 1 |
| **专精** | unity-programmer / blender-artist / backend-programmer / writer / sound-engineer | SystemTools ≤ 4、Skills ≤ 8、McpList ≤ 3，且专精单领域聚焦 |

通用 agent 保持轻——它们的价值是路由 / 决策 / 文档，不是执行重活；专精 agent 允许工具栏更宽，但**单领域聚焦** + 严守上限。

### HR 接管裂变实施

裂变审议由 HR 主持（HR 的 hr_agents skill 已含 agent 裂变 / 合并工作流）；本模块只提供「触发阈值」铁律。

## 铁律

- **Session 写入唯一调用者 = Agent/Brain**——本轮 Kernel 删除后，原「业务 Workflow 的 CbimTaskExecutor」职责下沉到 Brain.MotorCortex / Brain 内部装配机制。其他模块（包括 Channel）不准直调 AppendSessionEvent。
- **OpenInstance 是装配胶水唯一入口**——Channel / 业务代码不直接 new ChatClientAgent。四源工具（Memory + Skills + SystemTools + McpList）都在这里装配。
- **不 host 短期会话**——AgentThread / ChatHistoryProvider 由 Microsoft 内部管，CBIM 不感知。
- **不重写 AIAgent**——AgentInstance 仅是 CBIM 元数据壳，运行体永远是 Microsoft `AIAgent`。
- **工具归能力，流程归业务**——`AgentDescription.Skills` / `SystemTools` / `McpList` 是能力声明的唯一地，`ModuleDescription` 不持任何能力字段。
- **三子模块平级不交叉**——Skills / StandardTools / Mcp 互不引用；并列被 AgentDescription 引用；各自在 OpenInstance 装配口发。
- **MCP server 连接目标必须 = task.Where**——能力归能力，目标归业务；workspaceRoot 由 OpenInstance 从 `options.TaskWhere` 注入，不可被 agent / 调用方覆盖。
- **MCP server 生命周期严格绑 AgentInstance**——OpenInstance 启 / CloseInstance 必 DisposeAsync。异常路径也走，否则进程泄漏。
- **Agent 必须专精**——`SystemTools` / `Skills` / `McpList` / 专精领域跨度 / `Soul` 长度任一维度超阈值，HR 立即裂变。
- **`McpDescriptor` 是唯一跨维度共享抽象**——`AgentDescription.McpList` 与 `ModuleDescription.McpList` 同类型；共用不代表跨维度耦合——是同一「外部端点」抽象被两个维度各自声明使用。
- **外部 AI 引擎接入不是独立平级模块，是 Agent 内部脑区的一个子类**——原「与 AgentSystem 平级的 ExternalAdapter 顶层模块」上轮废弃（commit ea2c876 脑区架构落地后）。外部 AI 引擎（Claude Code / Cursor / Codex）以 `Agent/Brain/MotorCortex` 家族下的 `ExternalMotorCortex` 子类（首发：`ClaudeCodeMotorCortex`）的形式存在。本服务门面仍然不直接感知具体外部引擎类型——装配由 BrainConfig + IBrainRegistry 完成，外部引擎的差异封装在 `Agent/Brain/` 内部。
- **不依赖 Kernel**——原 `CBIM.Kernel` 顶层模块（FlowGraph / TaskScheduler / ContextProviders）本轮随源码 / .meta / .dna 一同 git rm 物理删除。原职责被吸收：（1）调度协调 → Brain.PrefrontalCortex（铁律 A：唯一通路）；（2）LLM 执行器封装 · 上下文装配 → BrainBase（含 msai）+ ExternalMotorCortex / ClaudeCodeMotorCortex · Brain 内部装配机制。

### 六脑区编织铁律（本轮新增，完整定义见 `Agent/Brain/.dna/module.md`）

**本节标题保留以便历史可查**。本轮 Brain 重构后，脑区从「分散 leaf」收敛为「一份 .dna 通览全局 + 4 脑初始集」，采用大脑解剖学专业名；BrainBase 含 msai 装配；Native/External 仅在 MotorCortex 下分支。最新铁律完整描述在 `Agent/Brain/.dna/module.md`。本服务门面需从外部看到的铁律要点：

- **主脑唯一调度**——只有 PrefrontalCortex 可调其他脑区；其他脑区互不通讯。跨脑区数据流必须经主脑中转。
- **副作用唯一出口 = MotorCortex 家族**——所有「改变世界状态」动作（文件写 / MCP / HTTP / Workspace 变动 / .dna 写入）走 MotorCortex (NativeMotorCortex / ExternalMotorCortex) 任一子类。例外：Hippocampus 可直接 IMemoryService.Write；所有脑区都可调 IMemoryService.Query（只读不是动作）。
- **共享一份 Memory + 一份 task.Where**——标准脑区直接注入 BrainBase.Memory；ExternalMotorCortex 通过 MemoryShareMode 桥 (默认 McpServer) 共享访问同一实例。
- **主脑类型固定 PrefrontalCortex**——BrainConfig 构造期验证必须有且仅有一个 `StandardBrainDescriptor.IsPrefrontal = true`。主脑不存在 External 变体（类型系统层面杜绝）。
- **至少一个 MotorCortex**——BrainConfig 验证至少一个脑区 `BrainId` 以 `"motor-cortex."` 开头。无 MotorCortex 意味着 Agent 无法执行任何动作。
- **默认 4 脑装载**——`BrainConfig.Default(agentName)` 产出 [PrefrontalCortex, ParietalLobe, Hippocampus, NativeMotorCortex] 军定装载；`BrainConfig.Custom(...).WithClaudeCode(...)` 可额外加入 ClaudeCodeMotorCortex。
- **裂变仅限 MotorCortex + Workspace Module**——Dream 裂变出的新东西仅限两类：MotorCortex (能力侧) 与 Workspace Module (知识侧)。不裂主脑 / 架构脑 / Hippocampus 本身（避免递归）。
- **Pool / Cap=4 机制本轮废除**——多 MotorCortex 实例由 Dream 裂变动态产生 → IBrainRegistry 注册。
- **Native/External 仅在 MotorCortex 下分支**——其他脑区只能 Native。原因：外部 AI 工具本质是「会干活的肌肉」，没有主脑调度 / 记忆训练 / 架构设计能力，只在皮层适配符合本质。

## Origin Context

上一轮裁决：
1. 删 `OpenInstanceOptions.ActiveModulePaths` 字段；
2. 删对 `CBIM.Workspace` / `CBIM.Workspace.StandardTools` 的依赖；
3. 新增 `AgentDescription.tools` + `agent_extension_clis` 字段；
4. StandardTools 子模块物理迁入 AgentSystem 之下；
5. 新增 Agent 裂变规则——防止「全能 agent」误区在能力维度复发。

上轮增量（MCP 集成）：能力维度的「工具来源」上上轮识别了两类（StandardTools / agent_extension_clis），上轮补第三类：外部 MCP server。新增 `mcp_servers` 字段、`OpenInstanceOptions.TaskWhere` 字段、`AgentSystem/McpAdapter/` 子模块；裂变阈值表增 `mcp_servers 数 > 3` 一行。

**上一轮重大调整**（三大扩展抽象平级子模块化 · 代码已落地）：

1. **AgentDescription 以 C# 类实例化**（不是 frontmatter yaml 字串）：Id / Name / Soul / Identity + `Skills: List<Skill>` + `SystemTools: List<SystemTool>` + `McpList: List<McpDescriptor>` 三能力字段。代替上轮的字串名列表调用。
2. **`mcp_servers: [name]` 名字串 + IMcpRegistry 二级查棚取消**——`AgentDescription.McpList` 直接持 `McpDescriptor` 实例（`Stdio` 或 `Http`）。理由：Unity 项目内 cfg 与 agent 共存，二级表反增同步成本。
3. **原 `McpAdapter/` 子模块 → `Mcp/`**：名字与 Skills / StandardTools 对齐（都是「该抽象的家」）。
4. **`McpDescriptor` record → abstract 基类 + 两子类 + `McpTransportKind` 枚举**：Stdio / Http 两形态明确区分，形态识别从「字段是否存在」升为「类型判别」。
5. **`Skill` 从裸露在 AgentSystem/ 迁到 Skills/ 子模块**，namespace 独立。
6. **跨维度共享**：`Workspace.ModuleDescription.McpList: List<McpDescriptor>` 新增，同 `AgentDescription.McpList` 类型；`ModuleDna` 退为纯知识载体（不再夹带 MCP 协议信息）。
7. **McpServerAdapter / McpServerHandle 本轮未随代码落地**：装配侧（OpenInstance / 业务 Workflow）直接调 Microsoft.Agents.AI.Mcp client。后续如出现重复胶水再抽取。

**本轮增量（装配家平级化 · ExternalAdapter 锡兴）**：

8. **新增平级模块 `CBIM.ExternalAdapter`**（task-1 产出）接管外部 Agent 引擎的装配（Claude Code / Cursor / Codex 等）。本模块当夜同步明确身份：“内置 Microsoft AIAgent 装配家”，不拽上外部引擎责。Positioning / 铁律 / Emergent Insights 同步锁定“互不感知、互不依赖、由 Kernel/FlowGraph 以 task.Who 路由」这套平级装配家范式。本模块 Dependencies / Mermaid / Contract Surface **不引用 ExternalAdapter**——这本身是上述铁律的体现。

**本轮（v2 三层模型 + Memory 接口抽取）**：

9. **顶层心智收敛：6 层 → 3 层**——原「引擎层 / 能力层 / 基座层 / 扩展层」划分是源码组织精准分类，但顶层心智负载过高。本轮收敛为「基建 / Agent / Workspace」三层：AgentSystem 明确位于 Agent 层，与 ExternalAdapter / Kernel / Channel 同属该层。
10. **AgentSystem 语义重命名（物理未动）**——本轮明确「AgentSystem = Agent 层服务层门面」，可类比 PersonnelService。物理目录名 `AgentSystem/` 本轮保留（代码迁移成本高）；下切片视代码状态决定是否同步改为 `Agent/`。详见根 module.md 「AgentSystem → Agent 重命名决策」节。
11. **Memory 接口抽取 + per-Agent 实例**（本轮重要增量）——Memory 从「全局服务」抽为 `IMemoryService` 接口 + `FileMemoryBackend` 默认实现；AgentDescription 增 `MemoryFactory` 字段；AgentInstance 持 `MemoryService: IMemoryService`；OpenInstance 装配从「三源」扩为「四源（Memory + Skills + SystemTools + McpList）」；CloseInstance 增 `MemoryService.DisposeAsync` 释放。动机：接入 Pinecone / Weaviate / VectorStore 等第三方记忆后端；「一个人一份记忆」认知模型落地。
12. **多脑区视角（本轮新增预留）**——`AgentInstance` 增 `AIAgents: IReadOnlyList<AIAgent>` 字段预留（初期实现只装一个 AIAgent）。未来可从同 desc 装配多个 AIAgent（Reasoner + Critic + Summarizer），多脑区**共享**同一 `MemoryService` / `McpHandles` / Tool 集。这是「复合 Agent 内部脑区共享身体资源」的物理落地。
13. **类型契约 vs 实例集合术语明确**——之前「跨维度共享 McpDescriptor」表达总让人误以为「Agent 和 Workspace 共享同一份 McpList 实例」。本轮明确：**类型契约由基建层提供一份**（`McpDescriptor` / `SkillDescriptor` / `ToolDescriptor` 顶层模块）**，实例集合由 Agent 与 Workspace 各自独立持有**。同抽象、不同实例——错位问题从未出现。

**本轮补充（Kernel 顶层模块物理删除）**：

14. **`CBIM.Kernel` 顶层模块物理删除**——本轮裁决：原 `Kernel/` （含 FlowGraph / TaskScheduler / ContextProviders 三子模块）连同 .cs / .meta / .dna 整块 git rm 物理删除。原因：Kernel 两大职责被 Brain 层完全吸收——（1）任务调度协调（脑区间协作）由 PrefrontalCortex 主脑（铁律 A：唯一通路）完全覆盖；（2）LLM 执行器封装（msai + 可扩展外部 Agent）由 BrainBase（含 msai ChatClientAgent）+ ExternalMotorCortex / ClaudeCodeMotorCortex（外部桥接）完全覆盖。Kernel 沦为僵尸代码且报编译错（namespace 漂移、API 错引用），删了最干净。
15. **上轮「外部 Agent 装配家以 Kernel/FlowGraph 为 task.Who 路由」表达废除**——本轮 Kernel 删除后，路由交互全部下沉为 Agent/Brain.PrefrontalCortex 主脑内部 LLM + AIFunction 闭环。外部引擎以 ExternalMotorCortex 子类形式裂含在主脑可调度的脑区资源池中，外部引擎在跨装配家间不再需要外部调度器。

## Emergent Insights

1. **三足鼎立后能力维度的扩展轴看一眼就明**——三个子目录在 AgentSystem 下并列，agent 要「多会一手」三条路径，互不交叉互不覆盖。上一轮 Skill 裸露 / McpAdapter 孤为子模块的不对称状态被拉齐。
2. **跨维度共享抽象不是耦合**——McpDescriptor 被 AgentDescription 与 ModuleDescription 同时使用，不意味能力维度与业务维度耦合——是同一抽象被两个维度独立调用。跨维度共享只限 `McpDescriptor`，其余抽象（Skill / SystemTool）不跨维度。
3. **Mcp 子模块只出抽象、不出胶水**（本轮治理后状态）——胶水可能被能力侧 / 业务侧两处重复调 Microsoft.Agents.AI.Mcp，未来如出现明显重复代码再抽取为 Adapter 类。现阶段“类型从业务中退出”十分充足。
4. **装配家平级化原则**——Agent 引擎可以有多个装配家（本模块管 Microsoft、ExternalAdapter 管 Claude Code / Cursor / Codex、未来可能还有别的），**它们永远平级、永远互不感知**。装配家之间不需要公共抽象基类——它们的「共同点」不在模块间，而在 Kernel/FlowGraph 侧：同为 `task.Who` 的可调度目标、同走 Session 记录协议。跨装配家的统一在上层调度器达成，而不是在装配家之间建立抽象层——后者会逆转依赖方向，把亲生装配家（本模块）裹挨上领养装配家的生命周期问题。

5. **本轮装配家平级化原则修订**——原表达「装配家之间的『共同点』在 Kernel/FlowGraph 侧：同为 `task.Who` 的可调度目标」随 Kernel 顶层模块物理删除一同废除。本轮后的新表达：原「多装配家平级」架构上轮已随 ExternalAdapter 废除、本轮随 Kernel 废除两次收敛，现跨装配家统一点下沉到 **Agent/Brain.PrefrontalCortex 主脑内部 LLM**——主脑的 AIFunction 工具集里同时存在「调 NativeBrain」与「调 ExternalMotorCortex（包含 ClaudeCodeMotorCortex）」两类函数，主脑 LLM 根据任务语义选择。跨调度器抽象不存在（主脑本身是唯一调度者·铁律 A）。

## Non-Goals

- 不写 Agent 装配框架——`AIAgentBuilder` 接管。
- 不写短期会话 / thread 管理——Microsoft AgentThread 接管。
- 不写工具调用闭环——`FunctionInvokingChatClient` 接管。
- 不写会话压缩——Microsoft Compaction 接管。
- 不写自有 SessionStore（若 Microsoft AgentSession API 稳定，长期切换为 host）。
- **不实现 MCP 协议本身**——交 `Microsoft.Agents.AI.Mcp`。
- 不在本服务层直接管理 MCP server 进程生命周期——调 Microsoft client 启 / Dispose，在 OpenInstance / CloseInstance 入口发起。

