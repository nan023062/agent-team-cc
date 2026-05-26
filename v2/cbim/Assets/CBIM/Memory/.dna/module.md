---
name: cbim-unity-memory
owner: architect
description: Passive memory store: write / query / scan / get / stats. Depends only on Storage. Does NOT own any loop or timer — driven by Kernel's CRUD sub-loop.
keywords: []
dependencies: []
status: spec
---

## Positioning

**记忆系统是 CBIM 的服务层（M 维度）—— 不是一个具体的存储实现，而是一个可扩展的服务门面。**

对外：暴露统一的 CRUD 接口（write / get / query / scan / stats），允许外部世界注入记忆数据、访问记忆数据。所有调用方都只通过这一组接口看见记忆系统。

对内：可以抽象和扩展各种记忆库或算法——当前以「中期记忆扁平 JSON 条目」这一形态落地，未来可以增挂向量索引、关系图、分级缓存、远端同步等不同后端，全部隐藏在 `MemoryService` 门面之后。新增后端不破坏对外契约，老调用方零修改。

这套门面定位对应 CBIM 三大核心系统中的 **M（Memory）维度**。完整三系统切分见 v2 Unity 子树的根模块文档（`v2/cbim/Assets/CBIM/.dna/module.md` §「CBIM 三大核心系统」）。

C# 移植起步只覆盖**中期记忆这一层**的存储后端落地。**MemoryService 不是 actor**：不持有定时器、不跑循环、不开后台线程。CRUD 子循环与治理子循环都归 `Kernel/`，本模块只负责响应那些循环发出的调用。

对齐 `v1/kernel/memory/` 但做了坑缩：Python 那侧切了 `crud/` + `compaction/` + `jsonl_source/` 三个子目录；Unity 移植起步只发一个被动门面 + 单后端，compaction 与 jsonl_source 只在 Unity 侧真正出现需求时再以独立切片落地。

## Service-Layer Extension Model（服务层扩展模型）

记忆系统是服务层，不是存储实现。外部只看见门面，内部可以随需颠换后端。这是本模块最核心的架构约束。

```
        外部世界（Kernel 子循环 / Unity 场景 / 外部工具）
                              │
                              ▼
                  ┌────────────────────┐
                  │   MemoryService    │  ←─唯一公共门面（C1 开闭原则）
                  │   write / get /    │
                  │   query / scan /   │
                  │   stats            │
                  └───────┬────────────┘
                          │
          ┌───────────────┼─────────────────┐    ←─ 内部可插拔后端
          ▼               ▼                 ▼
  扁平 JSON 后端     向量检索后端       未来：远端同步 / 关系图 /
  （当前唯一实现）    （后续切片）          分级缓存 / 其他
```

**后端插拔原则**：

1. **后端只实现内部接口 `IMemoryBackend`**，不暴露给外部调用方。
2. **新增后端不允许拓宽公共门面。** 要补一个「按标签查」能力，先在 `Query` / `Scan` 参数上拓展，不开新方法。
3. **后端之间不允许互相依赖。** 多后端共存时，以装配顺序 / 路由策略决定谁响应。
4. **多后端路由由服务类本身决定**，不交给调用方。调用方从不需要知道「我现在查的是哪个后端」。
5. **迁移 / 重建 / 同步** 走独立的内部接口 `IMemoryMaintenance`，只被 Kernel 治理子循环持有——这是 C4（接口隔离原则）。

**存储实现路线图**（仅供设计参考，不是实现承诺）：

| 阶段 | 后端 | 场景 |
|------|------|------|
| 1（本切片） | 扁平 JSON | 单机 Unity、桌面原型 |
| 2 | + 关键词 / 向量检索 | 中型记忆量，需要语义查询 |
| 3 | + 远端同步（例如 SQLite / 云存储） | 多设备 / 多场景共享 |
| 4 | + 分级缓存 / 热冷分离 | 高负载，只在被证实需要后才动 |

**这与 Python 内核对齐**：那侧的 `v1/kernel/memory/_facade.py` 也是单一门面，未来如果需要加向量检索 / 远端同步，同样走「门面内部插拔后端」路子，不动公共门面。

## Three-Layer Memory Architecture（三层记忆体系 · 完整定义）

CBIM 把「记忆系统」的覆盖面划为三层。本模块当前只为中间一层提供存储后端；**以下表是三层记忆架构的唯一权威定义**，其他模块只能引用、不能重新解释：

| 层 | 名称 | 形态 | Unity 侧归属 | Python 侧对照 |
|----|------|------|--------------|--------------|
| 1 | **短期记忆** | 当前会话 context（LLM transcript / 对话缓冲） | **不归本模块**——Unity 场景的 LLM host 适配层持有；进程内对象，不落盘 | Claude Code 原生 `~/.claude/projects/<slug>/*.jsonl`，亦不归 `v1/kernel/memory/` 拥有 |
| 2 | **中期记忆** | session 压缩 / distill 后的持久条目（事实、决策、原则、过程） | **本模块** `MemoryService`，落到 `Application.persistentDataPath/.cbim/memory/medium/`（及 `candidates/`） | `v1/kernel/memory/`（medium + candidates） |
| 3a | **长期记忆 · 能力维度** | 组织架构图谱：agent 能力、角色、关系 | **不归本模块**——由 `AgentSystem/` 服务门面承担，当前只读侧由 `AgentRegistry/` 落地 | `v1/kernel/cbi/agents/` + `.claude/agents/*.md` |
| 3b | **长期记忆 · 业务维度** | 模块知识图谱：`.dna/` 模块树 + 模块间依赖 | **不归本模块**——由 `Workspace/` 服务门面承担，当前只读侧由 `Dna/` 落地 | `v1/kernel/cbi/_primitives/dna/` + 各模块 `.dna/`，由 `dna_*` MCP 工具读写 |

