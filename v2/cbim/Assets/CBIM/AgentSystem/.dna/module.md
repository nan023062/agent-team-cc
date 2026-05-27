---
name: cbim-unity-agent-system
owner: architect
description: 能力系统（C 维度）服务层。Microsoft 已有 AIAgentBuilder + ChatClientAgent + AgentSession；CBIM AgentSystem 保留 AgentDescription（含 tools / agent_extension_clis / mcp_servers 三类工具能力声明）+ 装配胶水 OpenInstance + Session 写侧。本轮新增：MCP server 接入——OpenInstance 期启 server 进程 + 连 task.Where + 包 AIFunction；CloseInstance 期断连 + 终止进程；实现位于 McpAdapter/ 子模块；AgentDescription 新增 mcp_servers 字段。
keywords: []
dependencies: []
status: spec
---

## Positioning

**能力系统是 CBIM 的服务层（C 维度）**：Microsoft 已提供 `AIAgentBuilder` / `ChatClientAgent` / `AgentSession` 整套，CBIM AgentSystem 退化为：

1. **AgentDescription**——CBIM 独有的 agent 类型描述 schema（系统提示词 + 能力关键词 + chat_client 装配选项 + **tools** + **agent_extension_clis** + **mcp_servers**）；落 `.claude/agents/<name>.md` frontmatter + body。
2. **装配胶水（OpenInstance）**——读 AgentDescription → 用 Microsoft `AIAgentBuilder` 装配 `AIAgent`（选 `IChatClient` Provider、可选包 `FunctionInvokingChatClient`、**按 agent 自身声明注入三源工具**：内置 AIFunction（StandardTools）+ 外部 CLI（agent_extension_clis）+ **MCP server（McpAdapter）**、可选 Compaction 策略）。
3. **Session 写侧**——`AppendSessionEvent(instanceId, ev)`；底层可直接 host Microsoft `AgentSession`（其本就是 append-only 工作日志抽象），CBIM 仅补「这条 Session 对应哪个 CBIM AgentInstance」的反查与「distill 作业能扫」的读侧。
4. **MCP server 生命周期**（本轮新增）——OpenInstance 期实依 AgentDescription.mcp_servers 启动 MCP server 进程 + 连 task.Where + 包 AIFunction；CloseInstance 期同口径关。实现位于子模块 `McpAdapter/`，本服务层仅作装配发起。

## CBIM 核心对偶中的位置

AgentSystem 与 Workspace 是一对正交服务层：

| 维度 | 本服务层 | 对偶服务层 |
|------|---------|----------|
| **能力（Capability）** | **AgentSystem**——管理「能力个体」 | — |
| **业务（Business）** | — | **Workspace**——管理「业务工作区」 |

二者**结构对称**：都以 `Description`（类型描述，落项目知识树）+ `Instance`（实例运行态，落 persistentDataPath）二元结构组织；都直接依赖 Storage；都不互相依赖；跨维度协同由 Kernel.FlowGraph 在 Task 期组合。

## 维度归属修正（本轮重大变动）

上一轮设计把「工具能力声明权」放在 `ModuleDescription.standard_tools`——**错**。本轮修正：

| 维度 | 内容 | 归属 |
|------|------|------|
| **能力（Agent）** | **工具 + skill + 专精领域** | AgentDescription（本模块） |
| **业务（Module）** | 工作流程 + 领域知识 | ModuleDescription（Workspace） |

**修正后的维度铁律**：工具属于能力，流程属于业务。

- 「这个 agent 能不能读文件 / 能不能联网 / 能不能跑 git CLI」——是 agent 自身的能力构成，写在 `AgentDescription.tools` + `agent_extension_clis`。
- 「这个 module 在做什么业务流程 / 涉及什么领域知识」——是 module 自身的业务声明，写在 `ModuleDescription` body。
- 工具的「动态注入」属性依然成立：通过「task 选哪个 agent」间接动态（不同任务选不同 agent，agent 自带不同工具集），而非按 module 动态。

## 本轮重要变动：不造能力系统轮子

| Microsoft 已提供 | CBIM 不再写 |
|---|---|
| `Microsoft.Agents.AI.AIAgentBuilder` | 自建 agent 装配链 |
| `Microsoft.Agents.AI.ChatClientAgent` | 自建 agent 实例壳 |
| `Microsoft.Agents.AI.AgentSession` | 自建 SessionEvent 抽象（**改为 host Microsoft AgentSession**） |
| `Microsoft.Agents.AI.AgentThread` | 自建短期会话 transcript |
| `FunctionInvokingChatClient` | 自建工具调用闭环 |
| 多 Provider 装配 | 自建 KernelExtension |

