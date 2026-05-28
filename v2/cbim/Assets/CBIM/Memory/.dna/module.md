---
name: cbim-unity-memory
owner: architect
description: CBIM 记忆服务（基建层 · 三层模型）。本轮重定位：从“全局记忆服务”抽象为“IMemoryService 接口 + FileMemoryBackend 默认实现”。IMemoryService 作为基建层类型约定；Agent 实例 per-Agent 持一个 IMemoryService 实例（默认 FileMemoryBackend，可接 Pinecone / Weaviate / VectorStore 等第三方实现）。MemoryEntry 扭平 JSON CRUD + Query 几个接口位于 IMemoryService 上；默认实现依赖 Storage。不再作为“横切关注点”出现，而是明确的基建接口 + Agent 所有实例。
keywords: []
dependencies: []
status: spec
---
## Positioning

**Memory 是 CBIM 基建层四件套之一**——与 `Tools/` / `Skills/` / `Mcp/` 平级，同为顶层模块、同为「类型契约 / 抽象接口」。

**本轮重定位（v2 三层模型）：从「全局记忆服务」抽象为「IMemoryService 接口 + 默认实现」**——

| 旧 | 新 |
|----|----|
| `MemoryService` 是横切关注点 / 全局服务 | `IMemoryService` 是基建层接口，**每个 Agent 持一个实例** |
| 后端固定为本地扁平 JSON | 默认实现 `FileMemoryBackend`（本地 JSON）；可替换为 Pinecone / Weaviate / Chroma / Microsoft VectorStore 等 |
| 跨 Agent 共享一份 Memory | per-Agent 实例化——「这个人的记忆」与「另一个人的记忆」物理隔离 |
| Memory 作为「跨能力跨业务」的横切层 | Memory 是「Agent 的内部资源」——Agent 装配时绑定，task 期使用 |

## 在三层架构中的位置

```
基建层（Infrastructure Primitives）：
  Tools/   ToolDescriptor 接口
  Skills/  SkillDescriptor 接口
  Mcp/     McpDescriptor 接口
  Memory/  ← 这里：IMemoryService 接口 + MemoryEntry 类型 + FileMemoryBackend 默认实现
  Storage/ FileBackend（IO 原语）

Agent 层：
  AgentSystem  持 IMemoryService 实例（per-Agent）

Workspace 层：
  Workspace  不持 Memory——模块只有规章/流程/接入点，没有「模块的记忆」
```

**与其他基建抽象的差别**：Tool/Skill/MCP 是「能力描述」（什么能用），Memory 是「资源服务」（数据存哪、怎么查）。前者是 LLM 看到的能力清单；后者是 LLM 的「记忆器官」。两者在基建层平级，但运行期角色不同。

## 为什么 Memory per-Agent 实例化

**认知模型对齐**：人有自己的记忆是常识。之前 Memory 作为「全局服务」是工程便利，但破坏了「Agent = 一个虚拟人」的认知模型——两个人不应该看到同一份记忆。

**接入第三方记忆库的开口**：

| 后端 | 适用场景 |
|------|---------|
| `FileMemoryBackend`（默认） | 单机 Unity 项目；记忆量 < 万级；零运维 |
| Pinecone / Weaviate / Chroma 实现 | 云端协作场景；多 Agent 共享某些记忆；语义检索强需求 |
| Microsoft VectorStore 实现 | 接入 Microsoft 生态向量检索；与 ChatHistoryProvider 联动 |
| In-Memory 实现（测试） | 单元测试不写盘；速度优先 |

**关键设计选择**：「per-Agent 实例化」并不阻碍「共享记忆」——只要多个 Agent 持的 IMemoryService 实例指向同一后端（如同一个 Pinecone index），它们就共享同一份数据。**实例隔离 ≠ 数据隔离**——前者是接口契约约定，后者是后端实现策略。

**默认行为（FileMemoryBackend）**：默认实现下每个 Agent 持自己的 FileMemoryBackend 实例，数据落到各自子目录（按 AgentInstance.Id 隔离）；若用户希望 Agent 间共享，配置时让多个 Agent 持指向同一目录的 FileMemoryBackend 即可。

## CBIM 核心对偶中的位置（重述）

