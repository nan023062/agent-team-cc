---
name: cbim-unity-context-providers
owner: architect
description: CBIM Context Providers：实现 Microsoft `AIContextProvider` 接口，将 CBIM 三大服务系统（Workspace 业务上下文 / Memory 检索结果 / Session 尾部事件）作为 Provider 注入到 Microsoft AIAgent 调用中。这是 CBIM 向 Microsoft Agent Framework 补补 CBIM 业务上下文的唯一插槽。
keywords: []
dependencies: []
status: spec
---
## Positioning

Kernel 下的**上下文桥**子系统——实现 Microsoft `AIContextProvider`，将 CBIM 三大服务系统的独有上下文（Workspace 模块 / Memory 检索结果 / Session 尾部事件）注入到 Microsoft AIAgent 调用中。

**这是 Microsoft Agent Framework 提供的正式扩展点**——不是 CBIM 发明的。CBIM 仅写三个 Provider 实现，不发明 Provider 抽象。

## Responsibility（一句话）

为 Workspace / Memory / Session 三大 CBIM 上下文各补一个 Microsoft `AIContextProvider` 实现；调用者（业务 Workflow / CbimTaskExecutor）按需装配。

## 三个同级 Provider

| Provider | 注入的上下文 | 数据源 |
|----------|-------------|---------|
| `WorkspaceContextProvider` | Task.Where 中模块的 `.dna/module.md` body 摘要 + 依赖边 + contract.md 接口 | `CBIM.Workspace.WorkspaceService` |
| `MemoryContextProvider` | `Memory.Query(Task.What, topK)` 返回的 MemoryEntry text 集 | `CBIM.Memory.MemoryService` |
| `SessionContextProvider` | Task.Who 的 Session 末 N 条事件 | `CBIM.AgentSystem.AgentSystemService` |

三者**同级、互不依赖**。装配顺序与优先级由调用者决定，Microsoft 负责合并与 token 预算。

## Public Contract

```csharp
namespace CBIM.Kernel.ContextProviders;

using Microsoft.Extensions.AI;
using CBIM.Kernel.TaskScheduler;

public interface IWorkspaceContextProvider { AIContextProvider For(CbimTask task); }
public interface IMemoryContextProvider    { AIContextProvider For(CbimTask task); }
public interface ISessionContextProvider   { AIContextProvider For(CbimTask task); }

/// <summary>装配门面：一调返回三个 Provider 列表。</summary>
public sealed class CbimContextProviderFactory
{
    public CbimContextProviderFactory(
        IWorkspaceContextProvider workspace,
        IMemoryContextProvider    memory,
        ISessionContextProvider   session);

    public IReadOnlyList<AIContextProvider> For(CbimTask task, CbimContextOptions? options = null);
}

public sealed record CbimContextOptions(
    bool IncludeWorkspace = true,
    bool IncludeMemory    = true,
    bool IncludeSession   = true,
    int  MemoryTopK       = 5,
    int  SessionTailN     = 20);
```

## Dependencies

- **Microsoft.Extensions.AI**——`AIContextProvider` / `AIContext`。
- `CBIM.Kernel.TaskScheduler`——`CbimTask`。
- `CBIM.Workspace`——读模块信息。
- `CBIM.Memory`——读记忆条目。
- `CBIM.AgentSystem`——读 Session 尾部。
- **不依赖 FlowGraph**——上下文与路由是两个独立维度。

## 铁律

1. **只实现 Microsoft `AIContextProvider`**——不发明 CBIM 自己的 Provider 抽象。
2. **三 Provider 同级、互不依赖**。
3. **Provider 是函数式的**——`For(task)` 是函数，不是状态机。
4. **不调 LLM**。Provider 只拼 prompt fragment，需要 LLM 总结表达为独立 Task。
5. **不担心 token 预算**——交给 Microsoft 默认合并策略。
6. **不持任何连接 / 缓存**——服务层自有缓存策略。

## Origin Context

架构重构前 CBIM 有 `Context POCO` 同时承载「节点间传状态」与「拼 prompt 输入」两职。本轮节点抽象已下沉到 Microsoft Workflows，「拼 prompt」一职唯一存活——迁入 Microsoft `AIContextProvider` 接口，由本模块提供三个 CBIM 独有实现。

## Implementation Order

1. `Api/` 三接口 + `CbimContextProviderFactory` + `CbimContextOptions`。
2. `Workspace/WorkspaceContextProvider.cs`。
3. `Memory/MemoryContextProvider.cs`。
4. `Session/SessionContextProvider.cs`。
5. 与 Microsoft Agent Framework 集成测试。

## Mirror in Python kernel

Python 侧无同名抽象——上下文拼装散落在 Claude Code SDK 与各 agent 的 system prompt 中。本模块是 Unity 侧独有。