CBIM **只写**：AgentDescription schema（`.claude/agents/*.md`）+ 装配胶水 + Session 与 AgentInstance 反查的薄索引。

## 三类长期·能力维度的数据

| 数据 | schema 归属 | 物理形态 |
|------|------------|---------|
| AgentDescription | **CBIM 独有**（系统提示词 + 能力关键词 + tools + agent_extension_clis + chat_client_config） | `<project>/.claude/agents/<name>.md` |
| AgentInstance | CBIM 独有（instanceId / descriptionName / 创建时间） | `persistentDataPath/.cbim/agents/instances/<id>.json` |
| Session 事件流 | **直接 host Microsoft `AgentSession`** | Microsoft AgentSession 落地路径（本模块仅维持 instanceId → sessionId 反查） |

## Children

| 子模块 | 一句话职责 | 状态 |
|--------|----------|------|
| `StandardTools/` | CBIM 内置通用能力工具集（Files / Search / Web / Bash）按家族 + 沙盒提供 AIFunction | spec |
| `McpAdapter/` | 外部 MCP server 接入适配：OpenInstance 期启动 server 进程 + 连 task.Where + 包 AIFunction；CloseInstance 期断连 + 终止进程 | spec |

### 三种工具来源总览（能力维度内的三并列）

CBIM 能力维度内的 AIFunction 来源有且仅有三类，江听同装配点（OpenInstance）、同生命周期（绑 AIAgent 实例）：

| 类型 | 形态 | 实现归属 | AgentDescription 声明字段 | 例子 |
|------|------|---------|------------------------|------|
| **StandardTools** | CBIM 内置 C# AIFunction | `StandardTools/` 子模块 | `tools: [Files, Search]` | `Read` / `Write` / `Grep` / `Glob` |
| **CLI 包装** | subprocess + stdin/stdout | Bash 家族（未来）+ CLI 白名单注入 | `agent_extension_clis: [git, dotnet]` | `dotnet` / `git` / `unity-cli` |
| **MCP server** | MCP 协议 + IPC | `McpAdapter/` 子模块 | `mcp_servers: [unity-mcp]` | `unity-mcp` / `blender-mcp` |

三者**同维度、同装配点、同生命周期**——仅底层调用形态不同。OpenInstance 是唯一装配胶水点。

## AgentDescription Schema 演进（本轮）

frontmatter 新增三个字段（`tools` / `agent_extension_clis` 上轮已加，`mcp_servers` 本轮加）：

```yaml
---
name: unity-programmer
role: programmer
description: Unity 端 C# 实现专精 agent
capabilities: [unity, csharp, asmdef, dotweens]
keywords: [unity, c#, gameobject]
tools:                                # CBIM 内置 AIFunction 家族名列表
  - Files
  - Search
agent_extension_clis:                 # agent 额外可调用的外部 CLI 工具列表
  - git
  - dotnet
  - unity-cli
mcp_servers:                          # 本轮新增——agent 装配时启动的 MCP server 列表
  - unity-mcp
---
```

C# 端记录追加字段（`Tools` / `AgentExtensionClis` 上轮已加，`McpServers` 本轮加）：

```csharp
public sealed record AgentDescription(
    string Name,
    string Role,
    string Description,
    IReadOnlyList<string> Capabilities,
    IReadOnlyList<string> Keywords,
    string SystemPrompt,
    ChatClientConfig ChatClientConfig,
    IReadOnlyList<string> Tools,                  // 内置 AIFunction 家族名
    IReadOnlyList<string> AgentExtensionClis,     // 外部 CLI 白名单
    IReadOnlyList<string> McpServers);            // 本轮新增：MCP server 名列表
```

字段语义：

- **`tools`**——CBIM 内置 AIFunction 家族名列表（Files / Search / Web / Bash……），由 `AgentSystem/StandardTools/` 子模块提供工厂。声明 = 该 agent 装配时挂载对应家族。未声明 = 不挂。**无全继承语义**。
- **`agent_extension_clis`**——该 agent 额外可调用的外部 CLI 命令白名单（git / dotnet / docker / ffmpeg / unity-cli ……）。装配时与 Bash 家族（若声明）配合，构成命令白名单。
- **`mcp_servers`**（本轮新增）——该 agent 装配时启动的 MCP server 名列表。名字指向 `IMcpRegistry`（`McpAdapter/`）里的 server cfg。OpenInstance 期依列启动进程 + 连 `task.Where` + 包 AIFunction；CloseInstance 期同口径关。
- **三者并列不交并**——都是「工具能力是 agent 业务属性」原则的不同落实路径；装配点都是 OpenInstance，生命周期都绑 AIAgent 实例。
- **未知家族 / 未授 CLI / 未知 MCP server**：装配时 warning，不阻塞（家族跳过 / CLI 不入白名单 / MCP server 启失败优雅降级）。

