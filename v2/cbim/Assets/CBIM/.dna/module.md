---
name: cbim-unity-agentos
owner: architect
description: CBIM Agent OS · Unity 原生 C# 实现。本轮顶层重构（三层模型 v2）：六层架构 → 三层架构（基建层 / Agent / Workspace）。基建层 = 类型约定（Tool接口 / Skill接口 / MCP协议 / IMemoryService / FileBackend）；Agent 层 = 虚拟人代理（多个脑区共享一份 Memory 实例 + Tool/Skill/MCP 集合）；Workspace 层 = 工作区 / 项目（模块树 + 模块对象，模块持自身 MCP/Skill 实例）。本轮仅修订架构与 .dna 层，代码迁移（Memory 接口抽取 / AgentSystem → Agent 重命名 / Workspace 业务 Skill+MCP 接线）下切片处理。
keywords: []
dependencies: []
status: spec
---
## Positioning

CBIM Agent OS 的 Unity 原生 C# 实现。本模块是组合根，自身**不承载任何业务逻辑**——只做装配。

**本轮顶层重构（v2 三层模型）**：把之前的「6 层架构（调度/引擎/业务/能力/基座/扩展）」收敛为**三层架构**——

```
基建层（Infrastructure Primitives）  类型约定 / 抽象接口 / 标准协议
   ↑
Agent 层（虚拟人代理）              人 = 多脑区共享一份 Memory + Tool/Skill/MCP 集合
   ↑
Workspace 层（工作区 / 项目）        模块树 + 模块对象（模块自身的 MCP / Skill 挂载点）
```

之前的六层并未消失——它们退化为「三层 + 横切关注点」的内部细分：调度（行为树）和外部 Agent 适配仍存在，但作为 Agent 层内部的子结构出现；不再被宣传为顶层概念。**真正的顶层心智模型只有三个名字：基建、Agent、Workspace**。

## CBIM 认知框架（顶层 mental model）

> **CBIM 是一个「复合 Agent」——一个拥有全知全能的人。**

| 隐喻 | CBIM 对应物 | 三层归属 |
|------|-------------|----------|
| **这个全能的人** | CBIM 整体（`AgenticOS` 装配根） | — |
| **大脑皮层 / 协调中枢** | 行为树调度（`Kernel/FlowGraph` + `Kernel/TaskScheduler`） | Agent 层内部 |
| **脑干 / 小脑 / 各专项脑区** | 内部各 Agent 实例 / 外部 Agent 句柄 | Agent 层 |
| **长期记忆** | Memory 实例（绑定 Agent） | 基建抽象（IMemoryService）+ Agent 持实例 |
| **工具与武器** | Tool 接口 / Skill 接口 / MCP 协议 | 基建（类型约定）+ Agent/Workspace 各自实例化 |
| **办公位 / 工作空间** | Module 模块对象 | Workspace 层 |
| **当下思考流** | AgentSession 运行态 | Agent 层（Microsoft AgentSession host） |

### 核心三定理（沿用不变）

1. **皮层定理（行为树 = 协调）**——复合 Agent 的跨脑区协作由行为树调度驱动；行为树边即「皮层突触」，不是 prompt 里的「请决定下一步」。
2. **脑区定理（子 Agent = ReAct）**——每个内部 Agent 只做 Reason-Act 自身循环，不调度其他子 Agent，不感知行为树。
3. **武器库定理（Tool / Skill / MCP = 共享标准 + 私有实例）**——**接口标准跨场景共享**（基建层），**实例集合各方独立持有**（Agent 持自己的 Tool/Skill/MCP 集合，Workspace 模块也持自己的 MCP/Skill 集合）。同一标准、不同实例——这是三层模型对原「跨维度共享抽象」的精确化。

### 命名收敛与新表达

