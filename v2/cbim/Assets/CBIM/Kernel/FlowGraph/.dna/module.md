---
name: cbim-unity-flowgraph
owner: architect
description: FlowGraph 子系统：Task 序列 + 路由规则（while/if 跑节点）。本身不调 LLM、不拿 Agent、不拿 Context——仅根据上个 Task 的结果决定下一个跑哪个 Task。具体执行调 TaskRunner。
keywords: []
dependencies: []
status: spec
---

## Positioning

Kernel 下的**业务工作流子系统**——以 **Microsoft.Agents.AI.Workflows** 为底层执行引擎，CBIM 仅写「业务拓扑装配」与「CbimTask 步骤适配器」两块极薄胶水。

**本轮重要变动**：不再自建 `IFlowGraph` / `FlowState` / `TaskOutcome` POCO。Microsoft.Agents.AI.Workflows 已提供完整的 `Workflow` / `Executor` / `Edge` / 条件路由 / 暂停-恢复 / 检查点能力，CBIM 重造毫无价值。

## Responsibility（一句话）

把 CBIM 的业务流程拓扑（ChatFlow / DispatchFlow / ArchExecFlow 等）表达为 Microsoft Workflows，并提供「以 CbimTask 为节点」的小型适配 Executor 让业务拓扑能引用 CBIM 的三元组词汇。

## 被砍的东西

| 原 CBIM 自建 | 取代方（Microsoft.Agents.AI.Workflows） |
|---|---|
| `IFlowGraph` / `FlowState` | `Workflow` / `WorkflowContext` |
| `TaskOutcome`（POCO） | `Executor` 返回值 / `WorkflowRunResult` |
| `Next(state, outcome)` 路由方法 | `Edge` + 条件路由（`AddEdge(from, to, condition)`） |
| 自写循环驱动 | `WorkflowHost.RunAsync` |
| Yield / Resume 状态机 | Microsoft Workflows 内建 checkpoint / suspend / resume |

CBIM **只保留**：
1. **CbimTaskExecutor**——一个泛 `Executor`，把入参 `CbimTask` 转一次 `AIAgent.RunAsync`，输出 result。
2. **业务 Workflow 装配类**（ChatFlow / DispatchFlow 等）——纯静态拓扑装配代码。

## Public Contract

```csharp
namespace CBIM.Kernel.FlowGraph;

using System.Threading;
using System.Threading.Tasks;
using Microsoft.Agents.AI;
using Microsoft.Agents.AI.Workflows;
using CBIM.AgentSystem;          // Agent, IAgentSystemSessionWriter
using CBIM.Kernel.TaskScheduler;  // CbimTask

/// <summary>
/// 把一条 CbimTask 转一次 AIAgent.RunAsync 的 Executor。
///
/// 关键签名约束（Microsoft.Agents.AI.Workflows 真实接口，不可改）：
///   - 返回类型必须是 <see cref="AgentResponse"/>（而非 AgentRunResponse——后者不存在）。
///   - HandleAsync 必须是 public abstract 的 override（基类签名 public abstract），
///     带 CancellationToken cancellationToken = default 第三参数。
///   - 构造函数必须把 string id 透传给基类 Executor&lt;TInput, TOutput&gt;(string id, ...)。
/// </summary>
public sealed class CbimTaskExecutor : Executor<CbimTask, AgentResponse>
{
    public CbimTaskExecutor(
        string id,
        IAgentSystemSessionWriter sessionWriter);

    public override ValueTask<AgentResponse> HandleAsync(
        CbimTask task,
        IWorkflowContext context,
        CancellationToken cancellationToken = default);
}

/// <summary>业务 Workflow 装配类示范（具体业务 Workflow 各自一文件）。</summary>
public static class ChatWorkflow
{
    public static Workflow Build(
        Agent classifyAgent,
        Agent respondAgent,
        IAgentSystemSessionWriter sessionWriter);
}
```

**关键点**：

