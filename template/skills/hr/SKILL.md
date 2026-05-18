# Skill: 人力治理（HR）

调用 HR subagent 执行能力层治理任务。

---

## 触发场景

| 场景 | 说明 |
|------|------|
| 能力缺口 | 现有 agent 无法覆盖所需任务，申请新 agent |
| 匹配 agent | 描述任务类型，HR 从现有 work agent 中匹配 |
| 培训 / 升格 | agent 反复出现同类问题，需要 skill 提炼或 soul 更新 |
| 日常信号采集 | 采集 work agent 能力缺口信号，见 `daily-signal.md` |
| 周度考核 | 评估 agent 执行质量并培训，见 `weekly-assessment.md` |
| 归档 | 某 agent 不再需要，回收其定义文件 |

---

## 人力申请流程

```
主 agent 拆解任务，发现缺少合适的执行 agent
   ↓
派发 HR（描述所需能力）
   ↓
HR 扫描 .claude/agents/，排除核心 4 个，匹配 work agents
   ├─ 有匹配 → 返回 agent 文件路径，主 agent 直接派发
   └─ 无匹配 → HR 起草新 agent → 用户确认 → 创建文件 → 通知主 agent
```

---

## 派发方式

```
你是 HR。读取 .claude/agents/hr/hr.md 加载你的完整身份。

本次任务：
  [具体任务描述，如：匹配一个能处理 Unity Shader 的 agent /
   对 programmer 做本周考核 / 招募一个数据分析 agent]

完成后输出结构化结果。
```

---

## 铁律

- 主 agent 不直接读写 `.claude/agents/`，一律通过 HR
- 核心 4 个 agent（助手 / 架构师 / 评审官 / HR）永远不在 HR 治理范围内
- 新 agent 草稿须经用户确认后才能落地
