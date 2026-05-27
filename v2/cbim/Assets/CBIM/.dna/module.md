---
name: cbim-unity-agentos
owner: architect
description: CBIM Agent OS · Unity 原生 C# 实现。本轮顶层重构：彻底贯穿「不造轮子」原则——以 Microsoft.Agents.AI + Microsoft.Agents.AI.Workflows + Microsoft.Extensions.AI 生态为底层，CBIM 仅保留业务独有部分。SystemTools / ExecutionUnit / TaskRunner 本轮废弃；Memory / AgentSystem / Channel 大幅瘦身。组成根：Channel（入口）+ Kernel（3 子模块胶水）+ AgentSystem / Memory / Workspace（三服务层）+ Storage（IO 原语）。
keywords: []
dependencies: []
status: spec
---

## Positioning

CBIM Agent OS 的 Unity 原生 C# 实现。本模块是组合根，自身**不承载任何业务逻辑**——只做装配。

**本轮顶层重构**：彻底贯穿「不造轮子」——所有能用 Microsoft Agent Framework 生态替代的全部交出去，CBIM 只保留真正业务独有的部分。

## 核心对偶：能力 / 业务

CBIM 把「软件中的角色」分成两个正交维度，并以两套独立服务层承载：

| 维度 | 概念 | 服务层 | 本维度内容 | 物理形态 |
|------|------|--------|------------|----------|
| **能力（Capability）** | Agent —— 具有特定领域能力的「个体」 | `AgentSystem/`（C 维度） | **Soul / Identity + Skills + SystemTools + McpList + 专精领域** | `AgentDescription`（C# 类实例化） + `AgentInstance` |
| **业务（Business）** | Module —— 特定业务类型的「工作区」 | `Workspace/`（B 维度） | **Dna + Workflows + McpList** | `ModuleDescription` + `ModuleInstance` |
| **记忆（Memory）** | 跨能力跨业务的事实 / 决策 / 原则沉淀 | `Memory/`（M 维度） | 事实 / 决策 entries | `MemoryEntry` 才平 JSON |

**对偶的核心约束**：

- 能力维度回答「**谁**能动 + 拿什么工具动」——工具是 agent 的能力构成。
- 业务维度回答「在**什么样的工作区**里动、能动**什么**（业务流程 + 领域知识 + 业务接入点）」——不持 agent 工具。
- 一件任务由二者交叉成立——`Task = Agent + ModuleList + Requirement`。三大服务系统互不依赖，跨系统协同走 Kernel.FlowGraph + ContextProviders。

**唯一跨维度共享抽象（本轮重点）**：`McpDescriptor`——同抽象、同类型、同符号；被 `AgentDescription.McpList`（能力侧：agent 自带、跟人走）与 `ModuleDescription.McpList`（业务侧：module 接入点、跟业务走）同时引用。依赖方向严格单向：`Workspace → AgentSystem.Mcp`。

**维度错位的反面教材**：上一轮把工具声明放在 `ModuleDescription.standard_tools`，本轮推翻——详「能力 / 业务对偶铁律」节。记住：「看起来与某维度伴生」 ≠ 「应在该维度 schema 内」。

## 类比助记：人 + 办公位 = 任务场景

抽象描述都对，但难记。换个 mental model——CBIM 一次任务的两个主角，是**一个人坐到一个办公位上干活**。

### `AgentInstance` = 一个人

| 字段 | 类比 |
|------|------|
| `Agent`（MS AIAgent）| **大脑** —— 决策思考 |
| `Description.Soul` / `Identity` | **人格 / 身份** —— 性格与角色 |
| `Description.Skills` | **经验技能** —— 会做的事 |
| `Description.SystemTools` | **随身工具** —— 笔记本 / IDE |
| `Description.McpList` | **协作能力** —— 接外部系统的本事 |
| `Session` | **当下思考记录** —— 这次对话的脑中状态 |
| `McpHandles` | **启动中的工具进程** —— 跑着的 MCP server |
| `DisposeAsync` | **下班关电脑** —— 释放资源 |

### `ModuleInstance` = 一个办公位

