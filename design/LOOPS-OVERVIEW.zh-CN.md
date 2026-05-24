# CBIM 循环与角色全景

> CBIM 所有运行时角色与循环的**位置图**。
> 本文档只画位置，不画内部；每个循环/子循环/服务的内部设计在各自专门文档中。
> 关联文档：[`WORKFLOW-EXECUTION.zh-CN.md`](./WORKFLOW-EXECUTION.zh-CN.md)（执行任务循环 · 用户驱动的根）、[`WORKFLOW-DREAM.zh-CN.md`](./WORKFLOW-DREAM.zh-CN.md)（治理循环 · scheduler 驱动的根）、[`WORKFLOW-MEMORY.zh-CN.md`](./WORKFLOW-MEMORY.zh-CN.md)（主 agent 记忆能力 + 记忆服务）、[`WORKFLOW-ARCHITECT.zh-CN.md`](./WORKFLOW-ARCHITECT.zh-CN.md)（Architect 双子循环）、[`WORKFLOW-HR.zh-CN.md`](./WORKFLOW-HR.zh-CN.md)（HR 双子循环）。引擎实现技术文档见 [`v1/kernel/engine/bt/README.md`](../v1/kernel/engine/bt/README.md)。

> **架构总览：** CBIM 是**双根架构**。BT 引擎承载两棵平级的根树——执行任务循环（用户驱动）与治理循环（scheduler 驱动）。两根不互相依赖，各自独立黑板、独立 trace、独立入口工具。**3 个有循环的 actor**（主 agent / Architect / HR）各自挂 2 个子循环到两棵根上；**2 个无循环 agent**（Auditor / Work Agents）仅是 Claude Code 的 subagent 提示词配置，CBIM 不为它们设计循环；**1 个被动数据层**（记忆服务）等着被调用。

---

## 1. 总览图

```mermaid
flowchart TB
    User(["User<br/>说一次需求，等最终结果"])
    Sched(["SessionStart Hook<br/>检测「昨夜没跑就补跑」"])

    BT[["🌳 BT 引擎<br/>承载两棵平级根树<br/>核心驱动者"]]

    Coord["Coordinator (主 agent)<br/>含 CRUD 子循环 + 治理子循环<br/>(记忆能力宿主)"]
    Arch["Architect<br/>含执行子循环 + 治理子循环<br/>(.dna/ 业务知识轴)"]
    HR["HR<br/>含执行子循环 + 治理子循环<br/>(.claude/agents/ 能力轴)"]

    Aud["Auditor<br/>Claude Code 提示词配置 agent<br/>无 CBIM 循环设计"]
    Work["Work Agents<br/>Claude Code 提示词配置 agent<br/>无 CBIM 循环设计"]

    Mem[("记忆服务<br/>被动数据层 · 非 actor<br/>对外: query / scan / get / stats<br/>对治理: compact / sweep / rebuild")]

    User -->|提出需求| Coord
    Sched -->|注入「治理待补跑」提示| Coord
    Coord -->|bt_tick / bt_tick_resume<br/>执行根| BT
    Coord -->|dream_tick / dream_tick_resume<br/>治理根| BT

    BT -.->|执行根 Yield: 派 Architect 执行子循环| Coord
    BT -.->|执行根 Yield: 派 HR 执行子循环| Coord
    BT -.->|执行根 Yield: 派 Work Agent| Coord
    BT -.->|执行根 Yield: 派 Auditor (可选)| Coord
    BT -.->|治理根 Yield: 派 Architect 治理子循环| Coord
    BT -.->|治理根 Yield: 派 HR 治理子循环| Coord

    Coord -->|Task tool 派工| Arch
    Coord -->|Task tool 派工| HR
    Coord -->|Task tool 派工| Work
    Coord -->|Task tool 派工| Aud
    HR -->|执行子循环返回 agent_list| Coord
    Coord -->|按 agent_list 派工| Work
    Coord -->|整合结果| User

    Coord -.->|CRUD 子循环: write/query| Mem
    Arch -.->|查询| Mem
    HR -.->|查询| Mem
    Aud -.->|查询| Mem
    Work -.->|查询| Mem
    BT -.->|执行根 FlushMemory 写入| Mem
    BT -.->|治理根直调内部维护接口<br/>compact / sweep / rebuild| Mem
```

**双根架构：** BT 引擎同时承载两棵根树。执行任务循环走 `bt_tick`，治理循环走 `dream_tick`；两根共用引擎，但黑板、节点、trace、入口工具全部独立。Coordinator 仍是唯一 Action 执行手——但同时它也是有自己双子循环的 actor，负责把任一根 yield 出的 DispatchRequest 用 Task tool 派工。