## Agent 裂变规则（本轮新增 · 铁律）

**不做「全能 agent」，保持专精**。Agent 的工具广度 + skill 广度 + 专精领域跨度共同决定其复杂度上限。

### 裂变触发阈值（任一命中即裂）

| 维度 | 阈值 | 说明 |
|------|------|------|
| **`tools` 家族数** | > 4 | 超过 4 个 AIFunction 家族（Files + Search + Web + Bash + ……）= 工具栏过宽 |
| **`agent_extension_clis` CLI 数** | > 6 | 超过 6 个外部 CLI = 外部命令面太杂 |
| **`mcp_servers` server 数**（本轮新增） | > 3 | 超过 3 个 MCP server = 跨业务面太杂，且每个 server 都是独立外部进程，启动成本高 |
| **`capabilities` 跨领域跨度** | 跨 2+ 主领域 | 例：Unity + Backend + Blender 三栈混挂——拒绝 |
| **system_prompt 长度** | > 3000 token | 提示词膨胀通常意味着责任膨胀 |
| **skills 文件总数** | > 8 | 单 agent 关联超过 8 个 skill = 心智超载 |

命中其一 → 立即触发裂变审议（HR 与 architect 协商）。

### 裂变范式

- **按专精领域裂**——`ProgrammerAgent` 一个吃全宇宙 → `UnityProgrammerAgent` / `BlenderArtistAgent` / `BackendProgrammerAgent` 各管一摊。
- **按工具家族裂**——若不同任务需要的工具集互斥（数据科学 vs 游戏开发），按工具集分群裂。
- **按 MCP server 裂**（本轮新增）——不同 MCP server 面向不同业务生态（unity-mcp vs blender-mcp vs db-mcp）时，裂为该业务专精 agent。
- **按调用频度裂**——使用频繁但责任窄的部分独立成轻量 agent（auditor / hr / architect 已是此范式）。

### 通用 vs 专精 Agent

| 类别 | 角色 | 典型规模 |
|------|------|---------|
| **通用** | coordinator / hr / architect / auditor —— 协调与治理角色 | tools ≤ 2、agent_extension_clis ≤ 2、mcp_servers ≤ 1 |
| **专精** | unity-programmer / blender-artist / backend-programmer / writer / sound-engineer | tools ≤ 4、agent_extension_clis ≤ 6、mcp_servers ≤ 3，且 capabilities 单领域聚焦 |

通用 agent 保持轻——它们的价值是路由 / 决策 / 文档，不是执行重活；专精 agent 允许工具栏更宽，但**单领域聚焦** + 严守上限。

### HR 接管裂变实施

裂变审议由 HR 主持（HR 的 hr_agents skill 已含 agent 裂变 / 合并工作流）；本模块只提供「触发阈值」铁律。

## Contract Surface

```csharp
namespace CBIM.AgentSystem;

using Microsoft.Agents.AI;

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

public sealed record AgentDescription(
    string Name,
    string Role,
    string Description,
    IReadOnlyList<string> Capabilities,
    IReadOnlyList<string> Keywords,
    string SystemPrompt,
    ChatClientConfig ChatClientConfig,
    IReadOnlyList<string> Tools,                  // CBIM AIFunction 家族名
    IReadOnlyList<string> AgentExtensionClis,     // 外部 CLI 白名单
    IReadOnlyList<string> McpServers);            // 本轮新增：MCP server 名列表

public sealed record OpenInstanceOptions(
    IChatClient? ChatClientOverride = null,
    bool? EnableFunctionInvocation = null,
    IReadOnlyList<Microsoft.Extensions.AI.AIFunction>? Tools = null,
    IReadOnlyList<Microsoft.Extensions.AI.AIContextProvider>? Providers = null,
    string? TaskWhere = null);                    // 本轮新增：注入给 MCP server 启动的 workspaceRoot（= task.Where）
```

**SessionEvent**：本模块定义薄基类 + 几个子类（UserInput / LlmCall / ToolInvocation / Output / Error），落盘策略可走 Microsoft AgentSession 或本模块直接 jsonl。本轮初期实现可直接 jsonl，待 Microsoft AgentSession API 稳定后切换为 host。

