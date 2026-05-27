---
name: cbim-unity-task-scheduler
owner: architect
description: Task 数据类的定义家（路径保留、语义重定义）。Task = 不可变三元组：who（AIAgent 实例）+ where（Workspace 模块路径列表）+ what（Requirement），加上必要的路由信息（FlowGraphId / 父任务 ID）。本轮砍掉 Dispatch / TaskManager / IPipelineProvider / IDispatchHost——执行职责迁移到 TaskRunner。
keywords: []
dependencies: []
status: spec
---

## Positioning

Kernel 下的 **Task 不可变数据类定义家**。一份 POCO，三元组：who（AIAgent）+ where（Workspace 模块路径列表）+ what（Requirement）。

> **路径保留、语义重定义**。本模块不再含任何调度 / 派发 / 状态机逻辑——只是数据类。

## CBIM 三系统协同中的位置

`CbimTask` 是 CBIM 三大服务系统（AgentSystem / Workspace / Memory）**唯一的协同数据结构**——三系统本身互不依赖，只能通过 Task 的三元组在调用侧会合：

| Task 字段 | 出自 | 指向 | 面向的服务系统 |
|----------|------|------|---------------|
| `Who` (AIAgent) | AgentSystem.OpenInstance 装配 | 能力个体 | **AgentSystem（C）** |
| `Where` (Module 路径列表) | Workspace 模块树 | 业务工作区 | **Workspace（B）** |
| `What` (Requirement) | 调用侧 / 上一级 Task | 本次要做的事 | —（是任务本身） |

`Memory` 不出现在 Task 字段中——它是跨维度背景服务，由 `MemoryContextProvider` 在 RunAsync 期间主动按需读。

## Task 作为 MCP / 工具动态注入源

上一轮设计把 `Where` 字段同时作为「在哪里动」的业务语义声明 + 「MCP / 工具装配数据源」——**本轮修正后只保留前者**。

**本轮修正**：

- `Where`（module 路径列表）仅作为业务语义：「这件任务是在哪些业务块上发生」。供 ContextProviders（`WorkspaceContextProvider`）读取 ModuleDescription 并拼提示词。
- **不再是**工具 / MCP 装配数据源——该职责迁回 `Who` 字段（其背后的 AgentDescription）。
- Task 仍是三大服务系统协同的唯一词汇，但「拿什么工具」与 `Where` 解耦——该信息随 Who 一起进场（`task.Who` 本身已是装配完、工具已挂的 AIAgent）。

**修正后的字段语义**：

| 字段 | 语义 | 服务维度 | 是否参与工具装配 |
|------|------|---------|------------------|
| `Who` (AIAgent) | 能力个体（已装配工具的运行体）| C（AgentSystem） | 是——装配时读 AgentDescription.tools |
| `Where` (Module 路径列表) | 业务工作区 | B（Workspace） | 否——仅业务语义 |
| `What` (Requirement) | 本次要做的事 | — | 否 |

**为什么这是正确的**：工具能力是 agent 业务属性（为什么这个 agent 能调 git？因为它是个编程 agent），不是 module 业务属性（同一 module 被不同 agent 处理时工具需求不同）。`Where` 只负责「业务上下文」，`Who` 负责「能力上下文」——二者本来就是两个独立维度。

## Responsibility（一句话）

定义 `CbimTask` 不可变数据类，以 who / where / what + 可选路由信息表达 CBIM 中一件任务。

## Public Contract

```csharp
namespace CBIM.Kernel.TaskScheduler;

using Microsoft.Agents.AI;

public sealed record CbimTask(
    string TaskId,
    Microsoft.Agents.AI.AIAgent Who,
    IReadOnlyList<string> Where,
    string What,
    string? ParentTaskId = null,
    string? OriginChannel = null,
    IReadOnlyDictionary<string, object>? Params = null,
    DateTime CreatedAt = default)
{
    public static CbimTask Create(
        AIAgent who,
        IEnumerable<string> where,
        string what,
        string? parentTaskId = null,
        string? originChannel = null,
        IDictionary<string, object>? @params = null);
}
```

## Dependencies

- **Microsoft.Agents.AI**——仅引用 `AIAgent` 类型，不调任何方法。
- **无 CBIM 同级依赖**——这让 CbimTask 作为「最稳定底层」成立。
- **不依赖 Unity**——纯 C# POCO。

## 铁律

1. **`CbimTask` 是不可变 record**。需要调整则创建新 CbimTask（记 `ParentTaskId`）。
2. **本模块无行为**。不含派发 / 调度 / 状态转迁。
3. **`Who` 是 Microsoft `AIAgent`**——不接受字符串 agentInstanceId。
4. **不重新引入状态机**。Pending / Running / Done 是 `AIAgent.RunAsync` 的返回值职责。
5. **不提供 TaskRegistry / TaskHistory**。历史查询走 AgentSystem 的 Session。
6. **类名前缀 Cbim**——避免与 `System.Threading.Tasks.Task` 同名冲突。

## Origin Context

上轮本模块承载「Task 定义 + 派发 + Resume + 状态机」多职。本轮裁决：派发 / Resume 全部下沉 Microsoft `AIAgent.RunAsync`；本模块仅留数据类定义——是 FlowGraph 与所有调用者交换的共同词汇。

## Implementation Order

1. `Api/CbimTask.cs`——不可变 record + 静态构造。
2. 不再有更多文件。如未来 Task 需补元数据字段，在 record 上加属性即可。

## Mirror in Python kernel

Python 侧未抽象「Task」；该词汇仅 Unity 侧需要——因为 Unity 侧多 Agent / 多 Channel 并发，必须有一份显式的「调度词条」。