**3 + 2 + 1 角色拓扑：**
- **3 个有循环的 actor**（主 agent / Architect / HR）——每个 actor 在执行根挂一个执行子循环、在治理根挂一个治理子循环，共 6 个子循环；
- **2 个无循环 agent**（Auditor / Work Agents）——仅 Claude Code 提示词配置，BT 引擎只是 yield 它们的派工请求，它们的"内部行为"由提示词约束，不进 CBIM 循环设计；
- **1 个被动数据层**（记忆服务）——不是 actor，不在 yield 链路里，等着被主 agent 的两个子循环调用。

---

## 2. 角色一句话定位

| 角色 | 类型 | 一句话定位 | 详细设计文档 |
|------|------|------------|--------------|
| **Coordinator (主 agent)** | actor · 双子循环 | 唯一对外接口；调 `bt_tick` 启动执行根、调 `dream_tick` 启动治理根；按引擎 yield 出的 DispatchRequest 用 Task tool 派工；自身持有记忆 CRUD 子循环（执行根触发）+ 记忆治理子循环（治理根触发）。 | [`WORKFLOW-EXECUTION.zh-CN.md`](./WORKFLOW-EXECUTION.zh-CN.md) + [`WORKFLOW-DREAM.zh-CN.md`](./WORKFLOW-DREAM.zh-CN.md) + [`WORKFLOW-MEMORY.zh-CN.md`](./WORKFLOW-MEMORY.zh-CN.md) |
| **Architect** | actor · 双子循环 | 业务知识轴（`.dna/`）的管理者和执行者；执行子循环负责"接 yield 产 ContextPack"（必经门），治理子循环负责"扫 `.dna/` 找问题、安全动作自主、危险动作只产建议"。 | [`WORKFLOW-ARCHITECT.zh-CN.md`](./WORKFLOW-ARCHITECT.zh-CN.md) |
| **HR** | actor · 双子循环 | 能力轴（`.claude/agents/`）的管理者和执行者；执行子循环负责"按 ContextPack 匹配 / 招募 agent 返回 agent_list"，治理子循环负责"扫 `.claude/agents/` 找问题"。 | [`WORKFLOW-HR.zh-CN.md`](./WORKFLOW-HR.zh-CN.md) |
| **Auditor** | Claude Code subagent | 仅提示词配置，CBIM 不设计循环；执行根的可选叶节点 yield 它做独立评审，行为完全由 prompt 约束。 | `.claude/agents/auditor/auditor.md`（提示词配置） |
| **Work Agents** | Claude Code subagent | 仅提示词配置，CBIM 不设计循环；执行根 `DispatchParallel` yield 派工，每个 agent 的行为完全由其各自的 `.claude/agents/<dir>/<name>.md` 约束。 | `.claude/agents/<各 agent>/...`（提示词配置） |
| **记忆服务** | 被动数据层 | 不是 actor，没有主动性；项目本地的嵌入式数据库式服务；主 agent 通过 CRUD / 治理两个子循环使用它，其他 agent 通过对外只读 4 接口查询。 | [`WORKFLOW-MEMORY.zh-CN.md`](./WORKFLOW-MEMORY.zh-CN.md) |

**Auditor 和 Work Agents 是 Claude Code 的 subagent 提示词配置**，行为约束写在它们各自的 `.claude/agents/*.md` 文件里。CBIM 不为它们设计执行循环——BT 引擎只是 yield 它们的派工请求，它们被派去做什么、怎么做，全部由提示词决定。这是一种刻意的设计选择：把"有结构的角色"做成有循环的 actor，把"看 prompt 干活的角色"做成无循环的 subagent，让循环复杂度只压在真正需要的地方。

---

## 3. 本文档的角色与维护方式

| 项 | 约定 |
|----|------|
| 文档定位 | CBIM 所有循环、子循环与服务的**唯一位置索引**。新人读完此文应能回答"系统里有谁、谁找谁、各自在哪、谁有循环谁没有"。 |
| 内容边界 | 只画位置关系（谁派谁的工、谁查谁的数据、哪些子循环挂在哪棵根上）；**不**画任何循环的内部状态机、不写任何接口签名、不展开任何子循环的内部决策流程。 |
| 详细设计 | 每个 actor 的双子循环都有独立的 `WORKFLOW-*.zh-CN.md`（主 agent → WORKFLOW-MEMORY，Architect → WORKFLOW-ARCHITECT，HR → WORKFLOW-HR），本文档只在"详细设计文档"列中引用其路径。 |
| 维护触发 | 任何**循环边界调整**（新增循环 / 子循环、删除、合并、改变派工关系、改变查询关系、新增/删除根树、actor 升级/降级）必须**同步更新本文档**，否则位置图与实际不符即视为破窗。 |
| 不需要更新的场景 | 某个子循环内部状态机变化、接口签名变化、实现技术栈变化——这些只更新对应的 `WORKFLOW-*` 文档。 |

---

## 4. 当前状态