**三层之间的流动**：短期→中期走 distill（会话结束时提炼事实）；中期→长期走知识提升（architect / hr 在治理循环里把中期条目提炼进 `.dna/` 或 `.claude/agents/`）。这两条流动都是跨模块工作流，不在任一记忆模块内部完成。

**铁律**：本模块只读写 `medium/` 与 `candidates/` 两个目录下的扁平 JSON 条目（或未来内部扩展的等价后端）。不持有 agent 元数据、不持有模块依赖图、不暴露图查询接口。任何「能力图」或「模块图」的需求都要在 `Memory/` **之外**新开模块，不准把它们的 schema 塑进 `MemoryEntry`。

这套切分对齐 Python 内核：那侧 `v1/kernel/memory/` 同样只管 medium + candidates，能力与业务两张图各自有独立顶层。Unity 移植不要在这个边界上发明新形态。

## Responsibility（一句话）

对外暴露中期记忆的统一 CRUD 门面；对内可插拔后端实现；**不持有任何流控**。

## Contract Surface（规划）

暴露一个公共类 `MemoryService`，承载五个方法。全部同步——批量 / 节流是调用方的事。

| 方法 | 用途 |
|------|------|
| `void Write(MemoryEntry entry)` | 落盘一条；tier 从 entry 推断 |
| `MemoryEntry Get(string id)` | 按 id 查；不存在返回 null |
| `IReadOnlyList<MemoryEntry> Query(string text, int topK, string tierFilter)` | 自由文本检索；拓扑对齐 Python `memory_query` |
| `IReadOnlyList<MemoryEntry> Scan(MemoryScanFilter filter)` | 结构化过滤（source / tier / 日期区间） |
| `MemoryStats Stats()` | 计数、上次 distill 摘要、健康指标 |

维护接口（`Compact()` / `Sweep()` / `RebuildIndex()`）**独立**于公共 CRUD 表面，通过内部接口 `IMemoryMaintenance` 暴露——只有 Kernel 的治理子循环持有它。这是 C4（接口隔离原则）：CRUD 调用方不会**意外**触发维护操作。

后端契约（内部）：`IMemoryBackend` —— `Write` / `Get` / `Scan` / `Query` / `Stats` 五对应方法 + 路由提示（例如 `Supports(MemoryScanFilter)`）。后端互不感知，互不依赖；多后端编排由 `MemoryService` 装配根决定。

## Storage Layout（规划）

第一阶段「扁平 JSON 后端」落到 `Application.persistentDataPath/.cbim/memory/` 之下：

```
memory/
  short/      ← 手记条目（用户手写的笔记）
  medium/     ← distill 后的条目
  candidates/ ← compaction 工作区（后续切片）
  index.json  ← 索引
```

与 Python `v1/kernel/memory/` 的布局对齐——这样未来跨运行时的工具能同时读两边。单条记忆的 schema 由 `MemoryEntry` 定义（数据类，字段 `id` / `tier` / `source` / `created_at` / `text` / `tags`）。

后续后端（向量索引 / 远端同步 / 分级缓存）有各自的落地路径，由各自的后端实现决定；公共门面对此无感。

## Dependencies

- `CBIM.Storage`——用于原子写、JSON 序列化、路径解析。
- **此外什么都不依赖。** Memory 不准引用 Kernel、不准引用 AgentRegistry、不准引用 Dna、不准引用 AgentSystem / Workspace——asmdef 层面强约束。

## 铁律

- Service 对象没有 `Update()`、没有 `StartCoroutine`、不开 `Task.Run` 做后台。每个公共方法**同步返回**。调用方要异步——调用方自己包，不是本模块的事。
- **公共门面是 `MemoryService`，是唯一的对外面**。任何后端实现细节不得泄露为公共类型。
- **新增后端走「门面内部插拔」**，不允许通过"另开一个 Service"绕过门面。

## Mirror in Python kernel

Python 对应物是 `v1/kernel/memory/_facade.py`。C# 移植保持同样的五方法公共表面——`design/WORKFLOW-MEMORY.zh-CN.md` 这份设计稿对两边逐条适用。差异：Unity 侧暂无 jsonl_source 子后端（Claude Code 的 session JSONL 在 Unity 上下文中根本不存在）；也暂无 compaction。

## 不干的事（Non-Goals）

- **不持有短期记忆。** 会话 context 是 LLM host 适配层的事；MemoryService 不提供「追加一轮对话」这类接口。
- **不持有能力图谱（长期记忆 / 能力维度）。** agent 能力、角色、关系由 `AgentSystem/` 门面承担，当前读侧由 `AgentRegistry/` 落地。本模块不接受 `entry.kind == "agent"` 这类隐式多态使用。
- **不持有业务图谱（长期记忆 / 业务维度）。** `.dna/` 模块树与依赖图由 `Workspace/` 门面承担，当前读侧由 `Dna/` 落地。本模块不读写 `.dna/` 下任何文件。
- **不是检索引擎。** 向量检索 / BM25 是后端实现细节，何时上线由路线图决定；公共门面无感。

