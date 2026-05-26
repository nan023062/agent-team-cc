# engine/retrieval — 对外契约

> 本契约定义检索原语库对外暴露的全部接口。**5 个接口**：3 个写入（`index_upsert` / `index_delete` / `verify_consistency`）+ 2 个读取（`search` / `stats`）。任何内部原语（embedding provider 选择、BM25 vs vector 路由、索引文件格式）都不在契约内。

---

## 契约硬约束

| 约束 | 说明 |
|------|------|
| **不主动扫文件** | 5 个接口都是同步调用；本模块不起后台线程、不订阅事件、不启 watcher。 |
| **不 emit 事件** | 写入、检索、校验都不产生事件、不写跨模块日志（模块内部观测除外）。 |
| **不区分调用者** | 接口不接受、不感知 `agent_type` / `caller_role`。同一查询条件谁来调结果都一样。 |
| **接口语义对源一视同仁** | 所有接口都带 `source: str` 参数；不为某个源开专门方法。新增源 = 调用方传新字符串，本契约不变。 |
| **同步语义** | `index_upsert` 返回后，则该 doc 在下一次 `search` 中可被检到。`index_delete` 返回后不再被检到。不需要 flush 调用。 |
| **`is_available()` 降级透明** | 调用方**不需要**手动判断 embedding 是否可用；`search` / `index_upsert` 内部会查，不可用时自动走 BM25。但接口返回的 `Hit.score` 含义随后端变（cosine vs BM25 归一化），调用方只能用于排序不能用于阀值。 |
| **接口集稳定** | 这 5 个接口签名按公共契约级别管理：新增字段可向后兼容追加，删除/重命名/语义变更需走 contract 变更流程。 |

---

## `source` 枚举

这是公共契约的一部分。现有枚举值：

| source | 对应数据源 | 写入责任人 |
|--------|----------|-----------|
| `"transcript"` | `~/.claude/projects/<project-slug>/*.jsonl`（CC 对话转录） | `.claude/hooks/cbim_session_stop.py` |
| `"memory_medium"` | `.cbim/memory/medium/*.md` | `memory.crud.write` / `update` / `delete` |
| `"dna"` | `**/.dna/{module.md, contract.md, workflows/*}` | `mcp_server.tools.dna.*`（`dna_edit` / `dna_init` / `dna_split` / `dna_deprecate` 等） |
| `"agents"` | `.claude/agents/**/*.md` | `mcp_server.tools.agents.*`（`agent_update` / `agent_init` / `agent_archive` 等） |

新增 `source` 枚举值需走 contract 变更流程（与新增接口同级）。

---

## `index_upsert` — 写入或更新一条索引

| 字段 | 内容 |
|------|------|
| 用途 | 把 `(source, doc_id, content, metadata)` 写入或更新到索引 |
| 输入 | `source: str`（枚举）、`doc_id: str`（在该 source 内唯一）、`content: str`（全文）、`metadata: dict`（任意可 JSON 序列化键值对，供 `search` filter 使用） |
| 输出 | `None`（成功）或抛 `RetrievalError`（缺参 / source 未知 / IO 失败） |
| 副作用 | 同步写索引文件 + 更新内存索引；同步调 embedding provider（如可用）；同步更新 BM25 词频表 |
| 幂等性 | 同 `(source, doc_id)` 重复调用为更新；不重复写入多条 |
| 稳定承诺 | 函数签名锁死；`metadata` 可任意扩展（后端透传）不需接口变更 |

---

## `index_delete` — 删除一条索引

| 字段 | 内容 |
|------|------|
| 用途 | 把 `(source, doc_id)` 从索引中移除 |
| 输入 | `source: str`、`doc_id: str` |
| 输出 | `None`（成功）或抛 `RetrievalError` |
| 幂等性 | 不存在该 doc_id 返回成功（不报） |
| 稳定承诺 | 同上 |

---

## `search` — 检索

| 字段 | 内容 |
|------|------|
| 用途 | 在指定 `source` 内查找与 `query` 最相关的 `top_k` 条 |
| 输入 | `source: str`、`query: str`（自然语言 / 关键词）、`top_k: int = 10`、`filters: dict \| None`（按 metadata 键值过滤，与入库时的 metadata 匹配） |
| 输出 | `list[Hit]`，按相关性降序；无命中返回空列表 |
| `Hit` 字段 | `{doc_id: str, source: str, score: float, content: str, metadata: dict}` |
| 后端语义 | embedding 可用时 cosine 相似度；不可用时 BM25；调用方不感知。可选启用混合检索（RRF）——但由本模块配置决定，不进接口 |
| 失败语义 | source 未知 → 抛；索引未初始化 → 返回空列表 |
| 稳定承诺 | `Hit` 字段名锁定；新增字段可向后兼容追加 |