| 模块 / 子循环 | 设计状态 | 文档 |
|--------------|----------|------|
| 执行任务循环（用户驱动根） | ✅ 已设计（行为树引擎驱动） | [`WORKFLOW-EXECUTION.zh-CN.md`](./WORKFLOW-EXECUTION.zh-CN.md)；引擎实现 [`v1/kernel/engine/bt/README.md`](../v1/kernel/engine/bt/README.md) |
| 治理循环（scheduler 驱动根） | 🚧 设计中（v1 草案） | [`WORKFLOW-DREAM.zh-CN.md`](./WORKFLOW-DREAM.zh-CN.md) |
| 主 agent — 记忆 CRUD 子循环 | ✅ 已设计 | [`WORKFLOW-MEMORY.zh-CN.md`](./WORKFLOW-MEMORY.zh-CN.md) 第一部分 |
| 主 agent — 记忆治理子循环 | ✅ 已设计 | [`WORKFLOW-MEMORY.zh-CN.md`](./WORKFLOW-MEMORY.zh-CN.md) 第二部分 |
| Architect — 执行子循环 | 🚧 设计中 | [`WORKFLOW-ARCHITECT.zh-CN.md`](./WORKFLOW-ARCHITECT.zh-CN.md) 第一部分 |
| Architect — 治理子循环 | 🚧 设计中 | [`WORKFLOW-ARCHITECT.zh-CN.md`](./WORKFLOW-ARCHITECT.zh-CN.md) 第二部分 |
| HR — 执行子循环 | 🚧 设计中 | [`WORKFLOW-HR.zh-CN.md`](./WORKFLOW-HR.zh-CN.md) 第一部分 |
| HR — 治理子循环 | 🚧 设计中 | [`WORKFLOW-HR.zh-CN.md`](./WORKFLOW-HR.zh-CN.md) 第二部分 |
| 记忆服务（被动数据层） | ✅ 已设计 | [`WORKFLOW-MEMORY.zh-CN.md`](./WORKFLOW-MEMORY.zh-CN.md) §1–§3 |

**说明：Auditor 和 Work Agents 是 Claude Code 的 subagent 提示词配置**，行为约束写在它们各自的 `.claude/agents/*.md` 文件里，**CBIM 不为它们设计执行循环**。当前状态表里不再有"Auditor 独立评审循环"或"Work Agents 执行子循环"这两行——它们从未存在过、也不会被设计。

主循环根（执行 / 治理）分别独立设计；3 个有循环的 actor 各自挂 2 个子循环上去，内部细节正在沉淀；它们对外都通过 BT 引擎的 `DispatchRequest` 入口被调用，无论调用方是执行根还是治理根。

---

## 5. 驱动模型

**BT 引擎是核心驱动者，承载两棵平级根树；3 个有循环的 actor 各挂 2 个子循环上去**——这是 CBIM 当前的范式。

- **驱动者（BT 引擎）：** 持有两棵根树的拓扑、装饰器栈、独立黑板、迭代收敛判定。同一个引擎、两个入口、两份黑板。

- **两棵根树的驱动模型：**

  | 根 | 触发源 | 入口工具 | 黑板路径 | 用户感知 | 挂的子循环 |
  |----|--------|---------|----------|---------|----------|
  | 执行任务循环 | 用户 prompt | `bt_tick` / `bt_tick_resume` | `.cbim/scheduler/bt/<tick_id>/` | 等结果，前台 | 主 agent CRUD 子循环 / Architect 执行子循环 / HR 执行子循环 |
  | 治理循环 | SessionStart 补跑检测 | `dream_tick` / `dream_tick_resume` | `.cbim/scheduler/dream/<run_id>/` | 不等结果，后台；冲突时让位用户 | 主 agent 记忆治理子循环 / Architect 治理子循环 / HR 治理子循环 |

- **两根平级共存，互不依赖：** 执行循环的代码不 import 治理循环模块，反之亦然。共享的只有 BT 引擎本体（`engine/bt/core`）和被治理的资源目录（`.cbim/memory/` / `.dna/` / `.claude/agents/`）。

- **3 + 2 + 1 角色分工：**
  - **3 个有循环的 actor**（主 agent / Architect / HR）感知不到"现在跑的是哪棵根"——它们只看到 prompt 头部带不带治理模式标识，据此决定进哪个子循环；
  - **2 个无循环 agent**（Auditor / Work Agents）只在执行根被 yield，跑完就结束，不持有任何跨调用状态；
  - **1 个被动数据层**（记忆服务）只接受调用，从不感知是谁、来自哪个根、属于哪个子循环。

- **CBIM 是双根架构：** 历史上"单根模型"的决议已升级为"两根平级共存"——这不是推翻原决议，是承认 CBIM 同时需要"用户驱动的反应式调度"和"scheduler 驱动的自维护调度"两种模型。两者强行合并会让黑板膨胀、语义混乱；拆成两棵根、共用引擎、独立审计，是更干净的边界切分。

引擎实现细节、节点契约、协程式 yield/resume 协议详见 [`v1/kernel/engine/bt/README.md`](../v1/kernel/engine/bt/README.md)。