| 旧表达 | 新表达 | 说明 |
|--------|--------|------|
| 「6 层架构」（调度/引擎/业务/能力/基座/扩展） | 「三层架构」（基建/Agent/Workspace） | 顶层心智收敛 |
| 「能力层 Tool/Skill/MCP」 | 「基建层类型约定 Tool/Skill/MCP」 | Tool/Skill/MCP 不是「能力」，是「能力的类型契约」 |
| 「引擎层 AgentSystem」 | 「Agent 层（原 AgentSystem 服务层）」 | 服务层名称仍叫 AgentSystem，但概念上承载「Agent = 虚拟人」语义 |
| 「业务层 Workspace」 | 「Workspace 层」 | 名字未变；本轮明确「模块也持自己的 MCP/Skill 实例」 |
| 「Memory 横切关注点」 | 「IMemoryService 基建接口 + Agent 持 Memory 实例」 | Memory 不再是全局服务，而是 per-Agent 实例 |

## 三层模型详解

### 基建层（Infrastructure Primitives）

基建层 = **类型契约 / 抽象接口 / 标准协议**。本层不承载任何业务行为；只定义「Agent 层和 Workspace 层共同遵守的标准」。

| 子模块 | 提供的类型契约 | 物理位置 |
|--------|---------------|----------|
| `Tools/` | `ToolDescriptor`——工具家族声明抽象 | 顶层模块 |
| `Skills/` | `SkillDescriptor`——技能 / 工作流描述抽象 | 顶层模块 |
| `Mcp/` | `McpDescriptor`（abstract + Stdio/Http 子类）——MCP server 接入点抽象 | 顶层模块 |
| `Memory/`（接口部分） | `IMemoryService`——记忆服务接口 + `MemoryEntry` 记录类型 | 顶层模块（接口） |
| `Memory/`（默认实现） | `FileMemoryBackend`——基于 FileBackend 的默认 IMemoryService 实现 | 顶层模块（实现） |
| `Storage/` | `FileBackend`——文件系统原语（原子写 / JSON / 路径解析） | 顶层模块 |

**基建层铁律：**

- 基建层模块**不依赖**任何 Agent 层 / Workspace 层模块——它是依赖图最稳定的底层。
- 基建层只定义类型与接口，**不持业务状态**（FileBackend 持有 root 路径不算业务状态；那是 IO 配置）。
- 基建抽象一旦定义稳定，Agent 层 / Workspace 层可自由派生具体实例；后续接入 Pinecone / 第三方 MCP server / 自定义工具家族都不需要改基建层。
- **Tool / Skill / MCP / Memory 四件套不再被叫做「能力层」**——它们是「能力的类型契约」。能力（具体的 Tool 实例集合）属于谁，看谁实例化谁。

### Agent 层（虚拟人代理）

Agent 层 = **「人」的能力**。一个 Agent 实例代表一个虚拟人代理，由以下五件事拼装：

```
Agent 实例 = {
   思维对象集合：封装 Microsoft AIAgent（多个 ChatClientAgent 共享 ↓ 下方 4 项资源）
   Memory 实例：实现基建 IMemoryService 接口
   Tool 集合：按基建 Tool 标准派生（per-Agent 独立实例集）
   MCP 集合：按基建 MCP 标准派生（per-Agent 独立实例集）
   Skill 集合：按基建 Skill 标准派生（per-Agent 独立实例集）
}
```

**思维对象集合 = 多脑区** —— 一个 Agent 内部可装配多个 Microsoft `AIAgent`（如 Reasoner + Critic + Summarizer），这些「脑区」**共享同一份** Memory / Tool / MCP / Skill 资源池。这是「复合 Agent 的脑区共用同一具身」的物理落地——人有左右脑，但记忆和身体是一份。

**Agent 层物理模块构成：**

| 子模块 | 一句话职责 | 状态 |
|--------|----------|------|
| `AgentSystem/` | **Agent 装配服务层**（旧名 AgentSystem，本轮明确语义为「Agent 层服务门面」）。包含 AgentDescription schema + 装配胶水 OpenInstance + Session 写侧。**目录名是否同步重命名为 `Agent/` 见「AgentSystem → Agent 重命名决策」节** | spec |
| `ExternalAdapter/` | 外部 Agent 引擎适配层（Claude Code / Cursor / Codex 三策略）——同样是 Agent 层的一支，只是「人」由外部引擎驱动 | spec |
| `Kernel/` | Agent 层的内部协调子结构（行为树调度 + ContextProviders）——皮层落在 Agent 层内部 | spec |
| `Channel/` | Agent 层入口（Microsoft AgentSession 薄封装） | spec |

