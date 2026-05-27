---
name: cbim-unity-channel
owner: architect
description: Channel 系统（入口层）。本轮大幅瘦身：Microsoft 已有 AgentSession（能装业务交互 transcript）。CBIM Channel 是 Microsoft AgentSession 的薄封装——绑一个 AIAgent、提供 SendAsync / OnOutput IO 流、将每轮输入包为 CbimTask 递交 Microsoft Workflows 或直调 AIAgent.RunAsync。不拿 Memory / Workspace / Storage。
keywords: []
dependencies: []
status: spec
---
## Positioning

**Channel 是 CBIM 的入口层**——一个 Channel = 用户打开的一个交互界面实例，绑定一个 Microsoft `AIAgent`，承载 IO 流。

**本轮重要变动：Channel 退化为 Microsoft `AgentSession` 的薄封装。**

## 本轮变动

Microsoft.Agents.AI 已提供 `AgentSession` 抽象——其本就是「一个用户与一个 Agent 的持续交互 transcript」的标准容器。CBIM Channel 不再自抽象一份「交互界面」，而是：

- **底层 host 一个 Microsoft `AgentSession`**——持有 transcript / thread / 多轮上下文。
- **薄封装为 CBIM Channel**——暴露 `SendAsync(userMessage)` / `OnOutput` 两个 CBIM 调用约定面，便于 Unity 场景层订阅。
- **内部把每轮用户输入包为 CbimTask 后调用**：
  - 单 Task 简单场景：`task.Who.RunAsync(...)` + `agentSystem.AppendSessionEvent(...)`。
  - 多 Task 业务流程：取已装配的 Microsoft Workflow，调 `WorkflowHost.RunAsync(workflow, input)`。

## 核心概念

| 概念 | 定义 | 来源 |
|------|------|------|
| **Channel** | 用户交互窗口实例，1:1 绑定一个 AIAgent | CBIM 薄封装 |
| **AgentSession**（底层） | Microsoft 的交互 transcript 容器 | `Microsoft.Agents.AI.AgentSession` |
| **AIAgent** | 该窗口运行的「进程」 | `Microsoft.Agents.AI.AIAgent` |
| **CbimTask** | 单轮交互被包成的三元组 | `CBIM.Kernel.TaskScheduler.CbimTask` |
| **Session（CBIM 工作日志）** | CbimTaskExecutor 写到 AgentSystem 的事件流 | 与 transcript 不同 schema |

> Channel 的 transcript（Microsoft AgentSession）与 Agent 的工作日志（AgentSystem 的 Session）是两套不同记录：前者是「用户看见的对话」，后者是「Agent 内部的执行轨迹」。

## Contract Surface

```csharp
namespace CBIM.Channel;

using Microsoft.Agents.AI;

public sealed class ChannelService
{
    Channel OpenChannel(string agentDescriptionName, ChannelOptions options);
    Channel? GetChannel(string channelId);
    IReadOnlyList<Channel> ListChannels();
    void CloseChannel(string channelId);
}

public sealed class Channel
{
    string ChannelId { get; }
    AIAgent Agent { get; }
    AgentSession Session { get; }    // ← Microsoft 的，底层 transcript

    // 每轮用户输入 → 包 CbimTask → 调 Workflow 或 RunAsync
    Task<ChannelOutcome> SendAsync(string userMessage, CancellationToken ct = default);

    event Action<ChannelOutputEvent> OnOutput;
}

public sealed record ChannelOutcome(string ResultText, bool IsError, string? ErrorMessage);
```

## Dependencies

- **`Microsoft.Agents.AI`**——`AIAgent` / `AgentSession`。
- **`CBIM.AgentSystem`**——`OpenInstance` 拿 `AIAgent`、`AppendSessionEvent` 写工作日志。
- **`CBIM.Kernel.TaskScheduler`**——包 `CbimTask`。
- **`CBIM.Kernel.FlowGraph`**（可选）——多 Task 业务流程时拿 Microsoft Workflow + `CbimTaskExecutor`。
- **不直接依赖** Memory / Workspace / Storage——上下文走 ContextProviders（在 Workflow / Executor 内部装配）。

## 铁律

- **不直接访问** Memory / Workspace / Storage。
- **不直接调** `IChatClient`——拿 AIAgent 后调 `RunAsync`（或交给 Workflow）。
- **不写 Session 日志**——CbimTaskExecutor / 直调路径自己写。
- **不在 Channel 里加业务路由**——业务路由是 Workflow 职责。
- **薄封装铁律**：Channel 自定义 API 只够「OpenChannel / SendAsync / OnOutput / CloseChannel」四件事，其余功能直接暴露底层 `AgentSession` 给高阶调用者。

## Origin Context

上一轮 Channel 已从 BT 驱动者改为 Task 递交者，但仍自定义全套抽象。本轮发现 Microsoft `AgentSession` 本就是「一个用户与一个 Agent 的交互容器」，CBIM 再造一个独立 Channel 类是重复抽象。裁决：**退化为 AgentSession 薄封装**，仅保留 CBIM 调用约定面（OpenChannel / SendAsync 等）方便 Unity 场景层订阅。

## Implementation Sequence

1. `Channel` 数据类——内部 host `Microsoft.Agents.AI.AgentSession`。
2. `ChannelService.OpenChannel`——调 AgentSystem.OpenInstance 拿 AIAgent，构造 AgentSession，包成 Channel。
3. `Channel.SendAsync`——包 CbimTask（who = Agent, where = options.WorkspaceModules, what = userMessage），单 Task 走 `Agent.RunAsync(session, userMessage)` 并 AppendSessionEvent；多 Task 取注册的 Workflow 调 `WorkflowHost.RunAsync`。
4. `OnOutput`——订阅 AIAgent 输出事件转发。
5. 与 AgenticOS 集成。

## Non-Goals

- 不持久化 Channel——纯进程内对象。
- 不实现 Channel 之间协作——多 Agent 协作走 Workflow。
- 不感知 Microsoft Compaction / ContextProvider 装配——是 OpenInstance / Workflow 职责。
