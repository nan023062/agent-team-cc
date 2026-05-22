# CBIM 执行任务循环

> **v1**（基于 Claude Code）与 **v2**（原生实现）共享的设计蓝图。  
> 网页版：`design/web/loops.html` → 执行任务循环标签。

对 Claude Code 执行机制的优化。用户说一次需求，Coordinator 自治驱动到完成。Architect 是所有执行任务的必经门。

```mermaid
flowchart TD
    User(["👤 用户<br/>说一次需求"])
    Respond(["👤 用户<br/>收到最终结果"])

    User --> Understand

    subgraph Loop["🔄 Coordinator 自治调度循环"]
        Understand["1️⃣ 理解意图<br/>从对话提取需求<br/>不清晰 → 只问一个聚焦问题"]
        Route["2️⃣ 分类路由<br/>cbim skill show dispatch"]
        Decompose["3️⃣ 拆解子任务<br/>并行 / 串行"]
        ArchGate["4️⃣ Architect 必经门<br/>DNA 状态分析-思考-执行<br/>返回模块路径 + 设计约束"]
        WorkAgent["5️⃣ Work Agent 执行<br/>携带 Architect 上下文"]
        Collect["6️⃣ 收集分析结果"]

        Understand --> Route
        Route -->|"执行任务"| Decompose
        Route -->|"业务层 CRUD"| ArchGate
        Route -->|"能力层 CRUD"| HR["👥 HR 能力治理"]
        Decompose --> ArchGate
        ArchGate --> WorkAgent
        WorkAgent -->|"设计决策无法独立完成"| ArchGate
        WorkAgent --> Collect
    end

    Collect -->|"✅ 完成且一致"| Respond
    Collect -->|"🔁 有后续子任务"| Decompose
    Collect -->|"⚠️ 冲突 / 阻塞"| User
```

## 调度原则

- 每次迭代必须有实质进展，无进展即停止上报
- **打断用户的唯一条件：** 意图真正模糊 · 结果冲突 · 破坏性/不可逆操作

## Architect 必经门（步骤 4）

执行任务的所有子任务在派发给 Work Agent 之前，必须经过 Architect 进行 DNA 状态分析：

1. **分析**：读取相关 `.dna/` 文件，扫描工作区代码结构，判断 DNA 状态（0~3）
2. **思考**：根据状态决定动作——新建 / 跳过 / 补齐 / 标记 spec
3. **执行**：通过 `cbim dna` 命令完成 DNA 操作，返回任务上下文包

详见：[业务知识治理循环](./WORKFLOW-ARCHITECT.zh-CN.md)

## 路由分类

| 路由目标 | 触发条件 |
|----------|----------|
| 执行任务（Decompose → Architect → WorkAgent） | 代码实现、功能开发、bug 修复 |
| 业务层 CRUD（直接到 Architect） | 模块设计、DNA 管理、合规审查 |
| 能力层 CRUD（直接到 HR） | agent 招募/训练/评估/归档 |
