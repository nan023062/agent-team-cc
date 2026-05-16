# Skill: mem0 记忆查询（架构师）

查询涉及特定模块的历史 session 记忆，用于知识治理和模块健康考核。

## 使用时机

- 知识治理前：获取某模块的历史决策、踩坑、约束
- 模块健康考核：评估模块相关记忆积压量
- 替代 scan-memory 脚本做语义检索（命中率更高）

## 查询命令

```bash
# 查询某模块相关记忆（语义检索）
python3 tools/mem0_query.py --module <module-name> --query "<查询意图>" --top-k 10

# 示例：查询 combat 模块的架构决策
python3 tools/mem0_query.py --module combat --query "架构决策 设计原因" --top-k 10

# 示例：查询 combat 模块的踩坑记录
python3 tools/mem0_query.py --module combat --query "踩坑 问题 incident" --top-k 5

# 输出 JSON 供程序处理
python3 tools/mem0_query.py --module combat --query "模块约束" --json
```

## 写入记忆

架构师完成任务后，写入 session 记忆（双写：mem0 + 本地文件）：

```bash
python3 tools/mem0_write.py \
    --agent architect \
    --slug <简短描述，如 combat-split-decision> \
    --content "<本次 session 的关键事实：做了什么、决策了什么、遇到什么问题>" \
    --modules <涉及的模块，空格分隔，如 combat pathfinding> \
    --tags <类型标记，如 decision incident constraint>
```

## 升格判断

从查询结果中提炼：
- 同一决策出现 ≥2 次 → 升格到 `architecture.md` 关键决策节
- 同一踩坑出现 ≥2 次 → 考虑升格为 `workflow`
- 模块约束稳定 → 写入 `module.json` 或 `architecture.md`

升格后在 mem0 中对应的记忆无需删除，保留原始记录。