**Agent 层依赖基建层**：AgentSystem 引用 `CBIM.Tools` / `CBIM.Skills` / `CBIM.Mcp` / `CBIM.Memory.IMemoryService`；不反向。

### Workspace 层（工作区 / 项目）

Workspace 层 = **「工位」+「工位上贴的规章」+「工位接的外部系统」**。

| 子模块 | 一句话职责 | 状态 |
|--------|----------|------|
| `Workspace/` | 模块树 + 模块对象（ModuleDescription / ModuleMetadata / ModuleOwners / 模块自身的 MCP & Skill 挂载点） | spec |

**模块对象的组成（本轮明确）：**

```
Module 实例 = {
   元数据（ModuleMetadata）+ 物理工作区（WorkspaceRoot）  // 是什么 + 在哪
   模块 Skill（ModuleDescription.Workflows: SkillDescriptor[]）  // 业务流程声明（按基建 Skill 标准派生）
   模块 MCP   （ModuleDescription.McpList: McpDescriptor[]）     // 业务操作接入点（按基建 MCP 标准派生）
   模块负责人 （ModuleOwners）                                   // 谁来做
}
```

**与基建层的派生关系**：模块的 Skill 集合和 MCP 集合**实例**归属 Workspace 模块，**类型契约**来自基建层。这是「类型共享 / 实例不共享」原则的具象落地。

**与 Agent 层的关系**：Workspace 模块**不依赖** Agent 层——一个工位独立于坐进来的人存在。Agent 实例进入某 Workspace 模块执行任务时，Agent 自带的 Tool/MCP/Skill 与 Workspace 自带的 Skill/MCP 在装配点合并（去重 by Id）——这是 task 期的临时组合，不是模块间的静态依赖。

**Workspace 层依赖基建层**：Workspace 引用 `CBIM.Mcp` + `CBIM.Skills`（两个基建抽象），用于声明业务 MCP 与业务 Skill。不依赖 Agent 层。

## 关键变化点（v2 三层模型 vs 旧六层模型）

### 变化 1：Tool / Skill / MCP 重新定位为「基建类型约定」

- **旧**：被叫做「能力层 Tool/Skill/MCP」，作为顶层模块跨维度共享。
- **新**：仍是顶层模块，但语义重定位为「基建层类型约定」——它们不是「能力」，它们是「能力描述的类型契约」。具体能力实例由 Agent 与 Workspace 各自派生持有。
- **物理影响**：无（位置不变）。
- **认知影响**：消除「Tool/Skill/MCP 属于哪个维度」的反复纠缠——它们不属于任何维度，只是类型契约。
- **类型 vs 实例**：基建层一份抽象 + 多份派生实例（Agent 一套、每个 Module 一套）。

### 变化 2：Memory 从「具体服务」抽象为「接口 + 默认实现」

- **旧**：`MemoryService` 是单例服务，跨 Agent 共享一份扁平 JSON 后端。
- **新**：`IMemoryService` 是基建接口，`FileMemoryBackend`（基于 FileBackend）是默认实现。**每个 Agent 实例持一个 IMemoryService 实例**。
- **目的**：
  1. 接入第三方记忆库（Pinecone / Weaviate / Chroma）只需新实现 IMemoryService，不改 Agent 层代码。
  2. 不同 Agent 可以接不同后端（轻量 Agent 用 FileBackend，重型 Agent 用向量库）。
  3. 「这个人的记忆」语义化——记忆与 Agent 绑定，符合「人 = Memory + 工具集」的认知模型。
- **物理影响**：
  - `Memory/` 模块拆出 `IMemoryService` 接口 + `MemoryEntry` 类型 + `FileMemoryBackend` 默认实现。
  - `AgentSystem.AgentDescription` 增 Memory 字段（`IMemoryService` 配置 / 实例引用）。
  - `Agent` 实例持 `IMemoryService` 字段。
- **依赖方向**：`Agent → IMemoryService`；`FileMemoryBackend → IMemoryService + FileBackend`。无反向。

### 变化 3：AgentSystem 概念上重命名为 Agent

