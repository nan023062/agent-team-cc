# kernel/engine/execution — 对外契约

> 本契约定义行为树引擎对外暴露的全部接口。**只有 3 个接口**：2 个驱动入口（`bt_tick` / `bt_tick_resume`）+ 1 个观测辅助（`bt_list_running_ticks`）。任何"派 agent / 写黑板 / 读节点内部"的路径都不在本契约——它们要么经协程式 yield/resume 回路、要么归子模块内部。

签名细节以 [`../README.md §6`](../README.md#6-l7-协程式-yieldresume-协议细节) 为准；本文档固化这些签名为公共契约级稳定承诺。

---

## 契约硬约束

| 约束 | 说明 |
|------|------|
| **不暴露黑板直接写** | 黑板字段写者由 design §2.1 表锁定；外部不能跨过 Action 直接写 bb。需要影响树行为只能通过 `user_request` / `context` 两个入参。 |
| **不返回可执行回调** | `BtResult.Yield` 只返回数据描述（`DispatchRequest`）；引擎不交出任何"主 agent 调一下就能跑 Action"的函数引用。控制权要么在引擎、要么在主 agent，无中间态。 |
| **接口集稳定** | 这 3 个接口签名按公共契约级别管理：新增字段可向后兼容追加，删除/重命名/语义变更需走 contract 变更流程。新增第 4 个接口同走变更流程。 |
| **Action 调子 agent 必须经 yield** | 引擎进程内**不**持有"直接调其他 agent 的客户端"。任何 Action 需要派子 agent → `BtResult.Yield(DispatchRequest)` → 主 agent Task tool → `bt_tick_resume` 回交结果。绕开 Task tool 直派是破窗。 |
| **黑板 JSON 快照路径是公开契约** | `.cbim/scheduler/bt/<tick_id>/{bb.json, trace.jsonl, resume.json}` 三个文件名、目录布局、`bb.json.schema_version` 字段**进入公共契约**——外部观测工具（dashboard / 调试 / 审计回放）依赖这套布局。Schema 升级走 `schema_version` 递增 + 向后兼容读取策略。 |

---

### v3.8 新增：ContextRetrieval 前置与三分类上下文

| 约束 | 说明 |
|------|------|
| **每次 tick 启动后、`ModeClassify` 前一定跑 `ContextRetrieval`** | 根节点 `RootSeq` 节点顺序为 `InitTick → ContextRetrieval → ModeClassify → ModeSwitch`。顺序锁死；Mode 干预需走 contract 变更流程。 |
| **`bb.retrieved_context` 是三分类结构的黑板字段** | 唯一写者：`ContextRetrieval` 叶。读者：`ModeClassify` 与五个分支子树。结构与语义进入公共契约：```
{
  "recent_memory": [Hit, …],   # transcript + memory_medium，按 RRF (Reciprocal Rank Fusion) 融合
  "agents":        [Hit, …],   # agents 源
  "module_knowledge": [Hit, …]  # dna 源
}
``` |
| **`recent_memory` 跨源融合走 RRF，禁止跨语料分数排序** | transcript 与 memory_medium 是两个独立语料库（N / avgdl / IDF 尺度不可比），原始 BM25 / cosine 分数跨语料排序无意义。`ContextRetrieval` 对两源各自按相关性降序排名后调 `engine/retrieval` 提供的 `rrf_fuse(ranked_lists, top_k, k=60)`（k 取 Cormack et al. 2009 默认值）融合，最终 `Hit.score` 字段填 RRF 融合分数（不再是原始检索分数）。调用方只能用于排序，不能用于阈值判断——这与 `engine/retrieval` 契约中 `Hit.score` 的现有语义一致。 |
| **源 → 类别映射是公共契约** | `transcript`+`memory_medium` → `recent_memory`（RRF 融合）；`agents` → `agents`；`dna` → `module_knowledge`。任何 prompt 渲染都可依赖这套分类。 |
| **`ContextRetrieval` 不 yield** | `kernel/retrieval` 是同步嵌入式接口；ContextRetrieval 不需调外部 agent。 |
| **失败不阻塞 tick** | retrieval 报错被 `@Catch` 吞掉；写 `bb.retrieved_context = {"recent_memory":[], "agents":[], "module_knowledge":[]}` 后继续。 |
| **`Hit` 结构跨模块复用** | `Hit = {doc_id, source, score, content, metadata}`——与 `kernel/retrieval` 契约中的 `Hit` 同步演进；本契约不复述字段语义。 |
