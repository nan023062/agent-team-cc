# Skill: 短期记忆写入（Session）

**主 agent 专用。由 Stop hook 自动触发，通常无需手动执行。**

---

## 触发方式

| 方式 | 说明 |
|------|------|
| 自动（推荐） | Session 结束时 Stop hook 自动调用 `write-memory.py` 解析 transcript，写入 entry |
| 手动 | Hook 未触发 / 本次 session 有重要补充内容时，主 agent 手动补写 |

---

## Entry 格式

文件路径：`memory/entries/YYYY-MM-DD-main-<slug>.md`

```markdown
---
tags: session
---

## 任务概述
（用户的原始请求，一两句话概括）

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

## 信号填写规范

信号是提炼中期记忆的原料：

| 信号类型 | 填写内容 |
|---------|---------|
| 能力缺口 | `agent-id: 具体表现`（e.g. `programmer: 无法处理并发写入场景`） |
| 优秀模式 | `agent-id: 可复用的做法` |
| 知识更新候选 | `模块名: 需要更新的内容方向` |

未发现则留空，不要删除行。

---

## 手动补写步骤

1. 在 `memory/entries/` 创建文件，命名遵循 `YYYY-MM-DD-main-<slug>.md`
2. 按格式填写任务概述、subagent 执行记录、文件变动
3. 填写信号区——供后续 `distill.md` 提炼使用
