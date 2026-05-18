# Skill: 查询记忆

**主 agent 专用。session 中途需要检索历史时使用。**

---

## 命令格式

```bash
# 跨层查询（短期 + 中期，推荐）
.venv/bin/python -m memory.engine.cli query "查询意图" --top-k 5 --verbose

# 只查短期记忆（近期 session）
.venv/bin/python -m memory.engine.cli query "查询意图" --tier short --top-k 5

# 只查中期记忆（压缩后的关键洞察）
.venv/bin/python -m memory.engine.cli query "查询意图" --tier medium --top-k 3
```

**输出格式（--verbose）：**
```
memory/store/short/2026-05-10-main-xxx.md  # tier=short date=2026-05-10 score=0.8821
memory/store/medium/capability-programmer.md  # tier=medium date=2026-05-15 score=0.7432
```

---

## 使用流程

1. 运行上述命令，获取文件路径列表
2. 按路径读取 markdown 原文（Read 工具）
3. 从原文提取与当前任务相关的上下文

---

## 索引损坏时重建

```bash
# 重建全部索引
.venv/bin/python -m memory.engine.cli reindex

# 只重建某一层
.venv/bin/python -m memory.engine.cli reindex --tier short
.venv/bin/python -m memory.engine.cli reindex --tier medium
```