- **概念层**：「AgentSystem」改称「Agent 层」——服务层管理的是「一个个虚拟人」，名字应该反映对象本身，而不是「produces agents 的系统」。
- **物理目录是否同步改名（`AgentSystem/` → `Agent/`）**：见下文「AgentSystem → Agent 重命名决策」节——本轮决策保留物理目录名，下一切片再决定是否改名。
- **影响范围**：
  - 文档/术语：所有提到「AgentSystem」的位置，明确语义是「Agent 层服务门面」。
  - C# 命名空间：本轮不动（`CBIM.AgentSystem` 命名空间仍有效）。
  - 类名：本轮不动（`AgentSystemService` 等仍有效）。

### 变化 4：Workspace 模块明确「业务 MCP + 业务 Skill 挂载点」

- **旧状态**：`ModuleDescription` 已含 `McpList: McpDescriptor[]` 和 `Workflows: SkillDescriptor[]`——业务 MCP 已存在，业务 Skill 以「Workflows」别名存在。
- **本轮变化**：术语统一为「业务 MCP + 业务 Skill」——`Workflows` 字段语义上 = 业务 Skill 集合；MCP 字段语义上 = 业务 MCP 集合。基建标准（`McpDescriptor` / `SkillDescriptor`）不变。
- **物理影响**：无（字段已存在）；只更新文档表达。

### 变化 5：派生侧 Tool/Skill/MCP 集合各自独立

- **本轮明确**：Agent 持的 Tool/Skill/MCP 实例集合 与 Workspace 模块持的 MCP/Skill 实例集合 **是独立的**——同一基建标准、不同实例。
- **去重时机**：仅在 task 期装配点合并（Agent 自带 + 当前 task.Where 模块自带），按 Id 去重；模块间 / Agent 间互不感知彼此的实例集合。
- **跨维度共享的精确表达**：共享的是「类型 / 接口 / 协议」（基建层一份），不共享「实例集合」（Agent / 各 Module 各持各的）。

## AgentSystem → Agent 重命名决策（本轮裁决）

**裁决：本轮保留物理目录名 `AgentSystem/`；下一切片视代码迁移成本再决定是否改名。**

**理由：**

1. **物理改名成本**：`AgentSystem/` → `Agent/` 涉及目录、asmdef、C# 命名空间（`CBIM.AgentSystem` → `CBIM.Agent`）、所有 using 语句、类名（`AgentSystemService` → `AgentService`）、测试文件。本轮重构焦点在「概念三层模型 + Memory 接口抽取」，不宜与改名工程混合，否则一处编译失败拖累整轮 .dna 与 _ARCHITECTURE.md 验证。
2. **概念已重命名**：术语层面已把「AgentSystem 服务层」明确为「Agent 层」——读者看到「AgentSystem」时知道它是「Agent 层的服务门面」，不是「Agent 本身」。物理改名是表达上的精确化，不改语义。
3. **可逆性**：保留物理目录名 = 保留可选项；下一切片若代码迁移已稳定，可统一改名（或决定永远不改——「AgentSystem 服务层装配 Agent 实例」也读得通，类比「PersonnelSystem 装配 Person」）。

**改名/不改名的对比表：**

| 维度 | 改名（`Agent/`） | 不改名（`AgentSystem/` 保留） |
|------|------------------|-------------------------------|
| 概念清晰度 | 更直接（目录名 = 概念名） | 需要文档说明（目录是服务层名） |
| 代码迁移成本 | 高（命名空间 + 类名 + 引用链） | 零 |
| 与 ExternalAdapter 对称性 | 一般（Agent vs ExternalAdapter 不对称） | 现状（AgentSystem vs ExternalAdapter 都以 -System/-Adapter 收尾） |
| Channel / Kernel 引用更新 | 需要 | 不需要 |

**下一切片若决定改名**：作为独立的代码迁移任务执行，搭配 `Agent` namespace 的全局 rename + asmdef 重写 + 全部测试一次过。

## Children（本轮三层归属）

### 基建层

| 子模块 | 一句话职责 | 状态 |
|--------|----------|------|
| `Storage/` | 文件系统原语（FileBackend + 原子写 + JSON） | spec |
| `Tools/` | `ToolDescriptor` 工具家族抽象 + `Standard/` 内置实现 | spec |
| `Skills/` | `SkillDescriptor` 技能 / 工作流描述抽象 | spec |
| `Mcp/` | `McpDescriptor` abstract + Stdio/Http 子类 + Transport 枚举 | spec |
| `Memory/` | `IMemoryService` 接口 + `MemoryEntry` 类型 + `FileMemoryBackend` 默认实现 | spec |

