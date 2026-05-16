# Skill: ChromaDB 记忆操作（HR）

查询涉及特定 agent 的历史 session 记忆，用于能力考核和记忆提炼。

## 使用时机

- 能力考核前：获取某 agent 的历史 session，评估执行质量
- 记忆提炼：判断哪些 session 内容可升格为 skill

## 查询命令

```bash
# 查询某 agent 相关记忆（语义检索）
.venv/bin/python tools/chroma_query.py --agent <agent-id> --query "<查询意图>" --top-k 10

# 示例：查询 programmer 的决策记录
.venv/bin/python tools/chroma_query.py --agent programmer --query "架构决策 设计原因" --top-k 10

# 示例：查询 programmer 的踩坑记录
.venv/bin/python tools/chroma_query.py --agent programmer --query "踩坑 问题 incident" --top-k 5

# 输出 JSON 供程序处理
.venv/bin/python tools/chroma_query.py --agent programmer --query "寻路实现" --json
```

## 写入记忆

HR 完成任务后写入 session 记忆：

```bash
.venv/bin/python tools/chroma_write.py \
    --agent hr \
    --slug <简短描述，如 programmer-assessment-2026-05> \
    --content "<本次 session 的关键事实：考核了谁、发现什么、做了什么决策>" \
    --tags <类型标记，如 assessment reshape>
```

## 升格判断

从 agent 的历史记忆中提炼：
- 某技术模式出现 ≥2 次 → 升格为 agent skill（写入 `.claude/agents/<id>/skills/`）
- 某踩坑出现 ≥2 次 → 写入 skill 的注意事项节
- agent 能力范围稳定 → 更新 agent `.md` 的 `capabilities` 节

升格后原始记忆无需删除，ChromaDB 保留原始记录。