| 字段 | 类比 |
|------|------|
| `WorkspaceRoot` | **办公位位置** —— 哪间办公室哪张桌子 |
| `Description.Metadata` | **工作资料 + 操作说明** —— 贴在墙上的规章 |
| `Description.Workflows` | **工作流程** —— 标准作业流程清单 |
| `Description.Tools` | **办公设备** —— 打印机 / 扫描仪 / 专用屏 |
| `Description.McpList` | **接入业务系统** —— 连企业 ERP / CDN 控制台 |
| `Description.Owners` | **工位负责人** —— 开发 + 审计 |
| `ActivatedByTaskId` | **这次工单** —— 派给本工位的活儿 |

### 关键差别：主动 vs 被动

| | 人（Agent） | 办公位（Module） |
|--|------------|-----------------|
| 主动性 | **主动**：有大脑会思考 | **被动**：等人来用 |
| 资源生命周期 | 重——启动 MCP / 维护 Session / 需 Dispose | 轻——纯激活记录，无运行态 |
| 谁能离开 | 下班关电脑（DisposeAsync） | 工位不关电脑，等下一个人坐 |

### Task = 工单

`Task = 派 [某个人] 去 [一个或多个办公位] 干 [某件事]`

- 人**带着**自己的经验/工具/MCP（跟人走）到办公位
- 用办公位的**资料 / 设备 / 接入系统**（跟工位走）完成工单
- 同一个人坐不同办公位 → 经验通用 + 工位资源不同
- 同一个办公位被不同人坐 → 工位资源通用 + 经验不同

**为什么这个类比关键**：
1. **解释了"工具双重来源"的合理性**——人带笔记本，工位有打印机，两个都用很自然
2. **解释了"为什么 MCP 跨维度共享"**——MCP 协议本身就是"接入某个系统"，不论这个能力是人会的（git）还是工位接好的（公司 CRM）
3. **解释了"为什么 AgentInstance 重而 ModuleInstance 轻"**——人有大脑要维护，工位是死的
4. **解释了"为什么 Skills 在两侧都有"**——人有经验技能，工位有作业流程，都是"知道怎么做某件事"

## 本轮整体砍 / 留

| 类别 | 模块 | 决定 |
|------|------|------|
| **完全砍掉** | `SystemTools/` | Files/Search/Web 交给 Microsoft.Extensions.AI AIFunction 生态；Shell 因 net8-only 暂搁置 |
| **完全砍掉** | `Kernel/ExecutionUnit/` | 上轮已 deprecated，本轮物理删 |
| **完全砍掉** | `Kernel/TaskRunner/` | 30 行胶水折入 FlowGraph 的 CbimTaskExecutor（Microsoft Workflows Executor）|
| **大幅瘦身** | `Memory/` | 退化为 MemoryEntry 扁平 JSON CRUD + 将来挂 Microsoft VectorStore 的连接点；短期记忆 / Compaction / 向量检索全部交 Microsoft |
| **大幅瘦身** | `AgentSystem/` | 保留 AgentDescription schema + OpenInstance 装配胶水 + Session 写侧；AIAgentBuilder / ChatClientAgent / AgentThread / AgentSession 由 Microsoft 接管 |
| **大幅瘦身** | `Channel/` | 退化为 Microsoft `AgentSession` 的薄封装 |
| **重写** | `Kernel/FlowGraph/` | 基于 Microsoft.Agents.AI.Workflows，CBIM 仅写 CbimTaskExecutor + 业务 Workflow 装配类 |
| **重写** | `Kernel/TaskScheduler/` | 仅 CbimTask 不可变 record |
| **保留** | `Kernel/ContextProviders/` | 三 AIContextProvider 实现（CBIM 上下文 → Microsoft 抽象）|
| **保留** | `Workspace/` | CBIM 独有业务模块知识图谱 |
| **解耦** | `Storage/` | root path 注入，去 Unity 耦合 |

## CBIM 真正不可替代的东西

经过本轮裁决，CBIM 在 Unity 侧只写以下业务独有内容：