### Agent 层

| 子模块 | 一句话职责 | 状态 |
|--------|----------|------|
| `AgentSystem/` | Agent 装配服务门面（AgentDescription + OpenInstance + Session 写侧；持 IMemoryService 实例） | spec |
| `ExternalAdapter/` | 外部 Agent 引擎适配（Claude Code / Cursor / Codex 三策略） | spec |
| `Kernel/` | 行为树调度 + CbimTask + ContextProviders | spec |
| `Channel/` | Microsoft AgentSession 薄封装 | spec |

### Workspace 层

| 子模块 | 一句话职责 | 状态 |
|--------|----------|------|
| `Workspace/` | ModuleDescription + ModuleMetadata + ModuleOwners + 模块自身的 MCP/Skill 挂载点 | spec |

### 门面

| 子模块 | 一句话职责 | 状态 |
|--------|----------|------|
| `AgenticOS.cs` | 组合根门面（装配三层） | stub |

**已废弃**（代码已物理删）：`SystemTools/`、`Kernel/ExecutionUnit/`、`Kernel/TaskRunner/`、AgentSystem 下原独立的 `McpAdapter/`。

## Child Relationships（三层架构图）

```mermaid
flowchart TD
    classDef infra fill:#d1c4e9,stroke:#311b92,color:#000;
    classDef agent fill:#c8e6c9,stroke:#1b5e20,color:#000;
    classDef workspace fill:#bbdefb,stroke:#0d47a1,color:#000;
    classDef msai fill:#f8bbd0,stroke:#880e4f,color:#000;

    subgraph L1["基建层（类型约定 / 抽象接口 / 标准协议）"]
        STG["Storage<br/>FileBackend"]
        T["Tools<br/>ToolDescriptor (+ Standard 实现)"]
        SK["Skills<br/>SkillDescriptor"]
        MC["Mcp<br/>McpDescriptor (abstract)"]
        MEM["Memory<br/>IMemoryService 接口 +<br/>MemoryEntry +<br/>FileMemoryBackend 默认实现"]
        MEM --> STG
        T --> STG
    end

    subgraph L2["Agent 层（虚拟人代理 · 人的能力）"]
        AS["AgentSystem<br/>(AgentDescription 持 Memory/Tool/Skill/MCP)<br/>(OpenInstance 装配 + Session 写)"]
        EA["ExternalAdapter<br/>(外部引擎三策略)"]
        K["Kernel<br/>(FlowGraph + TaskScheduler + ContextProviders)"]
        CH["Channel<br/>(AgentSession 薄封装)"]
        K --> AS
        CH --> AS
        CH --> K
        AS --> MEM
        AS --> T
        AS --> SK
        AS --> MC
        EA --> T
        EA --> SK
        EA --> MC
    end

    subgraph L3["Workspace 层（工作区 / 项目）"]
        WS["Workspace<br/>(ModuleDescription:<br/>Metadata + Workflows[Skill] + McpList[Mcp] + Owners)"]
        WS --> MC
        WS --> SK
    end

    subgraph MSAI["Microsoft Agent Framework（横向底座）"]
        MSAgent["AIAgent / AgentSession"]
        MSChat["IChatClient"]
        MSWF["Workflow / Executor"]
        MSFn["AIFunction"]
        MSCP["AIContextProvider"]
        MSMcp["Mcp Client"]
    end

    AS -.AsAIAgent.-> MSAgent
    AS -.consumes.-> MSChat
    K -.基于.-> MSWF
    K -.实现.-> MSCP
    T -.produces.-> MSFn
    MC -.Microsoft.Agents.AI.Mcp.-> MSMcp

    AOS["AgenticOS<br/>(组合根)"]
    AOS --> CH
    AOS --> EA

    class STG,T,SK,MC,MEM infra;
    class AS,EA,K,CH agent;
    class WS workspace;
    class MSAgent,MSChat,MSWF,MSFn,MSCP,MSMcp msai;
```

**依赖单调（C3 铁律）：**

