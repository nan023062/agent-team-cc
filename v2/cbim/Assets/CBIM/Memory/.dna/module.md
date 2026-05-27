---
name: cbim-unity-memory
owner: architect
description: CBIM 记忆服务层（M 维度）。本轮大幅瘦身：Microsoft 已有 ChatHistoryProvider + Compaction + VectorData 整套生态。CBIM Memory 仅保留 AIContextProvider 的可装配后端实现（平文件 JSON 条目存储 + Query/Write CRUD 薄门面），用于被 CBIM 自己的 MemoryContextProvider 读。依赖仅 Storage。
keywords: []
dependencies: []
status: spec
---

## Positioning

**Memory 是 CBIM 的服务层（M 维度）——本轮大幅瘦身后退化为「业务胶水」：CBIM 独有的中期记忆条目（distill 后的事实 / 决策 / 原则）的扁平 JSON 存储与查询，被 `MemoryContextProvider` 读取后注入 Microsoft AIAgent。**

## CBIM 核心对偶中的位置

Memory 是 CBIM 三大服务系统中**唯一不参与「能力 / 业务对偶」**的一个——它是**跨能力、跨业务、跨会话**的事实沉淀层：

| 维度 | 服务层 | 关注边界 |
|------|--------|----------|
| 能力（C） | AgentSystem | 谁能动 |
| 业务（B） | Workspace | 在哪里动、能动什么 |
| **记忆（M）** | **Memory** | **跨上述两者的事实 / 决策 / 原则** |

**为什么 Memory 不走 MCP 动态注入模型**：

- 动态注入模型（工具 / MCP 端点）按 Task 期装配——绑定 Module、仅本次 RunAsync 生效。这种模型对「工具」适用，因为工具的「能不能调」按业务边界划分。
- 但记忆是**跨业务跨能力**的——一段事实在 Module A 里被 distill 出来，在 Module B 的会话里仍可能相关。如果按 Task 期装配，记忆就被切割成多个不连通的子集，违反记忆的本质。
- 因此 Memory 走 **ContextProvider 主动按需读** 模式：`MemoryContextProvider` 实现 Microsoft `AIContextProvider`，在每次 LLM 调用前根据当前 query 主动检索 `Memory.Query(text, topK)`，把相关条目拼进上下文。
- 这套模式由 Microsoft 抽象统一管理（token budget / 检索时机），CBIM Memory 服务层只暴露纯被动 CRUD + Query 门面，**完全无 Task / Module / Agent 感知**——这是它能成为「跨维度记忆」的前提。

## 本轮重要变动：不再造记忆轮子

Microsoft 已提供以下能力，CBIM **不再重造**：

| 已下沉到 Microsoft | 由哪个抽象 |
|---|---|
| 会话 transcript / thread 历史 | `Microsoft.Agents.AI.AgentThread` 与 `ChatHistoryProvider` |
| 会话压缩 / summarization | Microsoft Compaction 策略 |
| 向量检索 / 语义查询 | `Microsoft.Extensions.VectorData` + 各 VectorStore 实现 |
| token-budget 合并 | `AIContextProvider` 内建 |

CBIM Memory **只保留**：
1. **中期记忆条目存储**——distill 后的 `MemoryEntry`（事实 / 决策 / 原则 / 过程），扁平 JSON 落到 `persistentDataPath/.cbim/memory/medium/`。这是 CBIM 独有的「跨会话浓缩事实」语义，Microsoft 不感知。
2. **极薄 CRUD 门面**——Write / Get / Query / Scan / Stats 五方法，供 `MemoryContextProvider`（在 Kernel/ContextProviders/）读、以及治理子循环的 distill 作业写。
3. **可选未来后端**——向量检索时直接 host Microsoft `IVectorStore`，不自写。

## Three-Layer Memory（重画）

| 层 | 形态 | 归属（本轮重画后） |
|----|------|------------------|
| 短期 | thread 历史 / chat transcript | **Microsoft AgentThread + ChatHistoryProvider**（CBIM 不再 host） |
| 中期 | distill 后的 MemoryEntry | **本模块**（扁平 JSON）|
| 长期 · 能力 · 类型/实例 | AgentDescription + AgentInstance | `AgentSystem/` |
| 长期 · 能力 · 运行轨迹 | Session 事件流 | `AgentSystem/` 内置 |
| 长期 · 业务 | ModuleDescription + Module 实例 | `Workspace/` |

> **变动**：上轮短期记忆「不归 CBIM」的说法本轮**显式化为「归 Microsoft」**——AgentThread + ChatHistoryProvider 是 Microsoft 标准抽象，CBIM 不需要为短期记忆操心。

## Responsibility（一句话）

提供中期记忆条目的统一 CRUD + Query 门面；条目以扁平 JSON 落盘；供 `MemoryContextProvider` 读、distill 作业写。**不再扩展为通用记忆系统**。

## Contract Surface

```csharp
namespace CBIM.Memory;

public sealed class MemoryService
{
    void Write(MemoryEntry entry);
    MemoryEntry? Get(string id);
    IReadOnlyList<MemoryEntry> Query(string text, int topK);    // 关键词检索；未来可挂 Microsoft VectorStore
    IReadOnlyList<MemoryEntry> Scan(MemoryScanFilter filter);
    MemoryStats Stats();
}

public sealed record MemoryEntry(
    string Id,
    string Source,           // "distill" / "manual" / ...
    DateTime CreatedAt,
    string Text,
    IReadOnlyList<string> Tags);
```

**砍掉的接口**：
- 多 tier / short tier（短期归 Microsoft AgentThread）
- 维护接口（`Compact` / `Sweep` / `RebuildIndex`）—— Microsoft Compaction 策略接管
- 多后端插拔模型（保留「未来可挂 Microsoft VectorStore」一行路径，但本轮不抽象 `IMemoryBackend` 接口）

## Storage Layout

```
Application.persistentDataPath/.cbim/memory/
  medium/<id>.json    ← MemoryEntry 一文件
  index.json          ← id → 文件路径 + 摘要
```

无 `short/` / `candidates/` 目录——前者归 Microsoft，后者属未来 distill 作业话题。

## Dependencies

- `CBIM.Storage`——原子写、JSON。
- **不依赖** Kernel / AgentSystem / Workspace——服务层互不依赖。

## 铁律

- **不持短期记忆**——AgentThread / ChatHistoryProvider 是 Microsoft 职责。
- **不写 Compaction**——Microsoft 接管。
- **不写向量检索**——未来需要直接挂 `Microsoft.Extensions.VectorData` 的 IVectorStore 实现，不自抽象。
- **不持能力 / 业务图谱**——是 AgentSystem / Workspace 的事。
- **同步方法**——异步调用方自己包。

## Origin Context

上一轮 Memory 设计为「服务门面 + 可插拔后端」全功能架构，预留多 tier、维护接口、IMemoryBackend 抽象。本轮裁决：CBIM 在记忆层无业务独有价值（除「跨会话浓缩的 MemoryEntry 这一种东西」），所有通用能力交给 Microsoft。门面退化为「MemoryEntry 的 CRUD」+ 一份将来挂 VectorStore 的连接点。

## Non-Goals

- 不实现 Compaction / Sweep / RebuildIndex。
- 不实现向量检索本身——未来挂 Microsoft VectorStore。
- 不抽象 IMemoryBackend——本模块就是「直接 Storage 后端」，未来若需多后端走「门面装 IVectorStore」即可。
- 不持有 agent / module 图谱。