| 维度 | 服务层 | 关注边界 | 与 Memory 的关系 |
|------|--------|----------|------------------|
| 能力（Agent 层） | AgentSystem / ExternalAdapter | 谁能动 | 持 IMemoryService 实例 |
| 业务（Workspace 层） | Workspace | 在哪里动、能动什么 | **不持**——模块没有记忆 |
| 基建（基建层） | **Memory（本模块）** | 提供 IMemoryService 接口 + 默认实现 | 自身是被持有方 |

之前的「Memory 不参与对偶」说法本轮**精确化为**：Memory 接口是基建（被各方派生使用）；Memory 实例归 Agent 层持有（per-Agent）；Workspace 层不持 Memory。

## Three-Layer Memory（重画 · 本轮）

| 层 | 形态 | 归属（v2 三层模型后） |
|----|------|---------------------|
| 短期 | thread 历史 / chat transcript | **Microsoft AgentThread + ChatHistoryProvider**（CBIM 不再 host） |
| 中期 | distill 后的 MemoryEntry | **本模块 IMemoryService 接口** + Agent 持实例 |
| 长期 · 能力 · 类型/实例 | AgentDescription + AgentInstance | `AgentSystem/`（Agent 层） |
| 长期 · 能力 · 运行轨迹 | Session 事件流 | `AgentSystem/`（Agent 层） |
| 长期 · 业务 | ModuleDescription + Module 实例 | `Workspace/`（Workspace 层） |

> 中期记忆的归属由「跨 Agent 全局服务」改为「per-Agent IMemoryService 实例」——这是本轮唯一变化。

## 责任（一句话）

定义 `IMemoryService` 基建接口 + `MemoryEntry` 类型 + 默认 `FileMemoryBackend` 实现；Agent 装配时绑定一个 IMemoryService 实例；调用方按接口编程、不感知后端选型。

## Contract Surface

### 基建接口（公共契约）

```csharp
namespace CBIM.Memory;

/// <summary>
/// CBIM 中期记忆基建接口。Agent 实例持有一个 IMemoryService 实例。
/// 默认实现 = FileMemoryBackend；第三方后端（Pinecone / Weaviate / VectorStore 等）
/// 通过实现本接口接入，无需改 Agent 层代码。
/// </summary>
public interface IMemoryService : IAsyncDisposable
{
    void Write(MemoryEntry entry);
    MemoryEntry? Get(string id);
    IReadOnlyList<MemoryEntry> Query(string text, int topK);    // 关键词或向量检索（由实现决定）
    IReadOnlyList<MemoryEntry> Scan(MemoryScanFilter filter);
    MemoryStats Stats();
}

public sealed record MemoryEntry(
    string Id,
    string Source,           // "distill" / "manual" / ...
    DateTime CreatedAt,
    string Text,
    IReadOnlyList<string> Tags);

public sealed record MemoryScanFilter(
    string? Source = null,
    IReadOnlyList<string>? Tags = null,
    DateTime? Since = null,
    DateTime? Until = null);

public sealed record MemoryStats(
    int EntryCount,
    DateTime? OldestCreatedAt,
    DateTime? NewestCreatedAt);
```

### 默认实现（FileMemoryBackend）

```csharp
namespace CBIM.Memory;

using CBIM.Storage;

/// <summary>
/// IMemoryService 的默认实现：基于 FileBackend 的扁平 JSON 存储。
/// 单实例对应一个 root 目录；多实例可共享同一目录（Agent 间共享记忆）或各自独立目录。
/// </summary>
public sealed class FileMemoryBackend : IMemoryService
{
    public FileMemoryBackend(FileBackend storage, string subDir = "memory");

    // 实现 IMemoryService 全部接口
    public void Write(MemoryEntry entry);
    public MemoryEntry? Get(string id);
    public IReadOnlyList<MemoryEntry> Query(string text, int topK);  // 关键词检索
    public IReadOnlyList<MemoryEntry> Scan(MemoryScanFilter filter);
    public MemoryStats Stats();
    public ValueTask DisposeAsync();  // 默认实现无需特殊清理；为接口对称保留
}
```

### 接口设计原则