```
Workspace 层 → 基建层
Agent 层    → 基建层
Agent 层    → ⊥（不依赖 Workspace 层；二者跨层协同在 task 期由 AgenticOS / Kernel 组合）
基建层      → ⊥（不依赖任何 CBIM 同级层）
组合根      → 三层（仅装配；不参与运行期数据流）
```

**跨层关系澄清：**

- **Agent 层 ⊥ Workspace 层**——二者**互不依赖**。Task 执行时 Agent 进入某 Workspace 模块，由 Kernel 的 ContextProvider 把 Workspace 模块的 Skill/MCP/Metadata 注入到 Agent 的运行上下文——这是**运行期组合**，不是**编译期依赖**。
- **跨层共享抽象 = 基建层**——Tool/Skill/MCP/IMemoryService 同时被 Agent 层与 Workspace 层引用；依赖方向严格单向（两层都 → 基建层）。
- **Workspace 不引用 IMemoryService**——记忆是 Agent 的，不是模块的。模块只有规章、流程、接入点；没有「模块的记忆」。

## 三层架构铁律

1. **基建层不依赖任何其他 CBIM 层**——基建是依赖图最稳定底层；变更基建抽象 = 全栈影响，需高度审慎。
2. **基建抽象稳定优于完整**——`IMemoryService` 优先暴露最小必要接口；进化时不破坏既有实现（C6 开放/封闭）。
3. **Agent 层与 Workspace 层互不依赖**——所有跨层协同走运行期组合（Kernel / ContextProvider / 组合根），不走静态引用。
4. **类型契约共享 / 实例集合独立**——同一基建抽象的派生实例由各方独立持有，仅在 task 期装配点合并去重。
5. **Agent 持 IMemoryService 实例**——记忆与 Agent 绑定；不再有「全局 MemoryService 单例」概念。
6. **基建 IMemoryService 默认实现 = FileMemoryBackend**——本地文件后端；接 Pinecone / VectorStore 通过实现新 IMemoryService 派生。
7. **Module 持自身 MCP / Skill 实例**——Module 自带的接入点与流程都是 Module 的财产；Agent 进入此 Module 时按需借用，离开不带走。
8. **Tool 是唯一安全边界（沿用）**——无论 Agent 自带还是 Module 自带，所有副作用最终都穿过 `Tools/Standard` 或 `Mcp`。基建层的「Tool 接口」是这条铁律在抽象层的体现。
9. **AgentSystem 服务层名称 ≠ Agent 实例**——AgentSystem 是「装配 Agent 的服务层门面」，类比「PersonnelService 装配 Person」。术语澄清，本轮不改物理目录名。
10. **三层模型不破坏既有跨维度共享判断**——「跨维度共享」一类判断由基建层承接（抽象在基建、实例在各层）；旧文档里「跨维度共享 McpDescriptor」的判断**完全保留**，只是表达更精准。
11. **复合 Agent 三定理沿用不变**——皮层定理 / 脑区定理 / 武器库定理是顶层认知铁律，与三层模型正交（三层是源码组织视角，三定理是行为视角）。

## 历史层级名词的折叠

为避免老文档与新表达冲突，老六层名词与新三层名词的对应表如下：

| 旧六层名词 | 新三层位置 | 备注 |
|------------|-----------|------|
| 行为树调度层 | Agent 层 / Kernel 子模块 | 皮层落在 Agent 层内部 |
| 引擎层（AgentSystem / ExternalAdapter） | Agent 层 / AgentSystem + ExternalAdapter | 两支并入 Agent 层 |
| 业务层（Workspace / Channel） | Workspace 层（Workspace） + Agent 层（Channel） | Channel 是 Agent 入口，归 Agent 层 |
| 能力层（Skills / Mcp） | 基建层（Skills / Mcp） | 重定位为「类型约定」 |
| 基座层（Tools / Storage） | 基建层（Tools / Storage） | 名字最贴 |
| 扩展层（ExternalAdapter） | Agent 层（ExternalAdapter） | 外部引擎本质是「另一种 Agent 实现」 |
| 横切关注点（Memory） | 基建层（IMemoryService 接口）+ Agent 层（持实例） | 接口在基建、实例归 Agent |

老的 `_ARCHITECTURE.md` 顶层文档将由下一个 Work Agent 任务（doc_writer）重写以匹配三层模型。

