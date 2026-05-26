# kernel/memory — 对外契约

> 本契约定义记忆服务对外暴露的全部接口。**只有 4 个只读接口**；写入路径都不在本契约中——写入只能通过 `memory_write` MCP / CLI 两条入口走入 `crud/` 子模块。

**v2 重设计后的关键变化**：
- `tier="short"` 参数从所有接口上下架；`stats` 不再返回 `short` 分桶；`scan` / `query` / `get` 中 `tier` 过滤枚举由 `{short, medium, candidates}` 收窄为 `{medium, candidates}`。
- 写入入口从三条（Hook / `memory_write` MCP / CLI）变为两条（`memory_write` MCP / CLI）——Stop hook 不再写 short；hook 只作为 `kernel/retrieval` 的索引触发人，不走本模块。
- 新增一项隐含契约：**写入路径同步触发索引更新**。`memory_write` 返回后，该条目在下一次 `kernel/retrieval.search("memory_medium", ...)` 中可被检到；`delete` 返回后不再被检到。实现由 `crud/` 同步调 `retrieval.index_upsert` / `index_delete` 承担。

---

## 契约硬约束

| 约束 | 说明 |
|------|------|
| **只读** | 4 个接口都不修改任何状态。"查的同时记一下"是反模式。 |
| **不区分调用者** | 接口不接受、不感知 `agent_type` / `caller_role` 参数。同一查询条件，谁来查结果都一样。 |
| **不 emit 事件** | 查询不产生事件、不写日志、不通知任何方（模块内部观测除外）。 |
| **稳定优先** | 这 4 个接口的签名按公共契约级别管理：新增字段可向后兼容追加，删除/重命名需走 contract 变更流程。 |
| **不拥有 short 存储** | v2 后 `tier` 取值集锁定为 `{medium, candidates}`。传入 `"short"` 是接口不受控错误（受控：参数验证失败）。任何从 transcript 取数需绕到 transcript 路径进 `kernel/retrieval` 的 `transcript` 源。 |
| **stats 同级稳定** | `stats` 与 `query` / `scan` / `get` 同级稳定。audit / 健康度观测对它有长期依赖。 |
| **写入同步触发索引** | `memory_write` 返回前本模块必须完成对 `kernel/retrieval` 的同步调用。任何“写了但还没索引”的中间态是破窗。 |

---

## `query` — 语义/关键词检索

| 字段 | 内容 |
|------|------|
| 用途 | 语义/关键词检索，找最相关的若干条 |
| 输入 | 自然语言查询字符串 + 可选过滤（标签、时间窗、信号象限、`tier ∈ {medium, candidates}`） + 可选 `limit`。**不接受 `tier="short"`**。 |
| 输出 | 排序后的条目列表（按相关性降序） |
| 排序语义 | 按相关性；实现为调 `kernel/retrieval.search("memory_medium", query, top_k, filters)`，调用方不感知后端是 embedding 还是 BM25 |
| 失败语义 | 无命中返回空列表；传入 `tier="short"` 抛参数验证失败 |

---

## `scan` — 结构化过滤枚举

| 字段 | 内容 |
|------|------|
| 用途 | 枚举式拉取，不做相关性排序 |
| 输入 | 结构化过滤条件（标签集合、路径前缀、时间范围、信号象限、`promote_candidate` 标记、`tier ∈ {medium, candidates}`等） |
| 输出 | 全量符合条件的条目列表 |
| 排序语义 | 按时间戳降序（稳定，不随实现变化） |
| 典型用例 | "拉所有 `promote_candidate` 标记的条目"（知识循环自取入口）；"拉最近 30 天的所有 medium 条目"（治理循环扫描） |

---

## `get` — 精确取值

| 字段 | 内容 |
|------|------|
| 用途 | 已知坐标的精确取值 |
| 输入 | 条目 ID 或路径（仅限 `medium/` / `candidates/` 下） |
| 输出 | 单条完整内容 |
| 失败语义 | 不存在返回 `null`（或等价空值）；不招 |

---

## `stats` — 统计/观测

| 字段 | 内容 |
|------|------|
| 用途 | 健康度观测、容量决策、压缩触发判断 |
| 输入 | 可选过滤条件（标签、路径前缀、时间范围） |
| 输出（**结构稳定**） | 计数（按 `medium` / `candidates` 分桶，**不再含 `short`**）、分布（按标签 / 按信号象限）、最新时间戳、最早时间戳、各分桶磁盘占用上界 |
| 调用者依赖 | `audit` 模块的"记忆阈值"判断；`compaction/` 的健康巡检；任意循环的容量决策 |
| 稳定承诺 | 新增统计字段可追加；已存字段名称与含义不可变更。**`short` 分桶去除是一次 contract 变更**，走 schema_version 递增。 |

---

## 写入入口（不在对外契约内，仅作说明）

写入路径两条：`memory_write` MCP / CLI。两条都走入 `crud/` 子模块，**仅可写 `medium/`**（`candidates/` 由 `compaction/` 独占，对外不可直接写）。

`memory_write` 返回前同步完成：
1. 条目落盘到 `.cbim/memory/medium/<file>`；
2. 调 `compaction.identify(entry)` 识别是否为候选；
3. 调 `kernel/retrieval.index_upsert("memory_medium", doc_id, content, metadata)` 同步索引。

如任一步失败，整个 `memory_write` 返回错误；不允许“零步都足”之外的中间态。

---

## 不在契约内的部分

| 项 | 归属 |
|----|------|
| 写入路径具体实现 | 两条明确入口：`memory_write` MCP / CLI；进入 `crud/` 子模块；**不**对外暴露 |
| 压缩触发器 | `compact` 由 CLI / 定时 / 阈值独立触发；不是 API |
| 候选区数据结构 | 归 `compaction/` 子模块内部；外部只能通过 `scan(filter="promote_candidate")` 只读拉取 |
| 索引内部结构 | 归 `kernel/retrieval` 模块；外部不可见。**本模块不再拥有索引存储** |
| 健康巡检逻辑 | 归 `compaction/` 子模块；audit 只查 `stats` 自己判断阈值 |
| transcript 读取 / 删除 | 不在本模块。`engine/dream` 的记忆治理步负责读 transcripts（超 1 天）交主 agent 蒙骏、蒙骏后负责删原 transcripts |
| transcript 索引 | 不在本模块。`.claude/hooks/cbim_session_stop.py` 会话结束时同步调 `kernel/retrieval.index_upsert("transcript", ...)` |