- `CbimTaskExecutor` 内部调 `task.Who.AIAgent.RunAsync(...)`、调 `sessionWriter.AppendSessionEvent(task.Who.InstanceId, ev)`——这就是 CBIM 与 Microsoft 的唯一接点。
- `task.Who` 类型是 `CBIM.AgentSystem.Agent`（CBIM 运行时壳），其中包含 `AIAgent`（执行体）+ `InstanceId`（CBIM 自生成 GUID，作为 Session 文件名）+ `Session`（Microsoft AgentSession）。
- 原 TaskRunner 的「拼参 + 调 RunAsync + 写 Session」三步全部在这个 Executor 的 `HandleAsync` 中完成，不再需要独立的 TaskRunner 模块。

### Executor 构造参数说明

- `string id`：Workflow 拓扑中本 Executor 的唯一标识（基类强制要求）；由业务 Workflow 装配类决定（例：`"classify"` / `"respond"`）。
- `IAgentSystemSessionWriter sessionWriter`：Session 写侧接口，仅 AgentSystem 实现。

### instanceId 写 Session 的来源（铁律）

Executor 内部 `AppendSessionEvent(instanceId, ev)` 的 `instanceId` 参数**永远来自 `task.Who.InstanceId`**——即 `CBIM.AgentSystem.Agent.InstanceId`（CBIM 自生成 GUID）。

不可使用：

| 不可用的标识 | 不可用原因 |
|------|------|
| `task.Who.AIAgent.Id` | Microsoft AIAgent 的 GUID，每次 AsAIAgent 重新生成，无法反查 Agent 实例；Session 文件命名按 `<InstanceId>.jsonl` 走 CBIM 自生成 GUID。 |
| `task.TaskId` | Task 是一次性事件；Session 是 agent 实例的累计事件流，二者粒度不同。 |
| 任何字符串拼装 | Session 文件路径在 AgentSystem 内已硬编码为 `<InstanceId>.jsonl`，必须与之一致。 |

### Task 期 MCP / 工具透传

CbimTaskExecutor **不介入工具 / MCP 装配本身**。工具装配的数据源 = `task.Who.Description`（AgentDescription，能力维度），不是 `task.Where`（模块路径列表，业务维度）。

**装配发生在哪里**：AgentSystem.OpenInstanceAsync 装配 Agent 时，读 `AgentDescription.SystemTools` + `AgentDescription.McpList` + `AgentDescription.Skills` → 按 per-agent 沙盒注入 AIFunction。装配完成的 `Agent`（已含 AIAgent + Session + McpHandles）被作为 `task.Who` 传入 CbimTaskExecutor。

**Executor 的透传职责**：

- CbimTaskExecutor 拿到 `CbimTask` 后直接调 `task.Who.AIAgent.RunAsync(...)`——`task.Who.AIAgent` 本身已是装配完成、工具已挂的 `AIAgent`。Executor **不负责重新装配**。
- 若某些场景 Executor 需要「在 Task 期内造补充 agent 实例」，可调 `AgentSystem.OpenInstanceAsync(descriptionId, activatedByTaskId)`——传入「desc id + 触发 task id」，**不传 module 列表**。
- `task.Where` 仅供 ContextProviders 读作业务上下文素材（`WorkspaceContextProvider` 读该模列表的 ModuleDescription 并拼进提示词），不参与工具装配。

**与上一轮的差别**：

| 项 | 上一轮（错） | 本轮（正） |
|---|---|---|
| Executor 透传什么 | `task.Where` → `OpenInstanceOptions.ActiveModulePaths` | 什么也不透传——`task.Who.AIAgent` 本身自带工具 |
| 装配数据源 | ModuleDescription.standard_tools | AgentDescription.SystemTools / Skills / McpList |
| 装配发起点 | Task 期动态（按 module 拼装） | OpenInstanceAsync 期静态（按 agent 装配一次） |
| 动态性体现 | 同一 agent 跨 module 工具不同 | 同一 task 选不同 agent 则工具不同，间接动态 |