**OpenInstanceOptions.TaskWhere**（本轮新增）：MCP server 启动需要 workspaceRoot——该值固定取 `task.Where`，由调用方（CbimTaskExecutor / Channel 业务逻辑）透传。不允许 agent / OpenInstance 内部猜。若 `McpServers` 非空且未传 `TaskWhere` → throw `InvalidOperationException`。

## Service-Layer Extension Model

OpenInstance 是 **CBIM 装配能力 → Microsoft AIAgent 实例**的唯一胶水点。集中：
- 从 AgentDescription 取 `chat_client_config`
- 调 `AIAgentBuilder` 装配 `IChatClient`
- 可选 `FunctionInvokingChatClient` 包装
- 挂 Microsoft.Extensions.AI 生态 AIFunction（Agent 工具能力）
- 装配默认 Compaction 策略

未来新增 Provider / 换 Compaction / 挂新 AIFunction 类——只动这一处。

### 三源工具装配总序（本轮拓展）

OpenInstance 内部按下面顺序装配三源 AIFunction，最后合并传给 `AIAgentBuilder`：

```
OpenInstance(descriptionName, options):
  desc = GetDescription(descriptionName)
  workspaceRoot = options.TaskWhere   // 必传当 desc.McpServers 非空

  # 源 1：StandardTools（内置 AIFunction）
  sandbox = BuildSandbox(projectRoot, instanceRunDir)
  stdFns = StandardToolsService.CreateFamilies(desc.Tools, sandbox)
  # Bash 家族（若含）+ desc.AgentExtensionClis → CLI 白名单注入 Bash

  # 源 2：MCP server（本轮新增）
  mcpHandles = []
  foreach name in desc.McpServers:
      try:
          handle = await McpServerAdapter.StartAsync(name, workspaceRoot)
          mcpHandles.Add(handle)
      catch e:
          log.warn("MCP server start failed: {name}", e)   # 优雅降级，不阻塞
  mcpFns = mcpHandles.SelectMany(h => h.Functions).ToList()

  # 源 3：options.Tools（调用方额外透传的外插工具）
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
      await handle.DisposeAsync()                    # 断 IPC + Kill server 进程
  UnregisterInstance(instanceId)
```

### 三源对齐表

| 来源 | 声明字段 | 装配胶水 | 生命周期释放 |
|------|---------|---------|------------|
| StandardTools | `desc.Tools` | `StandardToolsService.CreateFamilies` | 随 AIAgent GC |
| CLI 包装 | `desc.AgentExtensionClis` | 注入 Bash 家族白名单 | 随 AIAgent GC |
| MCP server | `desc.McpServers` | `McpServerAdapter.StartAsync(name, task.Where)` | **CloseInstance 期 `handle.DisposeAsync` 显式释放** |

**MCP 是唯一需显式释放的源**——因为持有外部 server 进程。不释放 = 进程泄漏。这是 CloseInstance 接口存在的最强动机。

### CBIM 标准工具集的装配序（上轮修正备忘）

`AgentSystem/StandardTools/` 子模块提供一组按家族组织的 AIFunction（Files / Search / Web / Bash），**按 `AgentDescription.tools` 声明 + per-agent 沙盒装配**（不再按 module 装配）。装配责任落在 **OpenInstance 内部**——OpenInstance 是装配唯一胶水点。

**装配点的归属裁决**：

- `CbimTaskExecutor.HandleAsync` 的职责是「一次 `AIAgent.RunAsync` + 写 Session」，不是「装配 AIAgent」——它拿到的 `task.Who` 本身就是已装配好的 AIAgent（工具已挂）。
- AgentSystem 的「唯一胶水点」铁律要求装配逻辑全部走 OpenInstance——如果装配能力裂脱到 CbimTaskExecutor，将出现两个装配路径，违反 C1。
- Channel 也可能直接调 OpenInstance（不走 CbimTaskExecutor），那些场景同样需要工具装配——只有放在 OpenInstance 才能被所有入口共享。

**`OpenInstanceOptions` 本轮变动**：上轮新增的 `ActiveModulePaths` 字段上轮已删；本轮新增 `TaskWhere` 字段，用于透传 MCP server 启动的 workspaceRoot。

## Dependencies

- `CBIM.Storage`——AgentDescription / AgentInstance / Session 元数据 IO。
- `Microsoft.Agents.AI`——`AIAgent` / `AIAgentBuilder` / `ChatClientAgent` / `AgentSession`。
- `Microsoft.Extensions.AI`——`IChatClient` / `AIFunction` / `AIContextProvider`。
- **`CBIM.AgentSystem.StandardTools`**——调 `StandardToolsService.CreateFamilies` 装配内置工具。
- **`CBIM.AgentSystem.McpAdapter`**（本轮新增子模块）——调 `McpServerAdapter.StartAsync` 启 MCP server，CloseInstance 期 `handle.DisposeAsync`。
- **不依赖** Workspace / Kernel / Memory——能力维度服务层只依赖自己的子模块 + Storage + Microsoft 包。