1. **CbimTask 三元组**（who/where/what）—— CBIM 业务词汇
2. **业务 Workflow 装配**（ChatWorkflow / DispatchWorkflow / ArchExecWorkflow 等）—— CBIM 业务拓扑
3. **三个 AIContextProvider 实现**（Workspace / Memory / Session）—— CBIM 上下文桥
4. **AgentDescription schema + OpenInstance 装配**—— CBIM 能力定义与装配胶水
5. **MemoryEntry 扁平 JSON 后端**—— CBIM 中期记忆条目（distill 后事实）
6. **ModuleDescription 读侧 + reindex**—— CBIM 业务模块知识图谱
7. **Channel 薄封装**—— Unity 场景层的 OpenChannel/SendAsync 调用约定
8. **Storage 文件 IO 原语**—— 跨平台原子写

## Children

| 子模块 | 一句话职责 | 层级 | 状态 |
|--------|----------|------|------|
| `Storage/` | IO 原语（root 注入）| 最底层 | spec |
| `Memory/` | MemoryEntry 才平 JSON CRUD（M 服务层瘦身后）| 服务层 | spec |
| `AgentSystem/` | AgentDescription（Id+Name+Soul+Identity + Skills/SystemTools/McpList 三能力扩展）+ OpenInstance 装配 + Session 写；子模块三足鼎立：**Skills/** + **StandardTools/** + **Mcp/**（C 服务层 + 能力维度扩展三源）| 服务层 | spec |
| `Workspace/` | ModuleDescription（业务工作流程 + 领域知识 + McpList 业务操作接入点）+ 实例读侧（B 服务层）| 服务层 | spec |
| `Kernel/` | 驱动层 parent：TaskScheduler + FlowGraph + ContextProviders 3 业务胶水 | 驱动层 | spec |
| `Channel/` | 入口层：Microsoft AgentSession 薄封装 + SendAsync 调用约定 | 入口层 | spec |
| `AgenticOS.cs` | 组合根门面 | 门面 | stub |

**已废弃**（代码已物理删）：`SystemTools/`、`Kernel/ExecutionUnit/`、`Kernel/TaskRunner/`、AgentSystem 下原独立的 `McpAdapter/`（本轮重命名并位于 `Mcp/` 三足鼎立中）。

**本轮重要增量**（三大基础能力抽象顶层化·代码已落地）：

- `Tools/`（顶层）——含 `ToolDescriptor`（原 `SystemTool` 重命名） + `Tools/Standard/` 子模块承载内置工具家族实现（Files / Search）。整体从 `AgentSystem/StandardTools/` 提升为顶层。
- `Skills/`（顶层）——含 `SkillDescriptor`（原 `Skill` 重命名）。从 `AgentSystem/Skills/` 提升为顶层。
- `Mcp/`（顶层）——含 `McpDescriptor` abstract + `StdioMcpDescriptor` / `HttpMcpDescriptor` + `McpTransportKind` 枚举。从 `AgentSystem/Mcp/` 提升为顶层。

三顶层模块**同为「扩展能力」基础抽象**、**跨维度共享**（agent 和 module 都各自引用三者列表）、**同被 AgentDescription / ModuleDescription 三字段并列引用**——仅扩展形态不同。

**理由**：上轮把 Skill / SystemTool / Mcp 放在 `AgentSystem/` 子目录下导致维度错位——业务侧（Workspace）想用 McpDescriptor 时只能跨维度反向引用能力侧子模块，语义错位。本轮顶层化后两个维度都平等引用顶层模块，对称清晰。

**跨维度共享**：`McpDescriptor` 同时被 `AgentDescription.McpList`（能力维度）与 `ModuleDescription.McpList`（业务维度）引用——CBIM 内唯一跨维度共享抽象。Workspace 反向依赖 `CBIM.Mcp`（单向，符合 C3）。

## Child Relationships

```mermaid
flowchart TD
    AOS["AgenticOS\n(组合根 · 装配)"]
    CH["Channel\n(入口 · AgentSession 薄封装)"]

    subgraph K["Kernel（3 业务胶水子模块）"]
        TS["TaskScheduler\n(CbimTask record)"]
        FG["FlowGraph\n(Microsoft Workflows 适配 +\nCbimTaskExecutor)"]
        CP["ContextProviders\n(CBIM 上下文桥)"]
        FG --> TS
        FG --> CP
    end

    MSAF["Microsoft.Agents.AI +\n.Workflows + Extensions.AI +\n.Mcp （IChatClient / AIAgent / AgentSession /\nWorkflow / AIContextProvider / AIFunction /\nMcpClient）"]

    subgraph ASG["AgentSystem（C 能力服务层）"]
        AS["AgentSystemService\n(AgentDescription 含\nSkills / SystemTools / McpList +\nOpenInstance + Session 写)"]
        SK["Skills/\nSkill"]
        ST["StandardTools/\nSystemTool + AIFunction 家族"]
        MC["Mcp/\nMcpDescriptor（abstract）\n+ Stdio/Http 子类\n+ McpTransportKind"]
    end

    Mem["Memory\n(MemoryEntry CRUD)"]
    WS["Workspace\n(ModuleDescription:\nDna + Workflows + McpList)"]

    Storage["Storage\n(IO 原语 · root 注入)"]

    AOS --> CH
    CH --> AS
    CH --> FG
    CH -. 调 AgentSession / RunAsync .-> MSAF

    FG -. 基于 .-> MSAF
    FG --> AS
    CP --> Mem
    CP --> WS
    CP --> AS
    CP -. 实现 AIContextProvider .-> MSAF

    AS -. 装配 AIAgent .-> MSAF
    AS --> Storage
    AS -- 读 Skills --> SK
    AS -- 读 SystemTools --> ST
    AS -- 读 McpList --> MC
    AS -. CreateFamilies .-> ST

    Mem --> Storage
    WS --> Storage
    WS -- 跨维度共享 McpDescriptor --> MC
    ST --> Storage
    ST -. AIFunction .-> MSAF
    MC -. Microsoft.Agents.AI.Mcp .-> MSAF

    classDef base fill:#e0f0ff;
    class Storage base;
    classDef cap fill:#fffbe6;
    class SK,ST,MC cap;
```

依赖单调：`AgenticOS → Channel → {Kernel.FlowGraph, AgentSystem(+Skills, +StandardTools, +Mcp)} → {Memory, Workspace, Storage, Microsoft 包}`。跨服务层依赖仅一条：`Workspace → AgentSystem.Mcp`（跨维度共享 `McpDescriptor` 抽象）。无反向边。

**本轮重要增量**（能力维度三大扩展抽象平级化）：

- AgentSystem 下由上轮两位（StandardTools + McpAdapter）伸展为三位**平级**：Skills + StandardTools + Mcp。
- `McpAdapter/` 重命名为 `Mcp/`（与 Skills / StandardTools 命名风格对齐——都是「该抽象的家」）。
- `McpDescriptor` 抽为 abstract 基类，加 `StdioMcpDescriptor` / `HttpMcpDescriptor` 子类 + `McpTransportKind` 枚举。
- `Workspace.ModuleDescription` 增 `McpList` 字段，业务操作接入点从 `ModuleDna` 迁出。`ModuleDna` 退化为纯知识载体。
- McpServerAdapter 装配胶水本轮未随代码落地——能力侧 OpenInstance / 业务侧 Workflow 各自直接调 Microsoft.Agents.AI.Mcp client。
- AgentSystem 读 AgentDescription.mcp_servers 名字串 + IMcpRegistry 二级查棅全部取消——直接持 `McpDescriptor` 实例列表。

## 三大服务系统（M / C / B）

| 缩写 | 系统 | 模块 | 本轮瘦身后职责 |
|------|------|------|---------------|
| **M** | 记忆系统 | `Memory/` | MemoryEntry 扁平 JSON CRUD；短期归 Microsoft AgentThread；向量挂 Microsoft VectorStore |
| **C** | 能力系统 | `AgentSystem/` | AgentDescription schema + OpenInstance 装配 + Session 写；AIAgentBuilder / AgentSession 由 Microsoft 接管 |
| **B** | 业务模块 | `Workspace/` | ModuleDescription 读侧 + 后续写侧；Microsoft 不提供等价物 |

三大系统：互不依赖；都直接依赖 Storage；都不依赖 Kernel；都不依赖 Microsoft 包以外的同级模块。

## 铁律

1. **三大服务层互不依赖**——跨系统联动走 Kernel.FlowGraph + ContextProviders。
   - 服务层引用基础能力顶层模块（`CBIM.Tools` / `CBIM.Skills` / `CBIM.Mcp`）是合法依赖——不算服务层互相依赖。
2. **三大服务层都直接依赖 Storage**——是各自被动存储的唯一 IO 依赖。
3. **CBIM 不在 Kernel 层发明任何抽象**——`IChatClient` / `AIAgent` / `Workflow` / `Executor` / `AIContextProvider` / `AIFunction` / `McpClient` 全部直接采用 Microsoft。
4. **不造 IO 工具轮子**——文件 / 搜索 / 网页交 Microsoft.Extensions.AI AIFunction 生态；MSAI 未补齐期由 `Tools/Standard/` 顶层子模块暂补。
5. **不造业务工作流引擎**——Microsoft.Agents.AI.Workflows 接管，CBIM 仅写业务拓扑装配。
6. **不造记忆轮子**——Microsoft 已有 ChatHistoryProvider / Compaction / VectorData；CBIM 仅留 MemoryEntry 才平 JSON 后端。
7. **不造 Agent 装配轮子**——Microsoft `AIAgentBuilder` 接管；CBIM 仅写 OpenInstance 胶水。
8. **不造交互界面轮子**——Microsoft `AgentSession` 接管；Channel 是薄封装。
9. **Channel 只依赖 AgentSystem + Kernel.FlowGraph**——不直接访问 Memory / Workspace / Storage / Microsoft 包。
10. **AgenticOS 仅装配**——不直接驱动。
11. **不造 MCP 客户端协议轮子**——`Microsoft.Agents.AI.Mcp` 接管；CBIM `Mcp/` 顶层模块仅定义 `McpDescriptor` 抽象与传输枚举；启 server / 包 AIFunction / 关 的胶水在装配侧（OpenInstance / 业务 Workflow）直接使用 Microsoft client。
12. **MCP 抽象顶层共享，但连接目标必须 = task.Where**（关键维度交叉点）——MCP 抽象物理属于 `CBIM.Mcp` 顶层模块（跨维度共享），能力侧 / 业务侧都用同一抽象；但启动时必须连到 `task.Where` 指向的业务实例工作区根。能力侧装配点是 OpenInstance，workspaceRoot 由 `OpenInstanceOptions.TaskWhere` 透传。
13. **`McpDescriptor` 是 CBIM 唯一跨维度共享抽象**（本轮新增·关键）——`AgentDescription.McpList: IReadOnlyList<McpDescriptor>` 与 `ModuleDescription.McpList: IReadOnlyList<McpDescriptor>` 同一抽象、同类型、同符号。
    - **语义不同**：能力侧跟人走（agent 自带）；业务侧跟业务走（module 接入点）。
    - **装配位置不同**：能力侧在 OpenInstance；业务侧在 Kernel.FlowGraph / ContextProviders。
    - **依赖方向严格单向**：`Workspace → AgentSystem.Mcp`，不反向。
    - **仅限 `McpDescriptor`**：其余抽象（Skill / SystemTool）**不**跨维度；能力侧三子模块中仅 `Mcp/` 被 Workspace 引用。
    - **共享不代表耦合**：同一「外部端点」抽象被两维度独立使用，业务侧不感知能力侧使用、能力侧不感知业务侧使用。
14. **能力维度三大扩展抽象平级**（本轮新增）——Skills / StandardTools / Mcp 三子模块同层级、同装配点、同生命周期、同被 AgentDescription 三字段并列引用；平级三足鼎立，三者互不引用。

## 能力 / 业务对偶铁律（本轮重申，修正上一轮维度错位）

15. **工具归能力，流程归业务**——金样铁律。
    - **能力维度（Agent）** 责任：Skills（语义）+ SystemTools（AIFunction）+ McpList（外部端点）+ 专精领域。schema 落 `AgentDescription`（C# 类实例化，不是 frontmatter yaml）。
    - **业务维度（Module）** 责任：Dna（知识载体）+ Workflows（流程声明）+ McpList（业务操作接入点）。schema 落 `ModuleDescription`。
    - `ModuleDescription` 不持工具声明、不持 sandbox 配置。
    - `AgentDescription` 不持业务流程、不持 module 路径。
    - **例外一句话**：MCP 接入点在能力侧与业务侧都可被声明——跨维度共享 `McpDescriptor` 抽象，但语义归属不同（agent 自带 vs module 接入点）。共享抽象不跨维度耦合。
16. **工具动态性通过 Task.Who 实现**——`Task = Agent + ModuleList + Requirement`；同一任务选不同 agent → 自带不同工具集，间接实现「按需装配」。`Task.Where` 仅为业务上下文（+ MCP 启动 workspaceRoot），不参与工具装配选择。
17. **OpenInstance 是能力装配唯一胶水点**——读 `AgentDescription.Skills` / `SystemTools` / `McpList` 三能力源 → 拼接 → 注入 `AIAgentBuilder`。仅在本次 AIAgent 生命周期生效，无全局注入。
   - Skills: AgentSkillsProvider 注入 LLM 上下文（未来落地）。
   - SystemTools: `StandardToolsService.CreateFamilies` 按 per-agent 沙盒返回 AIFunction。
   - McpList: `Microsoft.Agents.AI.Mcp` client 启 server + 握手 + tools/list + 包 AIFunction。

## Agent 裂变铁律（本轮新增，防「全能 agent」维度贪吃）

18. **Agent 必须专精**——不做 `ProgrammerAgent` 一个吃全宇宙，而是 `UnityProgrammerAgent` / `BlenderArtistAgent` / `BackendProgrammerAgent` 各管一摊。
19. **三能力源广度超阈值 → 裂变**——阈值与裂变范式详 `AgentSystem/.dna/module.md`「裂变规则」一节。
    - `SystemTools` 家族 > 4 / `McpList` server > 3 / `Skills` > 8 / 专精领域跨 2+ 主领域 / `Soul` > 3000 token——任一命中即裂。
    - HR 主持裂变审议与执行（hr_agents skill），architect 提供阈值与架构原则。
20. **通用 agent 轻、专精 agent 允宽但需单领域聚焦**——通用角色（coordinator / hr / architect / auditor）SystemTools ≤ 2、Skills ≤ 4、McpList ≤ 1；专精角色 SystemTools ≤ 4、Skills ≤ 8、McpList ≤ 3 且 capabilities 单领域。

## Origin Context

CBIM v2 Unity 移植的演进线：

1. **最初**：Storage / Memory / Kernel 三模块。
2. **拆出 AgentRegistry / Dna**——长期记忆同级。
3. **拆出 AgentSystem / Workspace**——对齐三大系统。
4. **合并 AgentRegistry → AgentSystem，Dna → Workspace**——避免无意义层级。
5. **拆出 Channel**——入口语义显式化。
6. **Channel 重命名**——Session 下沉为 AgentSystem 内部概念。
7. **Kernel 升级为可插拔架构**（KernelExtension）——这一步随后被否。
8. **新增 SystemTools**——IO 工具收敛（这一步随后被否）。
9. **Kernel 重构为 Microsoft.Agents.AI 之上的 4 业务胶水**。
10. **顶层精简**：彻底贯穿不造轮子。SystemTools 砍、TaskRunner 砍、FlowGraph 基于 Microsoft Workflows、Memory/AgentSystem/Channel 大幅瘦身。
11. **补 IO 工具**：发现 MSAI Tools 几乎缺位，新增 StandardTools 子模块——**当时误放在 `Workspace/` 下**。
12. **上轮维度修正**：StandardTools 从 `Workspace/` 迁到 `AgentSystem/` 下；`ModuleDescription.standard_tools` / `external_mcp_servers` 字段删除；`AgentDescription.tools` + `agent_extension_clis` 字段新增；Agent 裂变铁律入能力维度顶层设计。
13. **上轮增量 MCP 集成**：新增 `AgentDescription.mcp_servers` 名字串 + `OpenInstanceOptions.TaskWhere`；新增 `AgentSystem/McpAdapter/` 子模块。
14. **本轮三足鼎立 + 代码落地 + 跨维度共享**（本轮重要调整）：
    - **能力维度三大扩展抽象平级子模块化**——`Skill` 从裸露 `CBIM.AgentSystem` 迁到 `Skills/`；`McpAdapter/` 重命名为 `Mcp/` 且抽象重组；StandardTools 位置不变。三者同层级三足鼎立。
    - **`McpDescriptor` 抽为 abstract 基类**——拆 `StdioMcpDescriptor` / `HttpMcpDescriptor` 两子类 + `McpTransportKind` 枚举。原 record 形态升为 abstract class。
    - **AgentDescription 以 C# 类实例化**（不是 frontmatter yaml 字串）：`Id` / `Name` / `Soul` / `Identity` + `Skills` / `SystemTools` / `McpList` 三能力字段。上轮的 `tools` / `agent_extension_clis` / `mcp_servers` 名字串列表、`IMcpRegistry` 二级表全部取消。
    - **跨维度共享 `McpDescriptor`**：`Workspace.ModuleDescription.McpList: IReadOnlyList<McpDescriptor>` 新增；`ModuleDna.Protocol` 字段删（代码已落地）。业务操作接入点从 DNA 迁到 ModuleDescription。`ModuleDna` 退化为纯知识载体（LocalModuleDna FilePath + RemoteModuleDna Endpoint+AuthToken）。
    - **McpServerAdapter / McpServerHandle 装配胶水本轮未随代码落地**——能力侧 OpenInstance / 业务侧 Workflow 各自直接调 Microsoft.Agents.AI.Mcp client。Mcp 子模块仅供类型与传输枚举，胶水后续如出现重复再抽取。

每一步的共同主线是「凡公共抽象交出去 / 凡 CBIM 独有业务保留」。补辩主线：

- 上轮加一条：**「凡某个能力伴随某个维度出现，不等于该能力应在该维度描述」**。维度归属看「谁发起」不看「谁伴生」。
- **本轮加一条**：**「同一抽象被多维度调用 ≠ 多维度耦合」**。共享 `McpDescriptor` 是 CBIM 唯一跨维度共享点；共享不等于耦合——两个维度独立调用同一抽象，依赖方向仍严格单向（`Workspace → AgentSystem.Mcp`）。

## Emergent Insights

1. **「不造轮子」是 C6（稳定抽象）在生态层面的应用**——Microsoft.Agents.AI 是业界连续迭代的公共抽象，CBIM 重造永远落后。CBIM 真正的价值在「CBIM 独有的业务词汇 + 业务拓扑 + 上下文桥」。
2. **能力 / 业务对偶让 CBIM 不再陷入「agent 全能化」误区**——业界常见做法是把工具 / MCP / 记忆全部挂到一个「万能 agent」上，导致 agent 越长越胖且职责混乱。CBIM 的金样铁律是**「工具归能力维度 + agent 必须专精」**：agent 描述「我是谁 + 我拿哪些工具」，业务 module 描述「我是什么业务流程 + 领域知识」；agent 肥了就裂变成专精多个，不让单 agent 多领域贪吃。
3. **「动态工具注入」的本质是 Task-期 × 同一 agent 生命周期 × 无全局**——传统做法是启动时全局注入、绑定 agent、全程生效。CBIM 是装配时按 AgentDescription 注入、绑定本次 AIAgent 生命周期、RunAsync 后释放。「同一 task 选不同 agent 则工具集不同」是“动态”的间接体现。三重收益：agent 只看见自身应有工具（上下文窗口干净）；agent 类型自带工具集由设计者在 `.claude/agents/` 声明（不需改调度代码）；不同任务选不同 agent 自动获得不同工具（无全局污染）。
4. **三大服务系统对称性进一步增强**——三者都退化为「业务独有 schema + 极薄 CRUD + 可选挂 Microsoft 后端」结构；AgentSystem / Workspace 还共享「Description（类型）+ Instance（实例）」二元结构。
5. **Kernel 子树缩到 3 个胶水模块**——CbimTask（词汇）+ FlowGraph（业务拓扑装配 + Task 期调度 RunAsync）+ ContextProviders（上下文桥）。再无第四个理由存在的子模块。
6. **Channel + AgentSession 关系类比终端 + 终端历史**——Channel 是 TTY，AgentSession 是 TTY 的 history buffer；进程 = AIAgent；进程日志 = AgentSystem 内 Session。四层显式拆开。
7. **预计 Unity 侧 CBIM 代码量大幅下降**——本轮裁决等于把 CBIM 在 Unity 侧的工程量降至「业务独有部分」，从 4 个数量级缩到3 个。
8. **维度错位是架构师日常陷阱**（上轮新增）——`standard_tools` 看起来与 module 伴生（「这个 module 上需要读文件」），但实际上「读文件」能力是调用者（agent）的能力。识别原则：**「谁发起该能力」才是 schema 归属的右答，不是「该能力伴随谁出现」**。
9. **能力维度三足鼎立后能看明扩展轴**（本轮新增）——Skills / StandardTools / Mcp 三个平级子目录在 AgentSystem 下并列，看一眼就明「agent 能多会一手」的三条路径，互不交叉互不覆盖。上轮 Skill 裸露 / McpAdapter 孤为子模块的不对称状态被拉齐——架构对称设计以对称语义齐齐列。
10. **跨维度共享抽象是「抽象复用」而非「耦合」**（本轮新增）——`McpDescriptor` 同时被 AgentDescription 与 ModuleDescription 使用，不意味能力维度与业务维度耦合——是同一抽象被两个维度独立调用。跨维度共享严格限定 `McpDescriptor`，其余抽象（Skill / SystemTool）不跨维度；依赖方向严格单向（`Workspace → AgentSystem.Mcp`）保证不引入反向边。

## Implementation Sequence（知识 → 代码）

按稳定性自底向上：

1. **Storage**（root 注入构造器 + 原子写 + JSON）。
2. **Memory**（MemoryEntry + 扁平 JSON CRUD + 关键词 Query）。
3. **Workspace**（ModuleDescription 读侧 + reindex）。
4. **AgentSystem**（AgentDescription schema + 实例索引；OpenInstance 装配在第 7 步前 stub）。
5. **Kernel/TaskScheduler**（CbimTask record）。
6. **Kernel/ContextProviders**（三 Provider 实现）。
7. **Kernel/FlowGraph**（CbimTaskExecutor + ChatWorkflow 装配 + AgentSystem.OpenInstance 实装）。
8. **Channel**（host Microsoft AgentSession + SendAsync）。
9. **AgenticOS** 组合根——OpenChannel + SendAsync 便捷封装。
10. **后续切片**：DispatchWorkflow / ArchExecWorkflow / TaskWorkspace / 写侧 API / Shell（如 .NET 升级）。

## Non-Goals（本轮）

- **不重新引入** LlmEngine / Pipeline / INode / IFlowGraph / IKernelEngine / ITaskRunner / IFileTools / IShellTools 任何抽象。
- **不自写** 业务工作流引擎、工具调用闭环、会话压缩、Yield/Resume 机制、IO 工具层。
- **不引入 MCP 服务端**——Unity 进程内直调 Microsoft。
- **不发治理循环代码**——本轮仅业务执行。
- **AgentSystem / Workspace 不发写侧**——Unity 侧暂走 Python `dna_*` / `agent_*` MCP 工具。
- **AgentDescription `chat_client_config` schema 详细演进**留后续切片。
- **Shell AIFunction**——Microsoft Tools.Shell 当前 net8-only，本轮 Unity 主线接受「无 Shell」约束。
- **Python 侧是否同步 Microsoft.Agents.AI**——Python architect 后续话题。

