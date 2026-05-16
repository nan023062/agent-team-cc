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

---

## Entry 格式

**文件命名**：`YYYY-MM-DD-<agent-id>-<slug>.md`

```markdown
---
date: YYYY-MM-DD
agent: <agent-id>
tags: [module-combat, decision, refactor, blocked]
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

所有 entry 统一存入 ChromaDB（同时存原文 + 向量），无本地文件双写。

| 阶段 | 存储 | 切换方式 |
|------|------|---------|
| 本地测试 | `./chroma_db`（单文件夹） | 不设环境变量 |
| 团队服务器 | ChromaDB HTTP Server | 设置 `CHROMA_HOST` |

**写入命令：**

```bash
python3 tools/chroma_write.py \
    --agent <agent-id> \
    --slug <简短描述> \
    --content "<session 内容>" \
    --modules <模块名，空格分隔> \
    --tags <标记，空格分隔>
```

**查询命令（返回原文，无需二次加载）：**

```bash
# 按 agent 查询（HR 用）
python3 tools/chroma_query.py --agent programmer --query "架构决策" --top-k 10

# 按模块查询（架构师用）
python3 tools/chroma_query.py --module combat --query "踩坑 incident" --top-k 5
```

**启动本地服务器（团队共享时）：**

```bash
chroma run --path ./chroma_db --port 8000
```

---

## 写入方

任意 agent 在任务结束后自行写入，或由秘书代写。  
内容不限：可以是模块改动、设计决策、踩坑经验、阻塞记录——只要是这次 session 里值得记录的事实。

---

## 压缩升格

**HR** 定期读取全部 entries，过滤 `agent=<id>`，提炼反复出现的能力模式：
→ agent skill 升格 / soul 更新

**架构师** 定期读取全部 entries，过滤 `tags` 含 `module-<name>`，提炼模块相关决策与约束：
→ `.aimodule/` 知识三件套 / workflows 更新

两条管线共用同一份原始记录，从不同维度提炼。

---

## 铁律

- `memory/entries/` 只写原始记录，不写已压缩的结论
- 单条 entry 对应一次 session，不跨 session 合并
- 压缩后的结论进 `.aimodule/` 或 `.claude/agents/`，不回写 `memory/`
- 多人团队并行写入，日期 + agent + slug 命名保证唯一
