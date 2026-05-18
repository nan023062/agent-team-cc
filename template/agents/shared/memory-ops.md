# Skill: 记忆操作（通用）

所有 agent 均可使用。**每次任务结束，必须自动写入 entry。** 无需用户提醒，无需助手要求，这是任务完成协议的最后一步。

---

## 写入 Entry（任务结束必须执行）

任务完成后，**立即**创建记录文件。无论任务成功、部分完成还是遇到阻塞，均需写入。

**文件路径**：`memory/entries/YYYY-MM-DD-<agent-id>-<slug>.md`

```markdown
---
modules: <模块名，空格分隔，可省略>
tags: decision incident constraint blocked refactor
---

## 任务概述
（做了什么）

## 关键事件
（架构决策、踩坑、阻塞点、用户反馈——只写非平凡的事实）

## 信号
- [ ] 能力缺口：（描述）
- [ ] 优秀模式：（描述）
- [ ] 知识更新候选：（描述）
```

`date` 和 `agent` 从文件名自动提取，无需在 frontmatter 中填写。

写完文件即可，**无需手动更新索引**。下次查询时自动同步。

---

## 向量查询

> 查询不会重建索引。索引只在写入新 entry 后需要更新（见"写入 Entry"节）。

```bash
# 按 agent 过滤（HR 用：考核某 agent 的历史 session）
.venv/bin/python memory/memory_query.py "踩坑 问题" --agent programmer --top-k 10

# 按模块过滤（架构师用：查某模块的历史决策）
.venv/bin/python memory/memory_query.py "架构决策 约束" --module combat --top-k 10

# 不过滤，全局查询
.venv/bin/python memory/memory_query.py "查询意图" --top-k 5

# 附带元数据（agent、日期、相似度分数）
.venv/bin/python memory/memory_query.py "缓存策略" --verbose
```

**输出**：每行一个文件路径。按路径读取 markdown 文件获取完整内容。

---

## 读取结果

```
# 工具输出示例：
memory/entries/2026-05-10-programmer-fix-auth.md
memory/entries/2026-04-22-architect-combat-split.md

# 按路径读取文件即可获得完整原文
```

---

## 升格判断

| 出现频率 | 升格目标 |
|---------|---------|
| 某能力模式 ≥2 次 | → agent skill（`.claude/agents/<id>/skills/`） |
| 某踩坑 ≥2 次 | → skill 注意事项节 |
| 某架构决策稳定 | → `.aimodule/architecture.md` 关键决策节 |
| 某确定性流程成熟 | → `.aimodule/workflows/` |

升格后原始 entry 保留，不删除、不修改。

---

## 索引说明

`memory/chroma_db/` 是向量索引，不提交 git。  
查询时自动按 mtime 增量同步，无需手动维护。

首次安装或索引损坏时手动重建：
```bash
.venv/bin/python memory/memory_index.py
```
