---
name: cbim-unity-agent-system
owner: architect
description: 能力系统（C 维度）服务层。Microsoft 已有 AIAgentBuilder + ChatClientAgent + AgentSession；CBIM AgentSystem 保留 AgentDescription（Id / Name / Soul / Identity + Skills / SystemTools / McpList 三类能力扩展字段）+ 装配胶水 OpenInstance + Session 写侧。本轮重大调整：能力维度三大扩展抽象平级子模块化——Skills / StandardTools / Mcp 三足鼎立，同为 agent 的扩展通道、同装配点、同生命周期、同被 AgentDescription 三字段并列引用。McpDescriptor 是 CBIM 唯一跨维度共享抽象（AgentDescription.McpList 与 ModuleDescription.McpList 同类型）。上一轮的 McpAdapter/ 子模块名称改为 Mcp/，与 Skills / StandardTools 命名风格对齐。
keywords: []
dependencies: []
status: spec
---

## Positioning

**能力系统是 CBIM 的服务层（C 维度）**：Microsoft 已提供 `AIAgentBuilder` / `ChatClientAgent` / `AgentSession` 整套，CBIM AgentSystem 退化为：

1. **AgentDescription**——CBIM 独有的 agent 类型描述 schema，以 C# 类实例化（不是 frontmatter yaml，这是 Unity 侧 schema 表达方式）：包含 `Id` / `Name` / `Soul` / `Identity` + 能力维度三大扩展字段（`Skills` / `SystemTools` / `McpList`）。
2. **装配胶水（OpenInstance）**——读 AgentDescription → 用 Microsoft `AIAgentBuilder` 装配 `AIAgent`（选 `IChatClient` Provider、可选包 `FunctionInvokingChatClient`、按 agent 自身声明注入三源工具：Skills（AgentSkillsProvider）+ SystemTools（StandardTools）+ McpList（Mcp 启 server / 连远端）、可选 Compaction 策略）。
3. **Session 写侧**——`AppendSessionEvent(instanceId, ev)`；底层可直接 host Microsoft `AgentSession`，CBIM 仅补「这条 Session 对应哪个 CBIM AgentInstance」的反查与「distill 作业能扫」的读侧。

## CBIM 核心对偶中的位置

AgentSystem 与 Workspace 是一对正交服务层：

| 维度 | 本服务层 | 对偶服务层 |
|------|---------|----------|
| **能力（Capability）** | **AgentSystem**——管理「能力个体」 | — |
| **业务（Business）** | — | **Workspace**——管理「业务工作区」 |

二者**结构对称**：都以 `Description`（类型描述）+ `Instance`（实例运行态）二元结构组织；都直接依赖 Storage；都不互相依赖；跨维度协同由 Kernel.FlowGraph 在 Task 期组合。

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

AgentSystem 下能力维度三大扩展抽象的三个**平级** leaf 子模块：

| 子模块 | 一句话职责 | 抽象类 | 装配产物 | 状态 |
|--------|----------|--------|---------|------|
| `Skills/` | CBIM 内置技能描述抽象 | `Skill` | AgentSkillsProvider 注入 | spec |
| `StandardTools/` | CBIM 内置通用能力工具集（Files / Search / Web / Bash）| `SystemTool`（家族引用）| 进程内 `AIFunction` 列表 | spec |
| `Mcp/` | MCP 描述符抽象（abstract + Stdio/Http 子类 + Transport 枚举）| `McpDescriptor` | 启 server / 连远端 + 包 `AIFunction` | spec |

### 三足鼎立关系（本轮关键裁决）

三子模块**同为「agent 能多会一手」的扩展通道**、**同装配点（OpenInstance）**、**同生命周期（绑 AIAgent 实例）**、**同被 AgentDescription 声明侧引用**——仅扩展形态不同。

```csharp
public sealed class AgentDescription
{
    public string Id { get; }
    public string Name { get; }
    public string Soul { get; }       // 系统提示词 / 人格
    public string Identity { get; }   // 身份 / 角色定位

    public IReadOnlyList<Skill> Skills { get; }              // 技能列表
    public IReadOnlyList<SystemTool> SystemTools { get; }    // 内置工具家族声明
    public IReadOnlyList<McpDescriptor> McpList { get; }     // MCP server 声明（抽象基类列表）
}
```

三字段语义：