## Origin Context

CBIM v2 Unity 移植的演进线（截至本轮）：

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
11. **补 IO 工具**：发现 MSAI Tools 几乎缺位，新增 StandardTools 子模块——当时误放在 `Workspace/` 下。
12. **维度修正**：StandardTools 从 `Workspace/` 迁到 `AgentSystem/` 下；`ModuleDescription.standard_tools` / `external_mcp_servers` 字段删除；`AgentDescription.tools` + `agent_extension_clis` 字段新增；Agent 裂变铁律入能力维度顶层设计。
13. **MCP 集成**：新增 `AgentDescription.mcp_servers` 名字串 + `OpenInstanceOptions.TaskWhere`；新增 `AgentSystem/McpAdapter/` 子模块。
14. **三足鼎立 + 代码落地 + 跨维度共享**：能力维度三大扩展抽象平级子模块化，`McpDescriptor` 抽为 abstract，`Workspace.ModuleDescription.McpList` 新增。
15. **顶层化 Tool/Skill/Mcp**：从 `AgentSystem/` 子目录提升为顶层模块；当时表述为「能力层 + 跨维度共享」。
16. **多引擎家纳管**：新增 `ExternalAdapter/` 作为第四服务层，三策略适配外部引擎。
17. **复合 Agent 认知**：提出「CBIM 整体 = 复合 Agent」顶层 mental model；提出复合 Agent 三定理。

**本轮（三层模型 + Memory 接口抽取）**：

18. **顶层心智从 6 层收敛到 3 层**——之前的「调度/引擎/业务/能力/基座/扩展」六层是源码组织的精确分类，但顶层心智过宽（读者得记 6 个层、6 个职责、6 套铁律）。本轮收敛为「基建 / Agent / Workspace」三层——三个名字、三句话、三个清晰职责。六层并未消失，只是退化为三层内部的子结构。
19. **Tool/Skill/MCP 重新定位为「基建类型约定」**——之前叫「能力层」隐含「这些是能力本身」，与「Agent 是能力个体」的另一表达冲突。本轮明确：Tool/Skill/MCP 是「能力的类型契约」（基建），具体能力实例由 Agent 与 Workspace 各自派生持有。
20. **Memory 抽象为 IMemoryService 接口 + 默认 FileBackend 实现**——为接入第三方记忆库（Pinecone / Weaviate / Chroma 等）开口；每个 Agent 持一个 IMemoryService 实例，从「全局服务」改为「per-Agent 实例」，与「人 = 拥有自己记忆」的认知模型对齐。
21. **AgentSystem 概念上重命名为 Agent**——服务层管理的对象是「一个个虚拟人」，名字应反映对象本身。物理目录改名留下切片决定（见「AgentSystem → Agent 重命名决策」节）。
22. **Workspace 模块明确「业务 MCP + 业务 Skill 挂载点」**——之前 `ModuleDescription.Workflows + McpList` 已存在但术语不统一；本轮把这两个字段明确为「业务 Skill 集合 + 业务 MCP 集合」，类型来自基建。
23. **「类型 vs 实例」原则取代「跨维度共享」表达**——之前「跨维度共享 McpDescriptor」表达虽精确但绕；本轮直接说「类型契约由基建层提供一份，实例集合由 Agent / Workspace 各自独立持有」——更易记、更易讲。

每一步的共同主线是「凡公共抽象交出去 / 凡 CBIM 独有业务保留」。本轮加一条：**「凡顶层心智模型，能用 3 个词说清就不用 6 个」**——架构演进的最后一英里是认知简化。

## Emergent Insights（本轮新增）

