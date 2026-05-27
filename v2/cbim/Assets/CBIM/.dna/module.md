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
| **能力（Capability）** | Agent —— 具有特定领域能力的「个体」 | `AgentSystem/`（C 维度） | **工具 + skill + 专精领域** | `AgentDescription`（含 tools / agent_extension_clis）+ `AgentInstance` |
| **业务（Business）** | Module —— 特定业务类型的「工作区」 | `Workspace/`（B 维度） | **工作流程 + 领域知识** | `ModuleDescription` + `ModuleInstance` |
| **记忆（Memory）** | 跨能力跨业务的事实 / 决策 / 原则沉淀 | `Memory/`（M 维度） | 事实/决策 entries | `MemoryEntry` 扈平 JSON |

**对偶的核心约束**：

- 能力维度回答「**谁**能动 + 拿什么工具动」——工具是 agent 的能力构成。
- 业务维度回答「在**什么样的工作区**里动、能动**什么**（业务流程 + 领域知识）」——不持工具。
- 一件任务由二者交叉成立——`Task = Agent + ModuleList + Requirement`。三大服务系统互不依赖，跨系统协同走 Kernel.FlowGraph + ContextProviders。

**维度错位的反面教材**：上一轮把工具声明放在 `ModuleDescription.standard_tools`，本轮推翻——详「能力 / 业务对偶铁律」节。记住：「看起来与某维度伴生」 ≠ 「应在该维度 schema 内」。

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
| `Memory/` | MemoryEntry 扱平 JSON CRUD（M 服务层瘦身后）| 服务层 | spec |
| `AgentSystem/` | AgentDescription（含 tools / agent_extension_clis / mcp_servers 三类工具能力声明）+ OpenInstance 装配 + Session 写 + **StandardTools 子模块** + **McpAdapter 子模块**（C 服务层 + 能力维度工具三源）| 服务层 | spec |
| `Workspace/` | ModuleDescription（业务工作流程 + 领域知识）+ 实例读侧（B 服务层）| 服务层 | spec |
| `Kernel/` | 驱动层 parent：TaskScheduler + FlowGraph + ContextProviders 3 业务胶水 | 驱动层 | spec |
| `Channel/` | 入口层：Microsoft AgentSession 薄封装 + SendAsync 调用约定 | 入口层 | spec |
| `AgenticOS.cs` | 组合根门面 | 门面 | stub |

**已废弃**（下次代码切片物理删）：`SystemTools/`、`Kernel/ExecutionUnit/`、`Kernel/TaskRunner/`

**本轮增量**（MCP 集成）：AgentSystem 下新增 `McpAdapter/` 子模块——能力维度的「工具来源三并列」装配齐（StandardTools / CLI / MCP server）；AgentDescription 增 `mcp_servers` 字段。**完全保留上轮「工具归能力维度」裁决；Workspace 仍不持任何工具声明。**

## Child Relationships

```mermaid
flowchart TD
    AOS["AgenticOS<br/>(组合根 · 装配)"]
    CH["Channel<br/>(入口 · AgentSession 薄封装)"]

    subgraph K["Kernel（3 业务胶水子模块）"]
        TS["TaskScheduler<br/>(CbimTask record)"]
        FG["FlowGraph<br/>(Microsoft Workflows 适配 +<br/>CbimTaskExecutor)"]
        CP["ContextProviders<br/>(CBIM 上下文桥)"]
        FG --> TS
        FG --> CP
    end

    MSAF["Microsoft.Agents.AI +<br/>.Workflows + Extensions.AI +<br/>.Mcp　(IChatClient / AIAgent / AgentSession /<br/>Workflow / AIContextProvider / AIFunction /<br/>McpClient)"]

    subgraph ASG["AgentSystem（C 能力服务层）"]
        AS["AgentSystemService<br/>(AgentDescription 含 tools /<br/>agent_extension_clis / mcp_servers +<br/>OpenInstance + Session 写)"]
        ST["StandardTools<br/>(AIFunction 家族 + 沙盒)"]
        MCP["McpAdapter<br/>(MCP server 启停 + AIFunction 包装)"]
    end

    Mem["Memory<br/>(MemoryEntry CRUD)"]
    WS["Workspace<br/>(ModuleDescription 读侧 ·<br/>工作流程 + 领域知识)"]

    Storage["Storage<br/>(IO 原语 · root 注入)"]

    AOS --> CH
    CH --> AS
    CH --> FG
    CH -.调 AgentSession / RunAsync.-> MSAF

    FG -.基于.-> MSAF
    FG --> AS
    CP --> Mem
    CP --> WS
    CP --> AS
    CP -.实现 AIContextProvider.-> MSAF

    AS -.装配 AIAgent.-> MSAF
    AS --> Storage
    AS -. 读 AgentDescription.tools .-> ST
    AS -. 读 AgentDescription.mcp_servers .-> MCP
    AS -. CreateFamilies .-> ST
    AS -. StartAsync(name, task.Where) .-> MCP
    Mem --> Storage
    WS --> Storage
    ST --> Storage
    ST -.AIFunction.-> MSAF
    MCP -.MCP client.-> MSAF
    MCP --> Storage

    classDef base fill:#e0f0ff;
    class Storage base;
    classDef cap fill:#fffbe6;
    class ST,MCP cap;
```

