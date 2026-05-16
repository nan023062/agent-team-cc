# tools/

记忆系统工具脚本，基于 ChromaDB。无需 API key，本地开箱即用，后续可切换到自建服务器。

---

## 本地 vs 服务器模式

| 模式 | 配置 | 适用场景 |
|------|------|---------|
| 本地（默认） | 不设环境变量 | 单机测试、MVP 阶段 |
| 服务器 | 设置 `CHROMA_HOST` | 团队共享记忆 |

**启动本地 ChromaDB 服务器：**
```bash
chroma run --path ./chroma_db --port 8000
```

**切换到服务器模式：**
```bash
export CHROMA_HOST=192.168.1.100   # 服务器 IP
export CHROMA_PORT=8000            # 默认 8000
```

---

## chroma_write.py — 写入记忆

agent 完成任务后写入 session 记录。

```bash
python3 tools/chroma_write.py \
    --agent <agent-id> \
    --slug  <简短描述> \
    --content "<session 内容>" \
    --modules <模块名，空格分隔> \
    --tags    <标记，空格分隔>
```

**示例：**
```bash
python3 tools/chroma_write.py \
    --agent programmer \
    --slug fix-auth-token-expiry \
    --content "JWT token 过期时间单位错误（秒 vs 毫秒），已修复并补测试。" \
    --modules auth \
    --tags incident decision
```

---

## chroma_query.py — 查询记忆

语义检索，直接返回原文，无需二次加载文件。

```bash
# 按 agent 查（HR 用）
python3 tools/chroma_query.py --agent programmer --query "踩坑 问题" --top-k 10

# 按模块查（架构师用）
python3 tools/chroma_query.py --module combat --query "架构决策" --top-k 5

# 输出 JSON 供程序处理
python3 tools/chroma_query.py --agent programmer --query "缓存策略" --json
```

---

## 查看明文

ChromaDB 查询直接返回原文，无需额外操作。也可以通过服务器 REST API 拉取：

```bash
# 拉取所有 entries（REST API）
curl http://localhost:8000/api/v2/tenants/default_tenant/databases/default_database/collections/memories/get
```