1. **「类型契约 vs 实例集合」是比「跨维度共享」更精确的描述**——之前「跨维度共享 McpDescriptor」总让人误以为「Agent 和 Workspace 共享同一份 McpList 实例」；新表达「类型在基建、实例各自独立」一句话讲清，无歧义。
2. **Memory per-Agent 实例化是「物理人 = 物理记忆」的认知落地**——人有自己的记忆是常识；之前 Memory 作为全局服务是工程便利，但破坏了认知模型。本轮回归到「每个人持有自己的记忆实例」——同时打开了第三方后端接入的能口。
3. **三层模型让「为什么要有调度层」的答案更短**——「行为树调度层是 Agent 层内部的脑皮层」——一句话讲完。之前六层中「调度层」作为顶层是认知层级错配（调度本质是 Agent 自身的脑功能，不是与 Agent 平级的另一物种）。
4. **「Agent 层 vs Workspace 层互不依赖」是 v2 顶层架构的最重要约束之一**——这条铁律保证「人」和「工位」是两件相互独立的资产，能各自演化、各自接入第三方实现。Kernel 在 task 期负责把二者组合——这是「皮层」职能的精确定义。
5. **基建层抽象稳定 = 整个系统的稳定底层**——把 Tool/Skill/MCP/Memory 接口都放在基建层，意味着这四个接口的版本变更需要双层审视（Agent + Workspace 都受影响）。这反过来鼓励基建接口设计追求「最小完整」——能不暴露就不暴露。
6. **AgentSystem → Agent 概念重命名暴露了「服务层命名 vs 实例命名」的张力**——`AgentSystem` 是服务层名（产生 Agent 的家），`Agent` 是实例名（被产生的对象）。两者在文档里随意混用会让读者迷惑。本轮分离概念（语义层）与物理（目录层）的处理方式——「概念已改、物理待议」——为下次类似改名留下了模板。

## Implementation Sequence（本轮 .dna 修订 → 下切片代码迁移）

本轮（架构修订）：

1. ✅ 根 `.dna/module.md` 切换为三层模型描述。
2. ✅ `AgentSystem/.dna/module.md` 明确「Agent 层服务门面 + 持 IMemoryService 实例」。
3. ✅ `Workspace/.dna/module.md` 明确「业务 MCP + 业务 Skill 挂载点」+ 与 Agent 层的解耦关系。
4. ✅ `Memory/.dna/module.md` 切换为「IMemoryService 接口 + FileMemoryBackend 默认实现 + per-Agent 实例化」。
5. ✅ `Tools/.dna/module.md` / `Skills/.dna/module.md` / `Mcp/.dna/module.md` 顶部加「基建层定位」段落（保留原内容，仅重定位）。
6. 由 Work Agent 重写 `_ARCHITECTURE.md`（doc_writer 任务）。

下切片（代码迁移，本轮不发）：

1. `Memory/` 拆出 `IMemoryService.cs` 接口 + `FileMemoryBackend.cs` 默认实现；`MemoryService` 类改名为 `FileMemoryBackend` 或保留为 facade。
2. `AgentDescription` 增 Memory 配置字段（实例引用 / 工厂方法）；`AgentSystem.OpenInstance` 装配 Agent 时绑定 IMemoryService 实例。
3. `Agent` 实例类（运行时）持 `IMemoryService` 字段；释放时（如有 IDisposable backend）按 IAsyncDisposable 协议关闭。
4. `Channel`、`Kernel.ContextProviders` 引用 IMemoryService 接口（不再引用具体 MemoryService 类）。
5. （可选）`AgentSystem/` → `Agent/` 物理目录改名 + 命名空间 + asmdef + 全部 using 更新。本轮裁决「下切片再议」。

## Non-Goals（本轮）

- **不实施代码迁移**——本轮仅 .dna + _ARCHITECTURE.md；具体 IMemoryService 抽取、AgentSystem 改名、Agent 类持 Memory 字段等留下切片。
- **不重新引入** LlmEngine / Pipeline / INode / IFlowGraph / IKernelEngine / ITaskRunner / IFileTools / IShellTools 任何抽象。
- **不自写** 业务工作流引擎、工具调用闭环、会话压缩、IO 工具层。
- **不引入 MCP 服务端**——Unity 进程内直调 Microsoft。
- **不发治理循环代码**——本轮仅业务执行。
- **AgentSystem / Workspace 不发写侧**——Unity 侧暂走 Python `dna_*` / `agent_*` MCP 工具。
- **AgentDescription `chat_client_config` schema 详细演进**留后续切片。
- **Shell AIFunction**——Microsoft Tools.Shell 当前 net8-only，本轮 Unity 主线接受「无 Shell」约束。
- **不为接入 Pinecone 写实现**——本轮仅暴露 `IMemoryService` 接口，具体后端接入是业务方按需自行派生。