1. **同步方法**——异步调用方自己包；接口本身不强加异步开销（默认实现是本地 IO，纯同步）。`IAsyncDisposable` 仅为允许第三方实现（如 Pinecone client）异步关闭。
2. **`Query` 语义由实现决定**——`FileMemoryBackend` 实现为关键词匹配；Pinecone / VectorStore 实现为向量相似度检索。接口契约只承诺「返回 topK 相关条目」，不规定算法。
3. **`MemoryEntry` 是不可变 record**——构造时校验，之后只读。所有实现都按这个不可变假设设计（不需要锁）。
4. **`MemoryScanFilter` 是组合过滤器**——所有可空字段；实现按支持程度过滤（不支持的字段忽略）。
5. **`Stats` 是只读快照**——实现可缓存（避免每次扫全表）。

### 被砍掉的接口（保留沿用上一轮裁决）

- 多 tier / short tier（短期归 Microsoft AgentThread）
- 维护接口（`Compact` / `Sweep` / `RebuildIndex`）—— Microsoft Compaction 策略接管
- 多后端插拔模型（保留「未来可挂 Microsoft VectorStore」一行路径，但本轮不抽象 `IMemoryBackend` 接口）

## 装配模型（Agent 层调用）

```
// AgentSystem.OpenInstance 装配 Agent 时：
var memory = options.MemoryFactory?.Invoke(workspaceRoot)
             ?? new FileMemoryBackend(storage, $"memory/{agentInstanceId}");
agent.MemoryService = memory;

// task 期 Agent 调用：
agent.MemoryService.Write(...);
var recall = agent.MemoryService.Query("关于 CDN 上传失败的过往经验", topK: 5);

// CloseInstance 时：
await agent.MemoryService.DisposeAsync();
```

`MemoryFactory` 是 `Func<string workspaceRoot, IMemoryService>`——调用方可注入自定义实现：

```csharp
// 默认：FileMemoryBackend
var agent = agentSystem.OpenInstance("unity-programmer", new OpenInstanceOptions {
    TaskWhere = "/path/to/workspace",
    // MemoryFactory 不传 → 用默认 FileMemoryBackend
});

// 自定义：接 Pinecone
var agent = agentSystem.OpenInstance("research-scholar", new OpenInstanceOptions {
    TaskWhere = "/path/to/workspace",
    MemoryFactory = root => new PineconeMemoryBackend(apiKey, indexName: "cbim-shared"),
});
```

## Storage Layout（默认实现）

```
<storageRoot>/.cbim/memory/<agentInstanceId>/
  <entryId>.json   ← MemoryEntry 一文件
  index.json       ← entry id → 摘要的快速索引
```

若多个 Agent 共享同一 storageRoot 子目录，则共享记忆（用户配置时主动让 MemoryFactory 返回指向同一目录的 backend 实例）。

## Dependencies

- **基建接口部分（`IMemoryService` / `MemoryEntry`）**：无外部依赖——纯 POCO + 接口。
- **默认实现（`FileMemoryBackend`）**：依赖 `CBIM.Storage` 的 `FileBackend`。
- **不依赖** Kernel / AgentSystem / Workspace——基建层不引用任何上层。
- **第三方实现**：自行依赖各 SDK（Pinecone client / Weaviate client / Microsoft.Extensions.VectorData 等）；不影响本模块抽象层。

依赖方向：`AgentSystem → IMemoryService → ⊥`；`FileMemoryBackend → IMemoryService + FileBackend → ⊥`。无反向。

## 铁律

- **接口稳定优于完整**——`IMemoryService` 暴露最小必要五方法（Write / Get / Query / Scan / Stats + DisposeAsync）；扩展时优先在「接口实现内部」而非「接口本身」加方法。
- **Agent 持 IMemoryService 实例**——不再有「全局 MemoryService 单例」；Memory 实例与 Agent 实例同生命周期。
- **Workspace 不持 Memory**——模块没有「自己的记忆」；模块只有规章 / 流程 / 接入点。
- **默认实现 = FileMemoryBackend**——基于 Storage 的本地扁平 JSON；零运维、零依赖。
- **第三方实现通过派生 IMemoryService 接入**——不修改本模块接口；接入 Pinecone / VectorStore / 任意后端都不动 Agent 层代码。
- **不持短期记忆**——AgentThread / ChatHistoryProvider 是 Microsoft 职责。
- **不写 Compaction**——Microsoft 接管。
- **不写向量检索本身**——若需要，通过实现新 IMemoryService 直接挂 `Microsoft.Extensions.VectorData` 的 IVectorStore。
- **不持能力 / 业务图谱**——是 AgentSystem / Workspace 的事。
- **接口同步方法 + Dispose 异步**——Memory 内部不为异步操心；IAsyncDisposable 仅为第三方实现的关闭语义留位。
- **MemoryFactory 注入点唯一**——调用方在 `OpenInstanceOptions.MemoryFactory` 提供工厂；其他位置不准 new IMemoryService 实例。

