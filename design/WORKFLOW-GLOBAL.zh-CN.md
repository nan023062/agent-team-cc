# CBIM 全局系统结构

> **v1**（基于 Claude Code）与 **v2**（原生实现）共享的设计蓝图。  
> 网页版：`design/web/index.html` → 全局结构标签。

三个层次 · 四个循环 · 双轴迭代裂变。用户只感知首尾，其余全部自治。

```mermaid
graph TB
    User(["👤 用户<br/>说一次需求，等最终结果"])

    subgraph ExecLayer["  执行层 — Claude Code 优化  "]
        Coord["🎯 Coordinator<br/>自治调度中心"]
        WorkAgent["🔧 Work Agent<br/>执行实现"]
    end

    subgraph GovLayer["  治理层 — 双轴迭代裂变  "]
        subgraph BizAxis["业务轴"]
            Arch["🏛 Architect<br/>业务知识治理循环<br/>.dna/ 知识系统"]
        end
        subgraph CapAxis["能力轴"]
            HR["👥 HR<br/>能力知识治理循环<br/>.claude/agents/"]
        end
    end

    subgraph MemLayer["  记忆层 — Hook 自动驱动  "]
        Mem["🧠 记忆治理循环<br/>short/ → medium/ → .dna/"]
    end

    User -->|"提出需求"| Coord
    Coord -->|"必经门<br/>DNA 状态确认"| Arch
    Arch -->|"模块路径 + 设计约束"| Coord
    Coord -->|"携带上下文派发"| WorkAgent
    WorkAgent -->|"设计决策上报"| Coord
    Coord -->|"整合结果"| User

    Coord -->|"能力缺口"| HR
    HR -->|"agent 路径"| Coord

    WorkAgent -->|"执行经验"| Mem
    Mem -->|"知识回流"| Arch
    Arch <-->|"协同裂变"| HR
```

**核心闭环：** 每次任务执行都在让系统变得更好——经验沉淀为记忆，记忆提升为知识，知识增强下一次执行。

**裂变机制：** 新模块 DNA 建立 → 知识图谱扩展；新 agent 孵化 → 能力图谱扩展；两轴协同，边界持续生长。

## 三个层次

| 层次 | 内容 | 治理目标 |
|------|------|----------|
| 执行层 | Coordinator + Work Agent | 任务完成，用户心智负担最低 |
| 治理层 | Architect（业务轴）+ HR（能力轴） | 知识与能力持续裂变 |
| 记忆层 | Hook 驱动的三层沉淀 | 经验不随会话消失 |

## 四个循环

- [执行任务循环](./WORKFLOW-EXECUTION.zh-CN.md) — 入口，所有需求由此进入
- [业务知识治理循环](./WORKFLOW-ARCHITECT.zh-CN.md) — 业务轴，DNA 四状态管理
- [能力知识治理循环](./WORKFLOW-HR.zh-CN.md) — 能力轴，agent 生命周期
- [记忆治理循环](./WORKFLOW-MEMORY.zh-CN.md) — 底座，贯穿全程
