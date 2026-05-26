---
name: cbim-unity-memory
owner: architect
description: Passive memory store: write / query / scan / get / stats. Depends only on Storage. Does NOT own any loop or timer — driven by Kernel's CRUD sub-loop.
keywords: []
dependencies: []
status: spec
---

## Positioning

C# 移植的被动记忆存储。**不是 actor**——不持有定时器、不跑循环、不开后台线程。CRUD 子循环与治理子循环都归 `Kernel/`，本模块只负责响应那些循环发出的调用。

对齐 `v1/kernel/memory/` 但做了坍缩：Python 那侧切了 `crud/` + `compaction/` + `jsonl_source/` 三个子目录；Unity 移植起步只发一个被动存储，compaction 与 jsonl_source 只在 Unity 侧真正出现需求时再以独立切片落地。

## Responsibility（一句话）

基于 Storage 在磁盘上存取记忆条目，**不持有任何流控**。

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

## Storage Layout（规划）

落到 `Application.persistentDataPath/.cbim/memory/` 之下：

```
memory/
  short/      ← 手记条目（用户手写的笔记）
  medium/     ← distill 后的条目
  candidates/ ← compaction 工作区（后续切片）
  index.json  ← 索引
```

与 Python `v1/kernel/memory/` 的布局对齐——这样未来跨运行时的工具能同时读两边。单条记忆的 schema 由 `MemoryEntry` 定义（数据类，字段 `id` / `tier` / `source` / `created_at` / `text` / `tags`）。

## Dependencies

- `CBIM.Storage`——用于原子写、JSON 序列化、路径解析。
- **此外什么都不依赖。** Memory 不准引用 Kernel——asmdef 层面强约束。

## 铁律

Service 对象没有 `Update()`、没有 `StartCoroutine`、不开 `Task.Run` 做后台。每个公共方法**同步返回**。调用方要异步——调用方自己包，不是本模块的事。

## Mirror in Python kernel

Python 对应物是 `v1/kernel/memory/_facade.py`。C# 移植保持同样的五方法公共表面——`design/WORKFLOW-MEMORY.zh-CN.md` 这份设计稿对两边逐条适用。差异：暂无 jsonl_source 子模块（Claude Code 的 session JSONL 在 Unity 上下文中根本不存在）；也暂无 compaction。