- **`Skills`**——该 agent 会的手艺（SKILL.md 风格描述），装配时由 AgentSkillsProvider 注入 LLM 上下文。类型来自 `CBIM.Skills.Skill`。
- **`SystemTools`**——该 agent 要装哪些 CBIM 内置工具家族（Files / Search / Web / Bash ……）。类型来自 `CBIM.AgentSystem.SystemTool`（现位于父命名空间，后续可平移到 `CBIM.Tools.Standard`）。声明 = 该 agent 装配时挂对应家族。
- **`McpList`**——该 agent 装配时需启动 / 连接的 MCP server 列表。类型来自 `CBIM.Mcp.McpDescriptor`（抽象基类，实例为 `StdioMcpDescriptor` / `HttpMcpDescriptor`）。
- **三者并列不交并**——都是「能力是 agent 的业务属性」原则的不同落实路径；装配点都是 OpenInstance，生命周期都绑 AIAgent 实例。
- **未知家族 / 未授 server**：装配时 warning，不阻塞（家族跳过 / MCP server 启失败优雅降级）。

### Mcp 子模块的额外职责（跨维度共享抽象）

**`McpDescriptor` 同时被 `AgentDescription.McpList` 与 `ModuleDescription.McpList` 使用**——这是 CBIM 内**唯一**跨维度共享的抽象类。

- 能力维度的 McpList = agent 自带的 MCP server（agent 装配时启动、跟人走）。
- 业务维度的 McpList = 业务 module（含云模块）暴露的 MCP server 端点（业务上下文中按需启动、跟业务走）。

两侧各自装配位置可能调 `Microsoft.Agents.AI.Mcp` client 启动 server / 连远端——装配胶水本轮未抽抽类，在能力侧 / 业务侧各自调发。

Workspace 反向引用 `Mcp/` 子模块的 `McpDescriptor` 类型——依赖方向：`Workspace → AgentSystem.Mcp`（Workspace 是更易变的业务层，Mcp 是更稳定的能力扩展层，符合 C3 单向依赖）。

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
using CBIM.Mcp;

public sealed class AgentSystemService
{
    // AgentDescription（类型）—— 读侧
    IReadOnlyList<AgentDescription> ListDescriptions();
    AgentDescription? GetDescription(string name);
    IReadOnlyList<AgentDescription> MatchDescriptions(string capability, int topK);

    // AgentInstance —— 装配 / 实例查询
    AIAgent OpenInstance(string descriptionName, OpenInstanceOptions? options = null);
    void CloseInstance(string instanceId);
    AIAgent? GetAgent(string instanceId);
    IReadOnlyList<AgentInstance> ListInstances();

    // Session —— 写侧 + 读侧
    void AppendSessionEvent(string instanceId, SessionEvent ev);
    IReadOnlyList<SessionEvent> ReadSessionTail(string instanceId, int n);

    AgentStats Stats();
}

/// AgentDescription 为 C# 可变纪录类（以代码为准，不是 frontmatter）
public sealed class AgentDescription
{
    public string Id { get; }
    public string Name { get; }
    public string Soul { get; }
    public string Identity { get; }
    public IReadOnlyList<Skill> Skills { get; }
    public IReadOnlyList<SystemTool> SystemTools { get; }
    public IReadOnlyList<McpDescriptor> McpList { get; }
}

public sealed record OpenInstanceOptions(
    IChatClient? ChatClientOverride = null,
    bool? EnableFunctionInvocation = null,
    IReadOnlyList<Microsoft.Extensions.AI.AIFunction>? Tools = null,
    IReadOnlyList<Microsoft.Extensions.AI.AIContextProvider>? Providers = null,
    string? TaskWhere = null);                    // MCP server 启动 workspaceRoot（task.Where）
```

**SessionEvent**：本模块定义薄基类 + 几个子类（UserInput / LlmCall / ToolInvocation / Output / Error），落盘策略可走 Microsoft AgentSession 或本模块直接 jsonl。本轮初期实现可直接 jsonl，待 Microsoft AgentSession API 稳定后切换为 host。

**OpenInstanceOptions.TaskWhere**：MCP server 启动需 workspaceRoot——该值固定取 `task.Where`，由调用方（CbimTaskExecutor / Channel 业务逻辑）透传。不允许 agent / OpenInstance 内部猜。若 `McpList` 非空且未传 `TaskWhere` → throw `InvalidOperationException`。

## Service-Layer Extension Model

OpenInstance 是 **CBIM 装配能力 → Microsoft AIAgent 实例**的唯一胶水点。集中：

- 从 AgentDescription 取 `Soul` / `Identity` / `Name` → `ChatClientAgentOptions` (Instructions / Description / Name)
- 调 `AIAgentBuilder` 装配 `IChatClient`
- 可选 `FunctionInvokingChatClient` 包装
- 挂 Microsoft.Extensions.AI 生态 `AIFunction`（Agent 工具能力）
- 装配默认 Compaction 策略

未来新增 Provider / 换 Compaction / 挂新 AIFunction 类——只动这一处。

### 三源能力装配总序

OpenInstance 内部按三源顺序装配，最后合并传给 `AIAgentBuilder`：

```
OpenInstance(descriptionName, options):
  desc = GetDescription(descriptionName)
  workspaceRoot = options.TaskWhere   // 必传当 desc.McpList 非空

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
  agent = AIAgentBuilder.Create(...)
      .UseFunctionInvocation()
      .UseTools(allFns)
      .Build()

  RegisterInstance(instanceId, agent, mcpHandles)   # mcpHandles 随实例生命周期
  return agent