依赖方向：能力服务层 → 子模块（StandardTools / McpAdapter） → Microsoft 包 + Storage，无反向边。

## 铁律

- **Session 写入唯一调用者 = 业务 Workflow 的 CbimTaskExecutor**——其他模块不准直调 AppendSessionEvent。
- **OpenInstance 是装配胶水唯一入口**——Channel / 业务代码不直接 new ChatClientAgent。三源工具（StandardTools / CLI / MCP）必顶都在这里装配。
- **不 host 短期会话**——AgentThread / ChatHistoryProvider 由 Microsoft 内部管，CBIM 不感知。
- **不重写 AIAgent**——AgentInstance 仅是 CBIM 元数据壳，运行体永远是 Microsoft `AIAgent`。
- **工具归能力，流程归业务**——`AgentDescription.tools` / `agent_extension_clis` / `mcp_servers` 是工具能力的唯一声明地，`ModuleDescription` 不持任何工具字段。
- **MCP server 连接目标必须 = task.Where**（本轮新增）——能力归能力，目标归业务；workspaceRoot 由 OpenInstance 从 `options.TaskWhere` 注入，不可被 agent / 调用方覆盖。
- **MCP server 生命周期严格绑 AgentInstance**（本轮新增）——OpenInstance 启 / CloseInstance 必 DisposeAsync。异常路径也走，否则进程泄漏。
- **Agent 必须专精**——`tools` / `clis` / `mcp_servers` / `capabilities` / `system_prompt` / `skills` 任一维度超阈值，HR 立即裂变。

## Origin Context

上一轮 AgentSystem 已大幅简化（合并 AgentRegistry），并新增对 Workspace 的依赖以读 `ModuleDescription.standard_tools`——上轮裁定该依赖方向反了：工具属于能力维度（agent），不属于业务维度（module）。

上轮裁决：
1. 删 `OpenInstanceOptions.ActiveModulePaths` 字段；
2. 删对 `CBIM.Workspace` / `CBIM.Workspace.StandardTools` 的依赖；
3. 新增 `AgentDescription.tools` + `agent_extension_clis` 字段；
4. StandardTools 子模块物理迁入 AgentSystem 之下；
5. 新增 Agent 裂变规则——防止「全能 agent」误区在能力维度复发。

**本轮增量（MCP 集成）**：能力维度的「工具来源」上轮识别了两类（StandardTools / agent_extension_clis），本轮补第三类：**外部 MCP server**。

1. 新增 `AgentDescription.mcp_servers` 字段（与 tools / agent_extension_clis 并列）。
2. 新增 `OpenInstanceOptions.TaskWhere` 字段（MCP server 启动需 workspaceRoot）。
3. 新增子模块 `AgentSystem/McpAdapter/`——责任：MCP server 启 / 连 / AIFunction 包装 / 关。
4. OpenInstance 装配序增「MCP server 启」一步，CloseInstance 增「handle.DisposeAsync」一步。
5. 裂变阈值表增 `mcp_servers 数 > 3` 一行。
6. 依赖表增 `CBIM.AgentSystem.McpAdapter` 一项。

为什么独立子模块而不居住 AgentSystem 主服务：MCP server 生命周期管理 + IPC 连接 + Microsoft.Agents.AI.Mcp 依赖是一份独立的责任；与 StandardTools 同位阶（都是「某种工具来源」子模块）。C2 单责任 + C5 共用复用双信号。

## Non-Goals

- 不写 Agent 装配框架——`AIAgentBuilder` 接管。
- 不写短期会话 / thread 管理——Microsoft AgentThread 接管。
- 不写工具调用闭环——`FunctionInvokingChatClient` 接管。
- 不写会话压缩——Microsoft Compaction 接管。
- 不写自有 SessionStore（若 Microsoft AgentSession API 稳定，长期切换为 host）。
- 不重新定义 schema——`AgentDescription` 沿用 `.claude/agents/*.md` frontmatter。
- **不实现 MCP 协议本身**（本轮修正——交 `Microsoft.Agents.AI.Mcp`）；本模块仅在 `McpAdapter/` 子模块中写接入胶水。
- 不在本服务层直接管理 MCP server 进程生命周期——责任下沉到 `McpAdapter/` 子模块；本服务层仅在 OpenInstance / CloseInstance 中调用其接口。
