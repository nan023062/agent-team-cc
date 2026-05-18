# Skill: 查询记忆

**主 agent 专用。session 中途需要检索历史时使用。**

---

## 命令格式

```bash
# 默认：返回最近修改的 top-k 条（短期 + 中期合并，按时间排序）
.venv/bin/python -m memory.engine.cli query "" --top-k 5

# 只查单层
.venv/bin/python -m memory.engine.cli query "" --tier short --top-k 5
.venv/bin/python -m memory.engine.cli query "" --tier medium --top-k 3
```

默认后端（FileBackend）按修改时间排序，查询文本参数忽略。
若已切换为语义后端（ChromaBackend），查询文本会参与相似度计算。

---

## 使用流程

1. 运行上述命令，获取文件路径列表
2. 按路径读取 markdown 原文（Read 工具）
3. 从原文提取与当前任务相关的上下文

---

## 常见场景

| 需要查什么 | 建议命令 |
|-----------|---------|
| 最近几次 session 做了什么 | `query "" --tier short --top-k 5` |
| agent 的能力模式摘要 | `query "" --tier medium --top-k 10`，再 Read capability-*.md |
| 某模块的历史决策 | `query "" --tier medium`，再 Read business-<module>.md |

---

## 索引重建

切换到语义后端后，需要将现有文件重新索引：

```bash
.venv/bin/python -m memory.engine.cli reindex
```
