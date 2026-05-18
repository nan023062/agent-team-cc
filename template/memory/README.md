# memory/ — 记忆系统

markdown 文件是唯一数据源（`memory/entries/`，可提交 git）。  
ChromaDB (`memory/chroma_db/`) 仅作向量索引，不提交 git，可随时从明文文件重建。

---

## 安装

```bash
# 在项目根目录（首次）
python3 -m venv .venv
.venv/bin/pip install -r memory/scripts/requirements.txt
```

---

## 工作流

```
1. agent 写 entry → memory/entries/YYYY-MM-DD-<agent>-<slug>.md
2. 向量查询       → .venv/bin/python memory/scripts/memory_query.py "查询意图"
                    （自动同步索引，无需额外步骤）
3. 读源文件       → 按返回路径读取 markdown 原文
```

`memory_index.py` 仅用于**首次安装**或**索引损坏**时手动重建。

---

## memory_index.py — 构建向量索引

扫描 `memory/entries/*.md`，增量更新 ChromaDB 索引。

```bash
.venv/bin/python memory/scripts/memory_index.py
# 指定其他目录
.venv/bin/python memory/scripts/memory_index.py --entries-dir path/to/entries
```

---

## memory_query.py — 向量检索

返回语义最相关的 entry 文件路径，**不返回内容**，调用方负责读取文件。

```bash
# 基本查询（返回 top-5 文件路径）
.venv/bin/python memory/scripts/memory_query.py "查询意图"

# 过滤 agent（HR 用）
.venv/bin/python memory/scripts/memory_query.py "踩坑 问题" --agent programmer --top-k 10

# 过滤模块（架构师用）
.venv/bin/python memory/scripts/memory_query.py "架构决策" --module combat --top-k 10

# 查询前先更新索引
.venv/bin/python memory/scripts/memory_query.py "寻路算法" --reindex

# 输出时附带元数据（agent、日期、相似度）
.venv/bin/python memory/scripts/memory_query.py "缓存策略" --verbose
```

**输出格式：**
- 默认：每行一个文件路径
- `--verbose`：路径后附 `# agent=xxx date=xxx score=x.xx`

---

## Entry 格式

文件命名：`YYYY-MM-DD-<agent-id>-<slug>.md`

```markdown
---
modules: combat pathfinding
tags: decision incident
---

## 任务概述
（做了什么）

## 关键事件
（架构决策、踩坑、阻塞点——只写非平凡的事实）

## 信号
- [ ] 能力缺口：...
- [ ] 优秀模式：...
```

`date` 和 `agent` 从文件名自动提取；`modules` 和 `tags` 通过 frontmatter 指定。

---

## 本地 vs 服务器模式

| 模式 | 配置 |
|------|------|
| 本地（默认） | 不设环境变量，索引存 `memory/chroma_db/` |
| 团队服务器 | `export CHROMA_HOST=<ip>; export CHROMA_PORT=8000` |

索引可随时从 `memory/entries/` 重建，丢失无损失。