---

## `verify_consistency` — 漂移校验

| 字段 | 内容 |
|------|------|
| 用途 | 检查索引与原始数据文件之间是否一致；发现漂移后**自动修复**（重跑 upsert / delete），返回报告 |
| 输入 | `source: str`、`mode: str ∈ {"fast", "full"}`（fast = mtime+size；full = sha256 hash） |
| 输出 | `DriftReport{source, mode, checked: int, drifted: list[doc_id], repaired: list[doc_id], failed: list[{doc_id, error}], duration_ms}` |
| 副作用 | 检查过程只读原始数据文件；修复过程会写索引文件（同 `index_upsert` / `index_delete`） |
| 使用场景 | `mode="fast"` 由 SessionStart hook 调用，必须 < 1 秒；`mode="full"` 由治理循环（`engine/dream` 的 MemRebuildIndex）调用，可能耗时几十秒 |
| 失败语义 | source 未知 → 抛；单个文件修复失败 → 进 `failed` 列表不中断 |
| 稳定承诺 | `DriftReport` 字段名锁定；`mode` 枚举锁定（新增走契约变更） |

---

## `stats` — 索引统计 / 观测

| 字段 | 内容 |
|------|------|
| 用途 | 返回索引健康度指标；供 dashboard / 治理循环判断是否需要重建 |
| 输入 | `source: str \| None`（None = 所有 source） |
| 输出（结构稳定） | `IndexStats{source, total_docs: int, vector_dim: int \| None, embedding_provider: str, fallback_active: bool, index_size_bytes: int, last_upsert_at: str, last_verify_at: str \| None, last_drift_count: int \| None}` |
| 调用者依赖 | dashboard 的"索引状态"面板；`audit` 的索引阈值判断；dream 循环 MemHealthScan |
| 稳定承诺 | 现有字段名与含义不变；新增字段可向后兼容追加 |

---

## `EmbeddingProvider` 配置

`EmbeddingProvider` 是内部抽象，不进接口契约。但其**选择机制**是公共契约的一部分：

- 配置文件 `.cbim/retrieval/config.json`（路径进契约），字段：
  - `provider: str ∈ {"openai", "local", "null"}`（默认 `"null"`：零配置安装走 BM25）
  - `openai_api_key_env: str`（环境变量名，默认 `"OPENAI_API_KEY"`）
  - `openai_model: str`（默认 `"text-embedding-3-small"`）
  - `local_model_path: str`（`provider="local"` 时必填）
  - `hybrid_search: bool`（默认 `false`；true 时 vector + BM25 走 RRF 融合）
- 运行时切换 provider 需重建索引（调 `verify_consistency(mode="full")` 会自动重建）。
- 接口集不随 provider 变更变化。

---

## 索引存储路径（公共契约）

```
.cbim/index/
  config.json                # provider 配置、hybrid 开关、schema_version
  <source>/                  # transcript / memory_medium / dna / agents
    meta.json                # {doc_id: {mtime, size, sha256, indexed_at}}
    vectors.bin              # 二进制 [N, dim]，provider 可用时存在
    bm25.json                # 倒排 + doc 长度
    docs/<doc_id>.txt        # 原文快照（供 BM25 重建与 search 返回 content）
```

- dashboard / debug 可只读消费这套布局（不走 MCP）。
- `schema_version` 递增 + 向后兼容读取。
- 不保证跨主机可携——`vectors.bin` 是 endian / dim 敏感的。跨主机迁移需重建。

---

## 不在契约内的部分

| 项 | 归属 |
|----|------|
| EmbeddingProvider 实现类 | 内部；通过 `config.json` 选择，不需调用方感知 |
| VectorIndex / BM25Index 算法细节 | 内部；可换实现但不改变接口 |
| RRF 融合参数 | 内部；k 值 / 权重不进接口 |
| BM25 分词策略 | 内部；中文 jieba / 英文 whitespace、停用词表都不进接口 |
| 索引二进制格式 | 内部；可升级但需 `schema_version` 调高 + 老文件可读 |
| 写入并发控制 | 内部；调用方不感知锁 |
| 索引入口触发逻辑 | 不在本模块；“写什么、何时写”完全在调用方（写入工具的同步副作用） |
| 调用方拼装 3 类 / N 类上下文 | 不在本模块；属于 `engine/execution` 的 retrieval 节点语义 |
