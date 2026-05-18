# Skill: Agent 培训（HR）

> 从 session 记忆中提炼经验，升格为 skill / soul，提升 work agent 能力上限。

## 触发场景

- 考核结论为"能力不足，需培训"
- 助手反映某 agent 重复犯同类错误
- 评审官持续打回同一 agent 的交付物

---

## 培训流程

### Step 1 — 定位问题

从记忆中检索该 agent 的相关记录：

```bash
python cbim/memory/engine/cli.py query "<agent-name> 问题" --top-k 10
python cbim/memory/engine/cli.py query "<agent-name> 错误 教训" --top-k 10
```

阅读返回的记忆文件，识别：
- 反复出现的失误模式（≥2次 → 值得提炼）
- 被忽视的边界条件
- 与其他 agent 协作的摩擦点

### Step 2 — 判断升格层级

| 内容 | 升格目标 |
|------|---------|
| 特定场景的操作步骤 | Skill 文件（`skills/<name>.md`） |
| 行为边界、判断原则 | Soul 更新（`<id>.md` 的原则/立场部分） |
| 触发条件变化 | Soul 更新（`<id>.md` 的触发场景部分） |

**可移植性自检**：这段内容放到另一个项目里还有意义吗？
- 有意义 → 升格
- 没有意义（项目特有细节）→ 保留在 memory，不升格

### Step 3 — 写入 Skill 或更新 Soul

**新增 Skill**：

```
.claude/agents/<id>/skills/<skill-name>.md

格式：
# Skill: <场景名>
## 触发条件
## 操作步骤
## 输出格式
## 边界与注意事项
```

**更新 Soul**（编辑 `.claude/agents/<id>/<id>.md`）：
- 在 `## 原则` 中追加新的行为准则
- 在 `## 触发场景` 中补充新的派发条件
- 不改动 frontmatter（model/tools 需用户确认）

### Step 4 — 汇报

向助手汇报：
- 培训了哪个 agent
- 提炼了什么（skill 名称 / soul 变更内容）
- 原始依据（哪几条记忆）