依赖单调：`AgenticOS → Channel → {Kernel.FlowGraph, AgentSystem(+StandardTools, +McpAdapter)} → {Memory, Workspace, Storage, Microsoft 包}`，无反向边。

**本轮增量**（MCP 集成）：

- AgentSystem 下新增 `McpAdapter` 子模块（与 StandardTools 同位阶，都是「某种工具来源」。
- AgentSystem 读 AgentDescription.mcp_servers 后调 McpAdapter.StartAsync（胶水在 OpenInstance）。
- McpAdapter 依赖 Microsoft.Agents.AI.Mcp（依赖边仅下游，不反向取 AgentSystem）。
- 能力维度内工具来源三并列（StandardTools / CLI / MCP server）装配点统一在 OpenInstance。

## 三大服务系统（M / C / B）

| 缩写 | 系统 | 模块 | 本轮瘦身后职责 |
|------|------|------|---------------|
| **M** | 记忆系统 | `Memory/` | MemoryEntry 扁平 JSON CRUD；短期归 Microsoft AgentThread；向量挂 Microsoft VectorStore |
| **C** | 能力系统 | `AgentSystem/` | AgentDescription schema + OpenInstance 装配 + Session 写；AIAgentBuilder / AgentSession 由 Microsoft 接管 |
| **B** | 业务模块 | `Workspace/` | ModuleDescription 读侧 + 后续写侧；Microsoft 不提供等价物 |

三大系统：互不依赖；都直接依赖 Storage；都不依赖 Kernel；都不依赖 Microsoft 包以外的同级模块。

## 铁律

1. **三大服务层互不依赖**——跨系统联动走 Kernel.FlowGraph + ContextProviders。
2. **三大服务层都直接依赖 Storage**——是各自被动存储的唯一 IO 依赖。
3. **CBIM 不在 Kernel 层发明任何抽象**——`IChatClient` / `AIAgent` / `Workflow` / `Executor` / `AIContextProvider` / `AIFunction` / `McpClient` 全部直接采用 Microsoft。
4. **不造 IO 工具轮子**——文件 / 搜索 / 网页交 Microsoft.Extensions.AI AIFunction 生态；MSAI 未补齐期由 `AgentSystem/StandardTools/` 子模块暂补。
5. **不造业务工作流引擎**——Microsoft.Agents.AI.Workflows 接管，CBIM 仅写业务拓扑装配。
6. **不造记忆轮子**——Microsoft 已有 ChatHistoryProvider / Compaction / VectorData；CBIM 仅留 MemoryEntry 扱平 JSON 后端。
7. **不造 Agent 装配轮子**——Microsoft `AIAgentBuilder` 接管；CBIM 仅写 OpenInstance 胶水。
8. **不造交互界面轮子**——Microsoft `AgentSession` 接管；Channel 是薄封装。
9. **Channel 只依赖 AgentSystem + Kernel.FlowGraph**——不直接访问 Memory / Workspace / Storage / Microsoft 包。
10. **AgenticOS 仅装配**——不直接驱动。
11. **不造 MCP 客户端协议轮子**（本轮新增）——`Microsoft.Agents.AI.Mcp` 接管；CBIM `AgentSystem/McpAdapter/` 子模块仅写「启动 server 进程 + 连 task.Where + 包 AIFunction + 关」的胶水。
12. **MCP 归能力维度，但连接目标必须 = task.Where**（本轮新增·关键维度交叉点）——MCP server 是 agent 能力的一部分（能力维度 schema），但启动时必须连到 `task.Where` 指向的业务实例工作区根（业务维度目标）。两个维度在 MCP 启动这一刻交叉——这是「能力归能力，目标归业务」原则的唯一明显交点；装配点是 OpenInstance，workspaceRoot 由 `OpenInstanceOptions.TaskWhere` 透传。

## 能力 / 业务对偶铁律（本轮重申，修正上一轮维度错位）

11. **工具归能力，流程归业务**——金样铁律。
    - **能力维度（Agent）** 责任：工具（AIFunction）+ skill + 专精领域。schema 落 `AgentDescription`。
    - **业务维度（Module）** 责任：业务工作流程 + 领域知识。schema 落 `ModuleDescription`。
    - `ModuleDescription` 不持工具声明、不持 MCP 端点、不持 sandbox 配置。
    - `AgentDescription` 不持业务流程、不持 module 路径。