**为什么这是正确的**：

- 「谁能调工具」是 agent 的能力描述，定义在 AgentDescription；Executor 拿到 `task.Who` 时能力已函盖在其内部 AIAgent 中。
- 「装配唯一胶水点 = OpenInstanceAsync」铁律不动，但其输入是 agent 自身声明而非 task.Where。
- Executor 职责收窄为「调一下 RunAsync + 写 Session」两件事，更加纯净。

## Dependencies

- **`Microsoft.Agents.AI.Workflows`**——核心运行时（Workflow / Executor / Edge / WorkflowHost）。
- **`Microsoft.Agents.AI`**——`AIAgent` / `AgentResponse`（返回类型，**不是 AgentRunResponse**）。
- **`CBIM.Kernel.TaskScheduler`**——`CbimTask` 数据类（其 `Who` 字段现为 `CBIM.AgentSystem.Agent`）。
- **`CBIM.Kernel.ContextProviders`**——装配 AIContextProvider 注入 RunAsync。
- **`CBIM.AgentSystem`**：
  - 消费实体类 `Agent`（从 `task.Who` 拿运行时壳：AIAgent + InstanceId + Session）。
  - 走接口 `IAgentSystemSessionWriter` 写 Session（避免反向耦合，接口归属 AgentSystem。C3 铁律：稳定方持接口定义权）。
- **不依赖 Memory / Workspace 直接访问**——走 ContextProviders 中转。

## 铁律

1. **不自建 Workflow 引擎**。任何「再加一层 IFlowGraph 抽象」的提案直接拒绝——Microsoft Workflows 已是公共抽象、长期演进。
2. **业务拓扑是装配代码、不是配置数据**。ChatWorkflow.Build 是纯 C# 静态方法——不引入 YAML/JSON 拓扑 DSL。
3. **CbimTaskExecutor 是唯一 Microsoft 接点**。所有 `AIAgent.RunAsync` 调用集中在此；Session 写入也在此。任何「绕过 Executor 自己调 RunAsync」是架构破坏。
4. **不在 Executor 里加业务逻辑**。Executor 只做「拼 ContextProvider + 调 RunAsync + 写 Session」三件事；业务路由表达为 Edge 条件。
5. **暂停-恢复用 Microsoft 检查点**。CBIM 不自写 yield/resume。
6. **接口归属遵 C3**：`IAgentSystemSessionWriter` 接口定义在 AgentSystem 模块，FlowGraph 依赖接口、AgentSystem 自身实现——稳定方持有接口定义权。

## Origin Context

上一轮 FlowGraph 设计为 `IFlowGraph` + `FlowState` + `Next` 自写路由 POCO，CBIM 自己驱动循环。本轮发现 Microsoft.Agents.AI.Workflows（NuGet 包，已装）正是这件事的完整公共抽象——`Workflow` / `Executor` / `Edge` / `WorkflowHost` / checkpoint / suspend / resume 全部内建。继续自写等于跟 Microsoft 上游平行演进，注定落后且无业务价值。

裁决：本轮**全部下沉**。CBIM 仅保留两块极薄胶水：CbimTaskExecutor（CBIM 三元组 → Microsoft Executor 适配器）+ 业务 Workflow 装配类（ChatWorkflow 等）。

## Implementation Order

1. `Api/CbimTaskExecutor.cs`——单文件，约 50 行。
2. `Workflows/ChatWorkflow.cs`——首个业务示范，验证端到端。
3. 后续切片：`Workflows/DispatchWorkflow.cs` / `Workflows/ArchExecWorkflow.cs`。
4. （可选）`Registry/WorkflowRegistry.cs`——名字 → Workflow Build 工厂，Channel 拿名字取拓扑。

## Mirror in Python kernel

Python 侧 `v1/kernel/engine/execution/tree/main_loop.py` 是 BT 拓扑——那边未来若引入 Microsoft Workflows 同形态包是 Python architect 话题。两边仅保「同样的业务拓扑与提示词语义」对齐。

