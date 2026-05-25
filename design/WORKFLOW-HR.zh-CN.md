# CBIM HR 的能力管理（治理子循环流程图）

> 全貌索引文档。父循环（治理根）见 [`WORKFLOW-DREAM.zh-CN.md`](./WORKFLOW-DREAM.zh-CN.md)，本文不展开。
> 位置图见 [`LOOPS-OVERVIEW.zh-CN.md`](./LOOPS-OVERVIEW.zh-CN.md)；与业务轴的对偶关系见 [`WORKFLOW-ARCHITECT.zh-CN.md`](./WORKFLOW-ARCHITECT.zh-CN.md)。

---

## 一句话定位

**HR 只持有一棵治理子循环流程图——回头式重构（扫已有能力册的健康度并产建议）。** 该子循环挂在治理根之下，由派工 prompt 头部携带的治理模式标识识别。

---

## 第一部分：执行轴上的 HR 边界（v3.6 变更说明）

### 1.1 v3.6 撤掉了 HR 执行子循环

历史上 HR 同时持有"执行子循环（前向式匹配 / 招募）"与"治理子循环（回头式扫健康度）"两棵子循环。**v3.6 已撤掉 HR 执行子循环。** 现在执行根派 Work Agent 前由主 agent 用系统级 MCP `agent_list` 查能力册，直接根据 `required_capability` 匹配 `.claude/agents/*.md`，匹配不到回退到 `programmer`——读侧不再走 HR。

边界判定的权威依据见 [`v1/kernel/cbi/agents/.dna/module.md`](../v1/kernel/cbi/agents/.dna/module.md)：**`agent_list` 是系统级查询能力所有 agent 都有权限；HR 只在写侧（招 / 训 / 治）出现。** 即：

- **读侧（匹配 / 查询）** 不归 HR——任何 agent 都能直接调 `agent_list`，因此执行根无需为查能力册而 yield 给 HR。
- **写侧（招募 / 训练 / 治理）** 仍归 HR——新建 agent 文件、训练已有 agent、扫健康度产建议这些动作必须经过 HR。

执行根上仍保留的两条 HR 相关路径：

- **`hr` mode** — 用户显式说"招个 X agent" / "把这个 agent 训成 Y"时，主 agent 直答给 HR，HR 在单轮内完成写动作。
- **`hr_gov` 治理子树** — 治理根后台扫能力册，本文档第二部分展开。

执行根的派工拓扑见 [`WORKFLOW-EXECUTION.zh-CN.md`](./WORKFLOW-EXECUTION.zh-CN.md) §4。

---

## 第二部分：HR治理子循环流程图

### 2.1 触发与定位

挂在治理根之下，由治理根的"派 HR 治理"节点 yield 触发，prompt 头部带治理模式标识。目标是对能力册做体检。**回头式**：不响应任何当前任务，只看已有 agent 的健康度与结构。

### 2.2 HR治理子循环流程图（Mermaid）

```mermaid
flowchart TD
    Yield(["接 yield<br/>携带治理模式标识"])
    Load["加载能力册与近期派工/评估痕迹"]

    S1["扫闲置"]
    S2["扫失能"]
    S3["扫累计能力缺口"]
    S4["扫声明与表现漂移"]
    S5["扫能力重复"]
    S6["扫职责过宽"]

    Classify{"按动作类别归类"}
    Safe["安全动作<br/>刷新评估字段 / 索引 / 治理日志"]
    SafeDo["立即执行（幂等）"]
    Risky["危险动作<br/>归档 / 补漏招募 / 合并 / 强制重训 / 拆分"]
    Advise["只产建议，不执行"]

    Build["装配治理报告"]
    Return(["回治理根<br/>由治理根汇总落盘"])

    Yield --> Load
    Load --> S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> Classify
    Classify -->|安全| Safe --> SafeDo --> Build
    Classify -->|危险| Risky --> Advise --> Build
    Build --> Return
```

### 2.3 节点职责表（治理子循环）

| 节点 | 职责 | 边界 |
|------|------|------|
| 加载能力册与痕迹 | 读全量 agent 与近期派工 / 评估痕迹 | 只读，不修改 |
| 六类扫描 | 闲置 / 失能 / 累计能力缺口 / 漂移 / 重复 / 职责过宽 | 不响应当前任务 |
| 按动作类别归类 | 区分安全动作与危险动作 | 分类依据：是否幂等可回滚 |
| 安全动作 | 评估字段、索引、治理日志这类幂等更新 | 立即执行 |
| 危险动作 | 涉及结构调整或 agent 进出册的操作 | 仅写入建议，待用户决策 |
| 装配治理报告 | 汇总已执行的安全动作与待决建议 | 不直接通知用户 |

---

## 第三部分：HR 在两根上的对比

| 维度 | 执行根（v3.6 起） | 治理根 |
|------|------------------|--------|
| HR 是否有子循环 | 否——读侧由主 agent 直接调 `agent_list`；写侧 `hr` mode 走单轮直答，不展开子循环 | 是——治理子循环流程图（第二部分） |
| 触发方 | 用户显式写动作请求（招 / 训），由模式分类落到 `hr` mode | 治理根派 HR 治理 |
| 产出物 | 单轮写动作结果（新 agent 文件 / 已训 agent / 拒绝说明） | 治理报告（安全动作 + 待决建议） |
| 衔接 | 直答回主 agent，汇总渲染给用户 | 交还治理根汇总落盘并在下次 SessionStart 呈现 |

---

## 第四部分：与业务轴的对偶

能力轴（HR 管）与业务轴（Architect 管）互为镜像：业务轴新增模块可触发能力轴招募对应专域 agent；新 agent 孵化反过来携带新的业务领域知识。两轴在治理侧对偶完整——各持一棵治理子循环流程图；执行侧则不对称——Architect 仍有执行子循环（产 ContextPack），HR 在执行轴上只暴露 `agent_list` 这一系统级读接口与 `hr` mode 单轮写直答，不再持有子循环。详见 [`WORKFLOW-ARCHITECT.zh-CN.md`](./WORKFLOW-ARCHITECT.zh-CN.md)。