12. **工具动态性通过 Task.Who 实现**——`Task = Agent + ModuleList + Requirement`；同一任务选不同 agent → 自带不同工具集，间接实现「按需装配」。`Task.Where` 仅为业务上下文，不参与工具装配。
13. **OpenInstance 是能力装配唯一胶水点**——读 `AgentDescription.tools` + `agent_extension_clis` → per-agent 沙盒 → `StandardToolsService.CreateFamilies` → 注入 `AIAgentBuilder.Tools`。仅在本次 AIAgent 生命周期生效，无全局注入。

## Agent 裂变铁律（本轮新增，防「全能 agent」维度贪吃）

14. **Agent 必须专精**——不做 `ProgrammerAgent` 一个吃全宇宙，而是 `UnityProgrammerAgent` / `BlenderArtistAgent` / `BackendProgrammerAgent` 各管一摊。
15. **工具 / skill 广度超阈值 → 裂变**——阈值与裂变范式详 `AgentSystem/.dna/module.md`「裂变规则」一节。
    - tools 家族 > 4 / extension CLIs > 6 / capabilities 跨 2+ 主领域 / system_prompt > 3000 token / skills > 8——任一命中即裂。
    - HR 主持裂变审议与执行（hr_agents skill），architect 提供阈值与架构原则。
16. **通用 agent 轻、专精 agent 允宽但需单领域聚焦**——通用角色（coordinator / hr / architect / auditor）tools ≤ 2、CLIs ≤ 2；专精角色 tools ≤ 4、CLIs ≤ 6 且 capabilities 单领域。

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
12. **本轮维度修正**：StandardTools 从 `Workspace/` 迁到 `AgentSystem/` 下；`ModuleDescription.standard_tools` / `external_mcp_servers` 字段删除；`AgentDescription.tools` + `agent_extension_clis` 字段新增；Agent 裂变铁律入能力维度顶层设计。唯一意识形态调整作业、无代码量净增。

每一步的共同主线是「凡公共抽象交出去 / 凡 CBIM 独有业务保留」。本轮多一条：**「凡某个能力伴随某个维度出现，不等于该能力应在该维度描述」**。维度归属看「谁发起」不看「谁伴生」。

## Emergent Insights

1. **「不造轮子」是 C6（稳定抽象）在生态层面的应用**——Microsoft.Agents.AI 是业界连续迭代的公共抽象，CBIM 重造永远落后。CBIM 真正的价值在「CBIM 独有的业务词汇 + 业务拓扑 + 上下文桥」。
2. **能力 / 业务对偶让 CBIM 不再陷入「agent 全能化」误区**——业界常见做法是把工具 / MCP / 记忆全部挂到一个「万能 agent」上，导致 agent 越长越胖且职责混乱。CBIM 的金样铁律是**「工具归能力维度 + agent 必须专精」**：agent 描述「我是谁 + 我拿哪些工具」，业务 module 描述「我是什么业务流程 + 领域知识」；agent 肥了就裂变成专精多个，不让单 agent 多领域贪吃。
3. **「动态工具注入」的本质是 Task-期 × 同一 agent 生命周期 × 无全局**——传统做法是启动时全局注入、绑定 agent、全程生效。CBIM 是装配时按 AgentDescription 注入、绑定本次 AIAgent 生命周期、RunAsync 后释放。「同一 task 选不同 agent 则工具集不同」是“动态”的间接体现：动态发起点是 task 对 agent 的选择，不是全局注入。三重收益：agent 只看见自身应有工具（上下文窗口干净）；agent 类型自带工具集由设计者在 `.claude/agents/` 声明（不需改调度代码）；不同任务选不同 agent 自动获得不同工具（无全局污染）。
4. **三大服务系统对称性进一步增强**——三者都退化为「业务独有 schema + 极薄 CRUD + 可选挂 Microsoft 后端」结构；AgentSystem / Workspace 还共享「Description（类型）+ Instance（实例）」二元结构。
5. **Kernel 子树缩到 3 个胶水模块**——CbimTask（词汇）+ FlowGraph（业务拓扑装配 + Task 期调度 RunAsync）+ ContextProviders（上下文桥）。再无第四个理由存在的子模块。
6. **Channel + AgentSession 关系类比终端 + 终端历史**——Channel 是 TTY，AgentSession 是 TTY 的 history buffer；进程 = AIAgent；进程日志 = AgentSystem 内 Session。四层显式拆开。
7. **预计 Unity 侧 CBIM 代码量大幅下降**——本轮裁决等于把 CBIM 在 Unity 侧的工程量降至「业务独有部分」，从 4 个数量级缩到3 个。
8. **维度错位是架构师日常陷阱**（本轮新增）——`standard_tools` 看起来与 module 伴生（「这个 module 上需要读文件」），但实际上「读文件」能力是调用者（agent）的能力。识别原则：**「谁发起该能力」才是 schema 归属的右答，不是「该能力伴随谁出现」**。同一 module 被不同 agent 处理时所需工具差别极大——architect 只读，programmer 要写要调 CLI。这个现象在上一轮被忽视了，本轮修正。

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

