# memory/ 统一记忆系统约定

> 所有记忆均为 agent session 记录，由执行任务的 agent 写入。  
> 压缩升格由 HR（能力维度）和架构师（内容维度）定期执行。

---

## 目录结构

```
memory/
└── entries/
    └── YYYY-MM-DD-<agent-id>-<slug>.md
```

所有 entry 平铺在 `entries/` 下，每条对应一次 agent 执行记录。  
每天可产生多条，命名唯一，多人团队并行写入无冲突。  
**entries/ 可提交 git**，是唯一数据源。

---

## Entry 格式

**文件命名**：`YYYY-MM-DD-<agent-id>-<slug>.md`

```markdown
---
modules: combat pathfinding
tags: decision incident
---

## 任务概述
（做了什么）

## 关键事件
（模块改动、架构决策、踩坑、阻塞点、用户反馈——只写非平凡的事实）

## 信号
- [ ] 能力缺口：（描述）
- [ ] 优秀模式：（描述）
- [ ] 模块知识更新候选：（描述）
```

`date` 和 `agent` 从文件名自动提取，无需在 frontmatter 中重复填写。

**tags 约定**（自由组合）：

| tag 前缀/关键词 | 用途 |
|----------------|------|
| `module-<name>` | 涉及某个模块，供架构师过滤 |
| `decision` | 包含架构决策 |
| `incident` | 踩坑或问题 |
| `constraint` | 新发现的约束 |
| `blocked` | 执行中遇到阻塞 |
| `refactor` | 代码/结构重构 |

---

## 存储架构

明文 markdown 文件是**唯一数据源**，ChromaDB 仅作向量索引。

| 内容 | 存储位置 | git |
|------|---------|-----|
| entry 原文 | `memory/entries/*.md` | ✅ 提交 |
| 向量索引 | `./chroma_db/` | ❌ gitignore |

**写入**：agent 直接创建 markdown 文件，无需调用脚本。

**向量查询**：按 `.claude/skills/memory/SKILL.md` 执行，返回文件路径后读取 markdown 原文。

**本地 vs 服务器：**

| 阶段 | 配置 |
|------|------|
| 本地测试 | 不设 `CHROMA_HOST` |
| 团队服务器 | `export CHROMA_HOST=<ip>` |

---

## 写入方

任意 agent 在任务结束后自行创建 entry 文件，或由助手代写。  
内容不限：可以是模块改动、设计决策、踩坑经验、阻塞记录——只要是这次 session 里值得记录的事实。

---

## 压缩升格

**HR** 定期查询 entries，过滤 `agent=<id>`，提炼反复出现的能力模式：
→ agent skill 升格 / soul 更新

**架构师** 定期查询 entries，过滤 `module=<name>`，提炼模块相关决策与约束：
→ `.aimodule/` 知识三件套 / workflows 更新

两条管线共用同一份原始记录，从不同维度提炼。

---

## 铁律

- `memory/entries/` 只写原始记录，不写已压缩的结论
- 单条 entry 对应一次 session，不跨 session 合并
- 压缩后的结论进 `.aimodule/` 或 `.claude/agents/`，不回写 `memory/`
- 多人团队并行写入，日期 + agent + slug 命名保证唯一
