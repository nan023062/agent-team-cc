# tools/

mem0 记忆系统工具脚本。环境变量 `MEM0_API_KEY` 必填（在 app.mem0.ai 注册获取）。

---

## mem0_write.py — 写入记忆

agent 完成任务后写入 session 记录，双写到本地文件 + mem0 Cloud。

```bash
python3 tools/mem0_write.py \
    --agent <agent-id> \
    --slug  <简短描述> \
    --content "<session 内容>" \
    --modules <模块名，空格分隔> \
    --tags    <标记，空格分隔>
```

**示例：**

```bash
python3 tools/mem0_write.py \
    --agent programmer \
    --slug fix-auth-token-expiry \
    --content "JWT token 过期时间单位错误（秒 vs 毫秒），已修复并补测试。" \
    --modules auth \
    --tags incident decision
```

---

## mem0_query.py — 查询记忆

语义检索 mem0 Cloud，返回相关 entry 的文件名和摘要。拿到文件名后按需读取 `memory/entries/` 原文。

```bash
# 按 agent 查（HR 用）
python3 tools/mem0_query.py --agent programmer --query "踩坑 问题" --top-k 10

# 按模块查（架构师用）
python3 tools/mem0_query.py --module combat --query "架构决策" --top-k 5

# 输出 JSON 供程序处理
python3 tools/mem0_query.py --agent programmer --query "缓存策略" --json
```

---

## mem0_reimport.py — 重建 Cloud 索引

从本地 `memory/entries/` 全量重建 mem0 Cloud 数据。本地文件是源头，Cloud 可随时重建。

```bash
# 预览，不实际写入
python3 tools/mem0_reimport.py --dry-run

# 全量重建
python3 tools/mem0_reimport.py

# 只重建某个 agent 的记录
python3 tools/mem0_reimport.py --agent programmer
```

**需要重建的场景：**
- 换了 `MEM0_API_KEY`（新 key 对应空库）
- mem0 Cloud 数据意外丢失
- 团队新成员想同步历史记忆到自己的 Cloud 账号
- 本地 entries 比 Cloud 多（离线期间写了很多条）
