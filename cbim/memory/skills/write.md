# Skill: 写短期记忆（Session Entry）

**主 agent 专用。由 Stop hook 自动触发，通常无需手动执行。**

---

## 触发方式

| 方式 | 说明 |
|------|------|
| 自动（推荐） | Session 结束时 Stop hook 自动解析 transcript，写入并索引 entry |
| 手动 | Hook 未触发 / 需要补充重要信息时，主 agent 手动写入 |

---

## Entry 格式

文件路径：`memory/store/short/YYYY-MM-DD-main-<slug>.md`

```markdown
---
tier: short
tags: session
modules: combat pathfinding   # 可选，涉及的模块名（空格分隔）
---

## 任务概述
（用户的原始请求，一两句话概括）

## Subagent 执行记录

### <subagent 描述>
结果：<关键输出摘要>

## 写入/修改文件
- path/to/file

## 信号
- [ ] 能力缺口：agent-id: 描述
- [ ] 优秀模式：agent-id: 描述
- [ ] 知识更新候选：模块名: 描述
```

---

## 信号填写规范

信号是提炼中期记忆的原料：

| 信号类型 | 格式 | 示例 |
|---------|------|------|
| 能力缺口 | `agent-id: 描述` | `programmer: 无法处理并发写入场景` |
| 优秀模式 | `agent-id: 描述` | `architect: 先出 contract 再出 architecture 效率更高` |
| 知识更新候选 | `模块名: 描述` | `combat: 伤害计算接口签名已变更` |

未发现则留空，不要删除行。

---

## 手动写入后索引

写入文件后，调用引擎建立向量索引：

```bash
.venv/bin/python -m memory.engine.cli add memory/store/short/<filename>.md --tier short
```
