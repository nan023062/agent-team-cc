# CBIM 循环与角色全景

> **一句话开宗明义：CBIM 所有循环都是 BT。** 八棵行为树跑在同一个引擎核心上，没有第二种调度模型，没有手写状态机，没有散落的协程。看到"循环"就等于看到一棵 BT。

本文档是给人看的**全貌索引**，不是技术规格。流程图为主，散文为辅；每棵 BT 的内部节点、黑板字段、收敛判定、实现细节，全部在各自的 `WORKFLOW-*.zh-CN.md` 里展开。

---

## 1. 八棵 BT 全景图

```mermaid
flowchart TB
    subgraph Engine["BT 引擎核心（同一套节点 / 装饰器 / Tick 协议）"]
        direction TB
        subgraph ExecRoot["执行根 BT（用户驱动）"]
            E0[["执行根 BT 拓扑"]]
            E1[["主 agent 记忆 CRUD 子循环 BT 拓扑"]]
            E2[["Architect 执行子循环 BT 拓扑"]]
            E3[["HR 执行子循环 BT 拓扑"]]
        end
        subgraph DreamRoot["治理根 BT（scheduler 驱动）"]
            D0[["治理根 BT 拓扑"]]
            D1[["主 agent 记忆治理子循环 BT 拓扑"]]
            D2[["Architect 治理子循环 BT 拓扑"]]
            D3[["HR 治理子循环 BT 拓扑"]]
        end
    end

    User(["User<br/>提需求 / 等结果"]) -->|触发| E0
    Sched(["SessionStart 补跑检测"]) -->|触发| D0

    E0 -.->|yield 派工| E1
    E0 -.->|yield 派工| E2
    E0 -.->|yield 派工| E3
    D0 -.->|yield 派工| D1
    D0 -.->|yield 派工| D2
    D0 -.->|yield 派工| D3

    NoBT["无 BT 协作者<br/>Auditor · Work Agents · 记忆服务"]
    E0 -.->|可选 yield| NoBT
    E1 -.->|调用| NoBT
    D1 -.->|调用| NoBT
```

两棵根 BT 平级共存，互不 import；六棵子循环 BT 按"执行/治理"分别挂到对应根上。子循环也是 BT，由根 BT 的 yield 派工触发，跑完回收结果继续 Tick。

---

## 2. 八棵 BT 归属表

| BT 名称 | 触发方 | 入口 | 详见文档 |
|---------|--------|------|----------|
| 执行根 BT | User prompt | 主 agent 调 `bt_tick` | [`WORKFLOW-EXECUTION.zh-CN.md`](./WORKFLOW-EXECUTION.zh-CN.md) |
| 治理根 BT | SessionStart 补跑检测 | 主 agent 调 `dream_tick` | [`WORKFLOW-DREAM.zh-CN.md`](./WORKFLOW-DREAM.zh-CN.md) |
| 主 agent 记忆 CRUD 子循环 BT | 执行根 yield | 主 agent 自驱 | [`WORKFLOW-MEMORY.zh-CN.md`](./WORKFLOW-MEMORY.zh-CN.md) |
| 主 agent 记忆治理子循环 BT | 治理根 yield | 主 agent 自驱 | [`WORKFLOW-MEMORY.zh-CN.md`](./WORKFLOW-MEMORY.zh-CN.md) |
| Architect 执行子循环 BT | 执行根 yield | Task tool 派给 Architect | [`WORKFLOW-ARCHITECT.zh-CN.md`](./WORKFLOW-ARCHITECT.zh-CN.md) |
| Architect 治理子循环 BT | 治理根 yield | Task tool 派给 Architect | [`WORKFLOW-ARCHITECT.zh-CN.md`](./WORKFLOW-ARCHITECT.zh-CN.md) |
| HR 执行子循环 BT | 执行根 yield | Task tool 派给 HR | [`WORKFLOW-HR.zh-CN.md`](./WORKFLOW-HR.zh-CN.md) |
| HR 治理子循环 BT | 治理根 yield | Task tool 派给 HR | [`WORKFLOW-HR.zh-CN.md`](./WORKFLOW-HR.zh-CN.md) |

引擎本体见 [`v1/kernel/engine/bt/README.md`](../v1/kernel/engine/bt/README.md)。

---

## 3. 无 BT 的协作者

CBIM 里有三类协作者**不跑 BT**，刻意保持简单：

- **Auditor** — Claude Code subagent，仅靠提示词约束行为；执行根 yield 派工，跑完结束。配置见 `.claude/agents/auditor/auditor.md`。
- **Work Agents** — Claude Code subagent，仅靠提示词约束行为；执行根 yield 派工，跑完结束。配置见 `.claude/agents/<各 agent>/...`。
- **记忆服务** — 被动数据层，不是 actor，等着被调用；对外只读查询接口，对治理走维护接口。详见 [`WORKFLOW-MEMORY.zh-CN.md`](./WORKFLOW-MEMORY.zh-CN.md)。

---

## 4. 维护约定

| 项 | 约定 |
|----|------|
| 文档定位 | 八棵 BT 的位置索引，新人读完应能回答"系统里有哪几棵 BT、各自挂在哪棵根上、各自的详细设计在哪个文档"。 |
| 内容边界 | 只画归属与触发关系；不画任何 BT 的节点拓扑、黑板字段、收敛逻辑、接口签名。 |
| 维护触发 | 新增 / 删除 / 合并 / 重挂任何一棵 BT，必须同步更新本文档的全景图与归属表。 |
| 不需更新的场景 | 某棵 BT 的内部节点、装饰器、黑板字段变化——只更新对应的 `WORKFLOW-*` 文档。 |
