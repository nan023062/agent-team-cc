# Memory — 独立存储+查询服务

> 项目本地的记忆服务。被动响应方，对外只暴露 4 个只读接口；写入由 3 条专用入口经 `crud/` 完成。
> 详细架构与边界见 [`design/WORKFLOW-MEMORY.zh-CN.md`](../../../design/WORKFLOW-MEMORY.zh-CN.md) 与 `.dna/module.md`。

## 对外契约（只读）

| 接口 | 用途 |
|------|------|
| `query(text, *, tier, limit, ...)` | 语义/关键词检索 |
| `scan(filter)` | 结构化过滤枚举（含 `promote_candidate`） |
| `get(id_or_path)` | 精确取值 |
| `stats(filter)` | 统计/观测（字段稳定，audit 依赖） |

```python
from memory import query, scan, get, stats
```

完整契约见 `.dna/contract.md`。

## 写入入口（不在对外契约）

| 入口 | 谁触发 |
|------|--------|
| `memory_write` MCP 工具 | LLM |
| `cbim memory ...` CLI | 人 |

两条入口都构造 `MemoryBackend` 后调 `crud.primitives.write`。`write` 是 **一体两步**：落盘 `medium/` + 同步触发 `compaction.identify` 暂存提升候选；同步调 `engine.retrieval.index_upsert("memory_medium", ...)` 保证检索索引与存储一致；调用方无感知。

v2 起本模块**不拥有短期记忆**：原 Stop hook 写 `short/` 的路径已废弃。短期记忆 = Claude Code 自身的 `~/.claude/projects/<slug>/*.jsonl` transcript，由 `engine.retrieval` 的 `transcript` 源在 hook 触发时索引；`engine.dream` 的治理循环负责蒸馏超龄 transcript 为 medium 条目。

---

## 目录结构

```
memory/
├── __init__.py            ← 父 facade，re-export query/scan/get/stats
├── _facade.py             ← 4 接口实现（转发，零业务逻辑）
├── _config.py             ← 配置合并器（hooks / cli / writer 共用）
├── cli.py                 ← argparse 入口（被 cbim memory 命令 dispatch）
├── session_loader.py      ← load_context（被 cbim_session_start hook 调）
├── config.py              ← 用户配置（CONFIG dict）
├── .dna/                  ← 模块知识（governance）
├── crud/                  ← 写入子模块
│   ├── primitives.py      ← write / update / delete（同步调 retrieval.index_upsert）
│   ├── backend.py         ← MemoryBackend ABC
│   ├── file_backend.py    ← FileBackend
│   └── chroma_backend.py  ← ChromaBackend
├── compaction/            ← 压缩升级子模块
│   ├── candidates.py      ← .cbim/memory/candidates/ 工作区
│   ├── identifier.py      ← identify（由 write 同步调）
│   ├── compactor.py       ← compact（候选蒸馏）
│   ├── promote_builder.py ← 提升候选打标（被 scan 拉走）
│   ├── archiver.py        ← sweep_expired（归档）
│   ├── rebuilder.py       ← rebuild（重建索引）
│   └── health.py          ← HealthChecker
└── README.md
```

数据落地（独立于代码树）：

```
.cbim/memory/
├── medium/                ← 中期 entries（蒸馏 .md，gitignore）
├── candidates/            ← 压缩升级工作区（gitignore）
├── .index/                ← FileBackend 索引（gitignore）
└── .chroma/               ← ChromaBackend 索引（gitignore，可选）
```

（短期记忆不在本模块路径下：见 `~/.claude/projects/<slug>/*.jsonl`，由 `engine.retrieval` 的 `transcript` 源管理。）

---

## 替换后端

1. 新建实现：在 `crud/` 下新建 `<your_backend>.py`，继承 `MemoryBackend`（`crud/backend.py`）
2. 切换：修改 `_facade.py` 的 backend 选择逻辑（或在调用方显式传入新 backend 实例）
3. 其余代码无需修改 —— 4 个对外接口签名稳定

---

## CLI 参考

```bash
# 由 SessionStart hook 自动 in-process 调用（无 CLI）：
#   memory.session_loader.load_context
# （Stop hook 不再写 memory；它只把 transcript 推到 engine.retrieval 的 transcript 源。）

# 手动 / skill 中使用
cbim memory query "查询意图" [--tier medium] [--top-k N] [--verbose]
cbim memory add <path> --tier medium
cbim memory cleanup [--keep-days N]
cbim memory reindex [--tier medium]

# 预览：统一仪表盘
cbim dashboard [--port 8765] [--no-browser]
```

---

## 安装 ChromaBackend（可选）

```bash
pip install chromadb
```

默认使用 FileBackend，无需额外依赖。

---

## 配置（`memory/config.json`）

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
