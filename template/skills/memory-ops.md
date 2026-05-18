# Skill: 记忆操作（主 agent 专用）

**只有主 agent（助手）持有此 skill。Subagent 不直接操作记忆。**

记忆的读写由 Claude Code hook 自动处理，主 agent 无需手动触发：

| 时机 | Hook | 行为 |
|------|------|------|
| Session 开始 | `SessionStart` → `load-memory.py` | 查询近期 entry 注入为上下文 |
| Session 结束 | `Stop` → `write-memory.py` | 解析 transcript，自动写入 entry |

本 skill 仅用于 **session 中途主动查询**历史记忆。

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

## 升格判断

| 出现频率 | 升格目标 |
|---------|---------|
| 某 agent 能力缺口 ≥2 次 | → 派发 HR 培训，升格为 skill |
| 某架构决策稳定 | → 派发架构师更新 `.aimodule/architecture.md` |
| 某确定性流程成熟 | → 派发架构师更新 `.aimodule/workflows/` |

升格后原始 entry 保留，不删除、不修改。

---

## 索引说明

`memory/chroma_db/` 是向量索引，不提交 git，查询时自动增量同步。

首次安装或索引损坏时手动重建：
```bash
.venv/bin/python memory/memory_index.py
```
