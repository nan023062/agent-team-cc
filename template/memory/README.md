# memory/ — 记忆系统

两层记忆 + 可替换后端。

```
memory/
├── engine/      ← CRUD 引擎（接口抽象 + ChromaDB 实现）
├── store/       ← 存储库
│   ├── short/   ← 短期记忆（session entries，.md，可 git 提交）
│   ├── medium/  ← 中期记忆（关键字压缩条目，.md，可 git 提交）
│   └── .chroma/ ← 向量索引（gitignore，可随时从 store/ 重建）
└── skills/      ← Agent 交互 skills（write / query / distill）
```

---

## 安装

```bash
# 在项目根目录（首次）
python3 -m venv .venv
.venv/bin/pip install -r memory/engine/requirements.txt
```

---

## CLI 用法

所有操作通过 `memory/engine/cli.py` 统一入口，在项目根目录运行：

```bash
# 索引一个 entry
.venv/bin/python -m memory.engine.cli add memory/store/short/xxx.md --tier short

# 查询（跨层，推荐）
.venv/bin/python -m memory.engine.cli query "缓存策略" --top-k 5 --verbose

# 只查短期 / 只查中期
.venv/bin/python -m memory.engine.cli query "agent 缺口" --tier short
.venv/bin/python -m memory.engine.cli query "模块决策" --tier medium

# 重建全部索引（首次安装或索引损坏时）
.venv/bin/python -m memory.engine.cli reindex
```

**输出格式（--verbose）：**
```
memory/store/short/2026-05-10-main-xxx.md  # tier=short date=2026-05-10 score=0.88
```
返回文件路径；读取原文用 Read 工具或 `cat`。

---

## 替换后端

1. 新建 `memory/engine/<your_backend>.py`，继承 `MemoryBackend`（`engine/base.py`）
2. 在 `engine/cli.py` 的 `_build_engine()` 中替换 `ChromaBackend(...)` 为你的实现
3. 其余代码无需修改

---

## 团队服务器模式

```bash
export CHROMA_HOST=<ip>
export CHROMA_PORT=8000
```

向量索引会连接远程 ChromaDB，`store/.chroma/` 不再使用。

---

## Agent Skills

| 场景 | 读取 |
|------|------|
| 补写 session entry | `memory/skills/write.md` |
| 检索历史记忆 | `memory/skills/query.md` |
| 短期→中期提炼 | `memory/skills/distill.md` |
