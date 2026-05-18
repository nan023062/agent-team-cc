# Skill: 记忆系统（主 agent 专用）

**只有主 agent（助手）持有此 skill。Subagent 不直接操作记忆。**

## 三层记忆

| 层级 | 存储 | 管理方式 |
|------|------|---------|
| **短期** | `memory/entries/` | Hook 自动写入，每次 session 结束即生成 |
| **中期（能力）** | `.claude/agents/<id>/skills/`、`<id>.md` | 提炼自短期，记录 agent 能力模式与 soul |
| **中期（知识）** | `.aimodule/` | 提炼自短期，记录模块架构决策与契约 |

---

## 短期记忆（自动）

由 Claude Code hook 驱动，主 agent 无需手动触发：

| 时机 | 行为 |
|------|------|
| Session 开始 | 查询近期 entry，自动注入为上下文 |
| Session 结束 | 解析 transcript，自动写入 entry |

---

## 记忆提炼（短期 → 中期）

定期扫描 `memory/entries/`，将反复出现的模式升格为中期记忆：

| 提炼任务 | Skill | 建议频率 |
|---------|-------|---------|
| 采集 agent / 模块升格信号 | `daily-signal.md` | 每日 |
| 执行升格（skill / soul / `.aimodule/` 更新）| `weekly-assessment.md` | 每周 |

---

## 按需查询（session 中途）

主 agent 在 session 中途需要检索历史记录时使用。

---

## Entry 格式（hook 自动生成，仅供参考）

文件命名：`YYYY-MM-DD-main-<slug>.md`

```markdown
---
tags: session
---

## 任务概述
（用户的原始请求）

## Subagent 执行记录

### <subagent 描述>
结果：<关键输出摘要>

## 写入/修改文件
- path/to/file

## 信号
- [ ] 能力缺口：
- [ ] 优秀模式：
- [ ] 知识更新候选：
```

---

## 向量查询（session 中途按需使用）

```bash
# 全局查询
.venv/bin/python memory/memory_query.py "查询意图" --top-k 5

# 按 subagent 过滤（了解某个 agent 的历史表现）
.venv/bin/python memory/memory_query.py "踩坑 问题" --agent programmer --top-k 10

# 附带元数据（日期、相似度分数）
.venv/bin/python memory/memory_query.py "架构决策" --verbose
```

输出：每行一个文件路径。按路径读取 markdown 原文获取完整内容。

---

## 索引说明

`memory/chroma_db/` 是向量索引，不提交 git，查询时自动增量同步。

首次安装或索引损坏时手动重建：
```bash
.venv/bin/python memory/memory_index.py
```
