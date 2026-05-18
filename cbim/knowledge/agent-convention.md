# Agent 能力层约定

> 能力层由 HR 治理，与内容层（`.dna/`）严格分离。

## 核心概念

**Agent**：`.claude/agents/<id>/` 目录下定义的执行单元，由一个 `<id>.md` 文件描述其身份、原则与技能。

**核心 Agent**（永久只读，HR 不得修改）：`architect`、`hr`、`auditor`，以及主 session（`CLAUDE.md`）。

**Work Agent**：由 HR 按需创建、培训、考核、归档的执行者。能力范围受单一职责约束。

---

## Agent 目录结构

```
.claude/agents/
└── <id>/
    └── <id>.md          # agent 完整定义（frontmatter + soul）
```

> **Skills 不在 agent 目录内。** 操作技能文档统一放在 `cbim/knowledge/skills/`，agent 的 Skills 表格通过路径引用。

---

## <id>.md 格式

```markdown
---
name: <显示名>
description: <一句话定位，供助手决策派发时参考>
model: claude-sonnet-4-6
tools: Read, Write, Edit, Glob, Grep, Bash
---

## 职责

<该 agent 做什么，不做什么>

## 原则

1. <行为边界>
2. <判断准则>
3. <协作规范>

## 触发场景

- <助手何时应该派发此 agent>

## Skills

| 场景 | Skill 文件 |
|------|-----------|
| <场景描述> | `cbim/knowledge/skills/<skill-name>/SKILL.md` |
```

---

## frontmatter 字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | ✅ | 显示名，可含中文 |
| `description` | ✅ | 助手派发决策依据，简洁、准确 |
| `model` | ✅ | 推荐 `claude-sonnet-4-6`；高复杂度任务用 `claude-opus-4-6` |
| `tools` | ✅ | 最小必要权限原则，不授予不需要的工具 |

---

## Soul / Identity 写作原则

**可移植性铁律**：soul 只含专业能力，不含任何项目特定内容。

自检：把这段内容放到另一个完全不同的项目里，它还有意义吗？
- 有意义 → 可以写入 soul
- 没有意义 → 留在 `cbim/memory/store/`，不升格

**写什么**：
- 性格与说话方式（让 agent 有辨识度，协作更自然）
- 职责边界（做什么 / 不做什么）
- 判断原则（面对歧义时如何决策）
- 触发场景（助手何时该派发）

**不写什么**：
- 项目名称、模块名、业务逻辑
- 当前任务状态、临时规则
- 对其他具体 agent 的硬编码依赖（用角色而非 id 描述协作）

---

## Agent 生命周期

```
招募（scaffold）
    ↓
执行任务（由助手派发）
    ↓
考核（HR 定期评估）
    ├─ 能力不足 ──→ 培训（提炼 skill / 更新 soul）
    ├─ 职责过宽 ──→ 裂变（拆分为多个专精 agent）
    └─ 长期闲置 ──→ 归档（.md.archived）
```

---

## CRUD 工具

```bash
# 列出所有 agents
python cbim/knowledge/engine/cli.py agents list

# 查看 agent 详情
python cbim/knowledge/engine/cli.py agents show <name>

# 创建新 agent（生成骨架文件）
python cbim/knowledge/engine/cli.py agents scaffold <name> --description "..."

# 归档 agent
python cbim/knowledge/engine/cli.py agents archive <name>
```