CloseInstance(instanceId):
  inst = LookupInstance(instanceId)
  foreach handle in inst.McpHandles:
      await handle.DisposeAsync()                    # 断 IPC + Kill server 进程 / 断 HTTP
  UnregisterInstance(instanceId)
```

### 三源对齐表

| 来源 | 声明字段 | 装配胶水 | 生命周期释放 |
|------|---------|---------|------------|
| Skills | `desc.Skills` | AgentSkillsProvider（未来落地）注入 LLM 上下文 | 随 AIAgent GC |
| SystemTools | `desc.SystemTools` | `StandardToolsService.CreateFamilies` | 随 AIAgent GC |
| MCP server | `desc.McpList` | `Microsoft.Agents.AI.Mcp` client.StartAsync（代替原 McpServerAdapter）| **CloseInstance 期 `handle.DisposeAsync` 显式释放** |

**MCP 是唯一需显式释放的源**——因为持有外部 server 进程 / 连接。不释放 = 资源泄漏。这是 CloseInstance 接口存在的最强动机。

## Dependencies

- `CBIM.Storage`——AgentDescription / AgentInstance / Session 元数据 IO。
- `Microsoft.Agents.AI`——`AIAgent` / `AIAgentBuilder` / `ChatClientAgent` / `AgentSession`。
- `Microsoft.Extensions.AI`——`IChatClient` / `AIFunction` / `AIContextProvider`。
- `Microsoft.Agents.AI.Mcp`——MCP client（本模块在 OpenInstance 内使用。接口抽象仅使用 `CBIM.Mcp.McpDescriptor`）。
- **`CBIM.Skills`**（子模块）——`Skill` 类型。
- **`CBIM.Tools.Standard`**（子模块）——`StandardToolsService.CreateFamilies` 装配内置工具。
- **`CBIM.Mcp`**（子模块）——`McpDescriptor` / `McpTransportKind` / `StdioMcpDescriptor` / `HttpMcpDescriptor`。
- **不依赖** Workspace / Kernel / Memory——能力维度服务层只依赖自己的子模块 + Storage + Microsoft 包。

依赖方向：能力服务层 → 子模块（Skills / StandardTools / Mcp） → Microsoft 包 + Storage，无反向边。

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

- **Session 写入唯一调用者 = 业务 Workflow 的 CbimTaskExecutor**——其他模块不准直调 AppendSessionEvent。
- **OpenInstance 是装配胶水唯一入口**——Channel / 业务代码不直接 new ChatClientAgent。三源工具（Skills / SystemTools / McpList）都在这里装配。
- **不 host 短期会话**——AgentThread / ChatHistoryProvider 由 Microsoft 内部管，CBIM 不感知。
- **不重写 AIAgent**——AgentInstance 仅是 CBIM 元数据壳，运行体永远是 Microsoft `AIAgent`。
- **工具归能力，流程归业务**——`AgentDescription.Skills` / `SystemTools` / `McpList` 是能力声明的唯一地，`ModuleDescription` 不持任何能力字段。
- **三子模块平级不交叉**——Skills / StandardTools / Mcp 互不引用；并列被 AgentDescription 引用；各自在 OpenInstance 装配口发。
- **MCP server 连接目标必须 = task.Where**——能力归能力，目标归业务；workspaceRoot 由 OpenInstance 从 `options.TaskWhere` 注入，不可被 agent / 调用方覆盖。
- **MCP server 生命周期严格绑 AgentInstance**——OpenInstance 启 / CloseInstance 必 DisposeAsync。异常路径也走，否则进程泄漏。
- **Agent 必须专精**——`SystemTools` / `Skills` / `McpList` / 专精领域跨度 / `Soul` 长度任一维度超阈值，HR 立即裂变。
- **`McpDescriptor` 是唯一跨维度共享抽象**——`AgentDescription.McpList` 与 `ModuleDescription.McpList` 同类型；上上说然，共用不代表跨维度耦合——是同一「外部端点」抽象被两个维度各自声明使用。

## Origin Context

上一轮裁决：
1. 删 `OpenInstanceOptions.ActiveModulePaths` 字段；
2. 删对 `CBIM.Workspace` / `CBIM.Workspace.StandardTools` 的依赖；
3. 新增 `AgentDescription.tools` + `agent_extension_clis` 字段；
4. StandardTools 子模块物理迁入 AgentSystem 之下；
5. 新增 Agent 裂变规则——防止「全能 agent」误区在能力维度复发。

上轮增量（MCP 集成）：能力维度的「工具来源」上上轮识别了两类（StandardTools / agent_extension_clis），上轮补第三类：外部 MCP server。新增 `mcp_servers` 字段、`OpenInstanceOptions.TaskWhere` 字段、`AgentSystem/McpAdapter/` 子模块；裂变阈值表增 `mcp_servers 数 > 3` 一行。

**本轮重大调整**（三大扩展抽象平级子模块化 · 代码已落地）：

1. **AgentDescription 以 C# 类实例化**（不是 frontmatter yaml 字串）：Id / Name / Soul / Identity + `Skills: List<Skill>` + `SystemTools: List<SystemTool>` + `McpList: List<McpDescriptor>` 三能力字段。代替上轮的字串名列表调用。
2. **`mcp_servers: [name]` 名字串 + IMcpRegistry 二级查棅取消**——`AgentDescription.McpList` 直接持 `McpDescriptor` 实例（`Stdio` 或 `Http`）。理由：Unity 项目内 cfg 与 agent 共存，二级表反增同步成本。
3. **原 `McpAdapter/` 子模块 → `Mcp/`**：名字与 Skills / StandardTools 对齐（都是「该抽象的家」）。
4. **`McpDescriptor` record → abstract 基类 + 两子类 + `McpTransportKind` 枚举**：Stdio / Http 两形态明确区分，形态识别从「字段是否存在」升为「类型判别」。
5. **`Skill` 从裸露在 AgentSystem/ 迁到 Skills/ 子模块**，namespace 独立。
6. **跨维度共享**：`Workspace.ModuleDescription.McpList: List<McpDescriptor>` 新增，同 `AgentDescription.McpList` 类型；`ModuleDna` 退为纯知识载体（不再夹带 MCP 协议信息）。
7. **McpServerAdapter / McpServerHandle 本轮未随代码落地**：装配侧（OpenInstance / 业务 Workflow）直接调 Microsoft.Agents.AI.Mcp client。后续如出现重复胶水再抽取。

## Emergent Insights

1. **三足鼎立后能力维度的扩展轴看一眼就明**——三个子目录在 AgentSystem 下并列，agent 要「多会一手」三条路径，互不交叉互不覆盖。上一轮 Skill 裸露 / McpAdapter 孤为子模块的不对称状态被拉齐。
2. **跨维度共享抽象不是耦合**——McpDescriptor 被 AgentDescription 与 ModuleDescription 同时使用，不意味能力维度与业务维度耦合——是同一抽象被两个维度独立调用。跨维度共享只限 `McpDescriptor`，其余抽象（Skill / SystemTool）不跨维度。
3. **Mcp 子模块只出抽象、不出胶水**（本轮治理后状态）——胶水可能被能力侧 / 业务侧两处重复调 Microsoft.Agents.AI.Mcp，未来如出现明显重复代码再抽取为 Adapter 类。现阶段“类型从业务中退出”十分充足。

## Non-Goals

- 不写 Agent 装配框架——`AIAgentBuilder` 接管。
- 不写短期会话 / thread 管理——Microsoft AgentThread 接管。
- 不写工具调用闭环——`FunctionInvokingChatClient` 接管。
- 不写会话压缩——Microsoft Compaction 接管。
- 不写自有 SessionStore（若 Microsoft AgentSession API 稳定，长期切换为 host）。
- **不实现 MCP 协议本身**——交 `Microsoft.Agents.AI.Mcp`。
- 不在本服务层直接管理 MCP server 进程生命周期——调 Microsoft client 启 / Dispose，在 OpenInstance / CloseInstance 入口发起。

