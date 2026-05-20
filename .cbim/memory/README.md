# Memory — 记忆系统（短期和中期）

## 三层记忆模型

| 层级 | 存储 | 共享方式 | 说明 |
|------|------|---------|------|
| **短期** | `store/short/` | 用户本地（gitignore） | session 结束自动写入 |
| **中期** | `store/medium/` | 用户本地（gitignore） | 按关键字压缩，手动 distill |
| **长期** | `.claude/agents/` + `.dna/` | 团队 git-tracked | HR / 架构师治理 |

短期和中期是本地工作记忆。长期知识库（agent 能力文件、模块知识文件）才是团队共享资产。

---

## 目录结构

```
memory/
├── engine/
│   ├── base.py           ← MemoryBackend 抽象接口（替换后端只改这里）
│   ├── chroma_backend.py ← ChromaDB 实现
│   ├── engine.py         ← MemoryEngine 门面（add/query/delete/reindex/cleanup）
│   ├── writer.py         ← Session entry 写入逻辑（transcript 解析、格式化、索引）
│   ├── loader.py         ← Session 上下文加载逻辑（查询、读文件、拼装 context）
│   ├── cli.py            ← CLI 统一入口
│   ├── config.py         ← 配置加载器（含内置默认值）
│   └── requirements.txt
├── store/                ← 整体 gitignore
│   ├── short/            ← 短期 entries（session 级 .md）
│   ├── medium/           ← 中期 entries（关键字压缩 .md）
│   └── .chroma/          ← 向量索引（可随时从 store/ 重建）
├── skills/
│   ├── write.md          ← 手动补写 session entry
│   ├── query.md          ← 查询记忆
│   └── distill.md        ← 短期→中期提炼
└── config.json           ← 可调参数（keep_days、top_k 等）
```

---

## 架构流程

```
┌─────────────────────────────────────────────────────────────────┐
│  Claude Code 生命周期事件                                        │
└──────────────────┬──────────────────────┬───────────────────────┘
                   │ Stop                 │ SessionStart
                   ▼                      ▼
         ┌──────────────────┐   ┌──────────────────┐
         │ write-memory.py  │   │ load-memory.py   │   ← hooks（薄层，无业务逻辑）
         └────────┬─────────┘   └────────┬─────────┘
                  │ cli write-session      │ cli load-context
                  ▼                        ▼
         ┌──────────────────┐   ┌──────────────────┐
         │   writer.py      │   │   loader.py      │   ← engine 业务逻辑
         │                  │   │                  │
         │ · 解析 transcript │   │ · 查询向量索引    │
         │ · 格式化 entry    │   │ · 读 .md 原文    │
         │ · 写 store/short/│   │ · 拼装 context   │
         │ · 更新向量索引   │   └────────┬─────────┘
         └────────┬─────────┘            │ additionalContext JSON
                  │                      ▼
                  │            ┌──────────────────────┐
                  │            │  Claude 主 agent      │
                  │            │  （session 启动上下文）│
                  │            └──────────────────────┘
                  │
                  ▼
         ┌──────────────────────────────────────┐
         │  engine.py  ←→  ChromaDB (store/.chroma/)│
         └──────────────────────────────────────┘
                  ↑                    ↑
                  │ cli add            │ cli query / cleanup
                  │                   │
         ┌────────┴──────┐   ┌────────┴──────┐
         │  主 agent     │   │  主 agent     │
         │  (distill)    │   │  (skills/     │
         │               │   │   query.md)   │
         │ store/short/  │   └───────────────┘
         │   → 提炼 →    │
         │ store/medium/ │
         └───────────────┘
```

### 写入流程（session 结束）

```
transcript.jsonl
    → writer.py 解析（用户请求、subagent 调度、文件变更）
    → store/short/YYYY-MM-DD-main-<slug>.md
    → engine.add() → ChromaDB 索引
```

### 加载流程（session 启动）

```
loader.py
    → engine.query("最近任务 决策 问题 阻塞", balanced, top_k=3)
    → 读 .md 原文（短期 + 中期各取 top-3，round-robin 合并）
    → {"additionalContext": "..."} → Claude 上下文注入
```

### 提炼流程（主 agent 手动触发）

```
store/short/*.md
    → 按能力关键字（agent-id）/ 业务关键字（模块名）分组
    → LLM 压缩汇总
    → store/medium/<type>-<keyword>.md
    → engine.add() → ChromaDB 索引
    → cli cleanup --keep-days 3（删除 N 天前短期 entry）
```

---

## 替换后端

1. 新建 `engine/<your_backend>.py`，继承 `MemoryBackend`（`base.py`）
2. 在 `cli.py` 的 `_build_engine()` 替换 `ChromaBackend(...)` 为新实现
3. 其余所有代码无需修改

---

## 安装

```bash
python3 -m venv .venv
.venv/bin/pip install -r memory/engine/requirements.txt
```

---

## CLI 参考

```bash
# hook 命令（通常由 hook 自动调用）
python .cbim/engine memory write-session <transcript_path>
python .cbim/engine memory load-context

# agent 命令（手动 / skill 中使用）
python .cbim/engine memory query "查询意图" [--tier short|medium] [--top-k N] [--verbose]
python .cbim/engine memory add <path> --tier short|medium
python .cbim/engine memory cleanup [--keep-days N]
python .cbim/engine memory reindex [--tier short|medium]

# 预览命令（启动本地 HTTP server，自动打开浏览器）
python .cbim/engine memory preview [--port 8765]
```

---

## 配置（memory/config.json）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `short_term.keep_days` | 3 | distill 后保留最近 N 天短期 entry |
| `short_term.max_request_chars` | 300 | entry 中用户请求截断长度 |
| `short_term.max_result_chars` | 600 | entry 中 agent 结果截断长度 |
| `short_term.max_slug_input_chars` | 50 | 文件名 slug 输入长度 |
| `short_term.max_slug_chars` | 30 | 文件名 slug 输出长度 |
| `query.default_top_k` | 5 | 手动查询每层返回数量 |
| `query.load_top_k` | 3 | session 启动时每层加载数量 |
| `query.entry_preview_chars` | 800 | 注入上下文时每条 entry 字符数 |
| `hooks.timeout_seconds` | 30 | CLI 子进程超时（秒） |
