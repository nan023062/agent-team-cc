# Skill: Agent 培训（HR）

> 从中期记忆的能力条目中提炼信号，将已验证的模式升格为 Skill 或内化进 Soul，提升 work agent 能力上限。

## 触发场景

- 考核结论为"能力不足，需培训"
- 助手反映某 agent 重复犯同类错误
- 评审官持续打回同一 agent 的交付物
- 中期记忆 `capability-<agent-id>.md` 的治理建议出现未勾选项

---

## 培训流程

### Step 1 — 读取中期能力条目

列出 medium tier 中该 agent 的条目：

```bash
.venv/bin/python -m memory.engine.cli query "" --tier medium --top-k 20
```

找到 `capability-<agent-id>.md`，用 Read 工具读取完整内容。

重点读取：
- `## MUST 记录`：违反过的原则约束（负向信号）
- `## HOW 记录`：已验证的有效流程（正向信号）
- `## 摘要`：对该 agent 当前能力状态的综合判断
- `## 治理建议`：上次提炼时标记的待处理项

### Step 2 — 按四象限判断升格目标

| 象限 | 信号内容 | 升格目标 | 升格条件 |
|------|---------|---------|---------|
| **MUST** | 不得违反的行为约束 | Soul（`## 原则` 部分） | 出现 ≥`distill.must_review_threshold` 次（默认 2，见 `memory/config.json`） |
| **HOW**（已验证） | 跨任务复用的有效流程 | Skill 文件 | 出现 ≥`distill.how_to_skill_threshold` 次，且跨项目成立（默认 3，见 `memory/config.json`） |
| **HOW**（未验证） | 仅出现 1-2 次 | 保留在中期，继续观察 | 继续积累 |

**可移植性自检**（MUST / HOW 升格前必做）：
> 把这条内容放到另一个项目、另一种语言的代码库里，还有意义吗？
- 有意义 → 升格（soul / skill）
- 没有意义，依赖当前项目上下文 → 保留在 medium，不升格

### Step 3 — 写入 Soul 或新增 Skill

**更新 Soul**（处理 MUST 信号）：

编辑 `.claude/agents/<id>/<id>.md`：

```markdown
## 原则
（追加新的行为准则，保持简洁，每条一行）
- 执行批量删除前必须展示预期变更范围并获得确认
- 遇到未定义的业务术语必须先澄清再执行，不得自行解读
```

不改动 frontmatter（`model`、`tools` 需用户确认）。

**新增 Skill**（处理 HOW 信号）：

```
.claude/agents/<id>/skills/<skill-name>.md

# Skill: <场景名称>

## 触发条件
（什么情况下启用此 skill）

## 步骤
1. ...
2. ...

## 输出格式
（期望的交付物格式）

## 边界与注意事项
（不该做什么、已知的边界条件）
```

### Step 4 — 更新中期条目的治理建议

勾选已完成的治理建议项，防止重复处理：

```markdown
## 治理建议
- [x] 提炼为 Skill（HOW 模式出现 ≥`how_to_skill_threshold` 次）  ← 已完成
- [x] 内化进 Soul（MUST 原则已验证稳定）                         ← 已完成
- [ ] 触发 HR 考核（能力缺口重复出现 ≥`must_review_threshold` 次）← 待处理
```

### Step 5 — 汇报

向助手汇报：

```
## 培训汇报 — <agent-id>

### Soul 更新
- 新增原则：[内容]（来源：capability-<id>.md MUST 记录 × N 次）

### 新增 Skill
- <skill-name>：[一句话描述]（来源：HOW 记录 × N 次）

### 保留观察
- [内容]（仅出现 N 次，继续积累）

### 未升格原因
- [内容]：项目特有细节，不满足跨项目可移植性
```
