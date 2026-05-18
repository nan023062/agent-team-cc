# Skill: Agent 考核（HR）

> 评估 work agent 的表现，输出培训/裂变/归档建议。

## 触发场景

- 一批任务完成后（由助手或用户发起）
- 用户明确指出某 agent 表现不足
- 评审官连续打回同一 agent 的交付物（≥2次）

---

## 考核流程

### Step 1 — 收集表现证据

```bash
# 检索该 agent 近期记录
python cbim/memory/engine/cli.py query "<agent-name>" --top-k 15 --verbose

# 检索评审官的相关评审
python cbim/memory/engine/cli.py query "评审 <agent-name>" --top-k 5
```

阅读记忆，记录：
- 任务完成质量（按时交付 / 返工 / 被打回次数）
- 边界遵守情况（有无越权 / 漏报）
- 协作表现（与其他 agent 的配合度）

### Step 2 — 查看当前定义

```bash
python cbim/knowledge/engine/cli.py agents show <name>
```

对比 agent 的当前职责定义与实际表现，判断：

| 现象 | 结论 |
|------|------|
| 能力不足，但职责定义合理 | 培训 |
| 职责定义过宽，上下文膨胀 | 裂变 |
| 长期闲置，职责被他人覆盖 | 归档 |
| 表现良好，有可提炼经验 | 主动培训（升格） |

### Step 3 — 输出考核报告

向助手汇报，包含：

```
Agent：<id>
考核周期：<时间范围>
表现摘要：<2-3句>
结论：培训 / 裂变 / 归档 / 无需操作
建议：<具体行动>
依据记忆：<文件名列表>
```

### Step 4 — 执行结论

- **培训** → 执行 `hr-training.md`
- **裂变** → 执行 `hr-agents.md` 的裂变流程
- **归档** → 执行 `hr-agents.md` 的归档流程
- **无需操作** → 记录本次考核结果到短期记忆（由助手 session 结束时自动写入）
