# memory/ — 记忆系统

## 三层记忆模型

| 层级 | 存储位置 | 共享方式 | 格式 |
|------|---------|---------|------|
| **短期**（session） | `memory/store/short/` + ChromaDB | 用户本地，不共享 | markdown |
| **中期**（关键字压缩） | `memory/store/medium/` + ChromaDB | 用户本地，不共享 | markdown |
| **长期**（知识库） | `.claude/agents/` + `.aimodule/` | **团队共享，git-tracked** | 纯明文 |

短期和中期是本地工作记忆，帮助主 agent 在 session 间保持连续性。  
长期知识库是真正的团队资产——agent 能力文件和模块知识文件全部明文，方便 git 追踪和冲突管理。

---

## 目录结构

```
memory/
├── engine/      ← CRUD 引擎（接口抽象 + ChromaDB 实现）
├── store/       ← 本地存储库（整体 gitignore）
│   ├── short/   ← 短期记忆（session entries）
│   ├── medium/  ← 中期记忆（关键字压缩条目）
│   └── .chroma/ ← 向量索引（可随时从 store/ 重建）
└── skills/      ← Agent 交互 skills（write / query / distill）
```

---

## 安装

```bash
python3 -m venv .venv
.venv/bin/pip install -r memory/engine/requirements.txt
```

---

## CLI 用法

从项目根目录运行：

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

---

## 替换后端

1. 新建 `memory/engine/<your_backend>.py`，继承 `MemoryBackend`（`engine/base.py`）
2. 在 `engine/cli.py` 的 `_build_engine()` 中替换 `ChromaBackend(...)` 为你的实现
3. 其余代码无需修改

---

## Agent Skills

| 场景 | 读取 |
|------|------|
| 补写 session entry | `memory/skills/write.md` |
| 检索历史记忆 | `memory/skills/query.md` |
| 短期→中期提炼 | `memory/skills/distill.md` |
