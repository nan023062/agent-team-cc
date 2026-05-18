# Skill: 记忆提炼（短期 → 中期 → 长期）

**主 agent 专用。定期或按需触发。**

## 三层记忆流向

```
memory/store/short/   ← session 自动写入（本地）
        ↓  distill（按关键字压缩）
memory/store/medium/  ← 本地工作记忆，供 session 间参考
        ↓  升格（驱动 HR / 架构师）
.claude/agents/<id>/skills/   ← 长期能力知识（团队 git-tracked）
.aimodule/                    ← 长期内容知识（团队 git-tracked）
```

---

## 触发时机

| 频率 | 建议 |
|------|------|
| 每日 | 短期→中期：采集信号，压缩为中期条目 |
| 每周 | 中期→长期：汇总中期信号，驱动 HR / 架构师执行升格 |
| 按需 | 用户主动触发，或感知到 agent / 模块质量下滑时 |

---

## 关键字规则

| 类型 | 来源 | 示例关键字 |
|------|------|----------|
| 能力关键字（capability） | 信号行中的 agent-id | `programmer`, `architect`, `hr` |
| 内容关键字（content） | frontmatter `modules` 字段 + "知识更新候选"信号中的模块名 | `combat`, `auth-module` |

---

## Phase 1 — 短期 → 中期（每日）

**Step 1 — 扫描短期记忆**

读取 `memory/store/short/` 下近 N 天 entry 文件，提取：
- 「信号」区的每一条记录
- frontmatter `modules` 字段

**Step 2 — 按关键字分组并压缩**

对每个关键字，生成或更新 `memory/store/medium/<type>-<keyword>.md`：

```markdown
---
tier: medium
type: capability
keyword: programmer
updated: YYYY-MM-DD
sources: 12
---

## 摘要
（所有相关信号的压缩总结）

## 信号汇总
- 能力缺口 × 3: ...
- 优秀模式 × 2: ...
```

写入后更新索引：

```bash
.venv/bin/python -m memory.engine.cli add memory/store/medium/<file>.md --tier medium
```

---

## Phase 2 — 中期 → 长期（每周）

读取中期记忆，汇总信号，驱动长期知识库更新：

**能力信号 → HR → 长期能力知识**
- 目标文件：`.claude/agents/<id>/skills/`、`.claude/agents/<id>/<id>.md`
- 读 `.claude/skills/hr/SKILL.md`，派发 HR 执行 assessment / training skill

**内容信号 → 架构师 → 长期内容知识**
- 目标文件：`.aimodule/architecture.md`、`.aimodule/contract.md`
- 读 `.claude/skills/architect/SKILL.md`，派发架构师执行 knowledge-governance skill

**输出摘要格式：**

```
## 记忆提炼摘要（{日期范围}，{N} 条 entry）

### 能力信号 → 建议升格到 .claude/agents/
- [agent-id] 信号类型：描述

### 内容信号 → 建议升格到 .aimodule/
- [模块名] 信号类型：描述

### 建议后续行动
- 能力升格：派发 HR
- 知识治理：派发架构师
```