## Origin Context

- **第一轮**：Memory 设计为「服务门面 + 可插拔后端」全功能架构，预留多 tier、维护接口、IMemoryBackend 抽象。
- **第二轮（上轮）**：裁决退化为「MemoryEntry 的扁平 JSON CRUD」+ 一份将来挂 VectorStore 的连接点——所有通用能力交给 Microsoft。
- **第三轮（本轮 · v2 三层模型）**：把上一轮的「具体 MemoryService 类」**抽出 IMemoryService 接口** + 保留 `FileMemoryBackend` 作为默认实现；Memory 从「全局横切服务」改为「per-Agent 实例」。
  - **驱动力**：
    1. v2 三层模型把 Memory 明确归入「基建层」，基建层应以接口为主、实现为辅。
    2. 用户明确希望「接入 Pinecone / 第三方记忆库」——必须先有接口才能换实现。
    3. 「Agent = 一个人」的认知模型要求每个人有自己的记忆，而不是全员共用一份。
- **本轮代码层面（下切片实施）**：
  1. 拆 `MemoryService.cs` → `IMemoryService.cs`（接口）+ `FileMemoryBackend.cs`（默认实现）。
  2. `AgentDescription` 增 `MemoryConfig` 字段（或 `MemoryFactory` 工厂方法）。
  3. `OpenInstanceOptions` 增 `MemoryFactory: Func<string, IMemoryService>?` 字段。
  4. `AgentInstance` 增 `MemoryService: IMemoryService` 字段；`CloseInstance` 调 `DisposeAsync`。

## Emergent Insights

1. **基建层接口的「最小完整」是稳定性的来源**——IMemoryService 只暴露五个方法，让任何后端都能实现。一旦放宽（如加 `BulkImport` / `Reindex` / `Migrate`），所有派生实现都被迫升级——基建抽象就不再稳定。这是 C6 在接口设计上的具象。
2. **per-Agent 实例化不等于数据隔离**——实例归属是接口契约；数据隔离是后端实现策略。配置「多 Agent 持指向同一 backend 的实例」即可共享数据，「持各自独立目录的实例」即数据隔离。这是「契约 vs 策略」的典型分离。
3. **Memory 接口的最大跨能力**——同一个 `IMemoryService` 接口，可以是「本地 JSON」、「云端向量库」、「In-Memory 测试桩」三种完全不同的存储与查询机制，但 LLM 看到的体验完全一致（Write / Query 两个方法）。这是基建抽象的最高境界——隔离实现复杂度，统一调用方式。
4. **Memory 从「横切」到「per-Agent」是认知模型修正**——「跨能力跨业务」的横切关注点是工程视角；「Agent 持自己的记忆」是认知视角。CBIM 选择认知视角是因为整个系统的 mental model 是「复合 Agent = 一个人」——人不会和别人共用记忆。
5. **接口 + 默认实现是基建层标准范式**——Tool 有 ToolDescriptor 抽象 + Standard 实现；Mcp 有 McpDescriptor 抽象 + 装配胶水实现；Memory 现在也有 IMemoryService 抽象 + FileMemoryBackend 实现。基建层四件套都遵循「抽象稳定 + 一份默认实现 + 第三方可派生」模式。

## Non-Goals

- 不实现 Compaction / Sweep / RebuildIndex（Microsoft 接管）。
- 不实现向量检索本身——通过派生 IMemoryService 接 VectorStore / Pinecone 等。
- 不抽象 `IMemoryBackend`（接口已经是 `IMemoryService` 本身——再叠一层 backend 抽象是过度设计）。
- 不持有 agent / module 图谱。
- 不为第三方后端预写实现——业务方自行派生 IMemoryService 接入；本模块不假设具体后端形态。
- 不暴露 token 预算 / 上下文窗口管理——这些是 Microsoft AIContextProvider 的事，不是 IMemoryService 的事。
