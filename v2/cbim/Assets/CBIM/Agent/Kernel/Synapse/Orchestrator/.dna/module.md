---
name: cbim-unity-agent-kernel-synapse-orchestrator
owner: architect
description: CBIMOrchestrator——FlowGraph（NeuralCircuit）执行引擎。基于 Microsoft.Agents.AI.Workflows.WorkflowBuilder/Workflow 包一层，把 CBIM 的 NeuralCircuit IR 翻译为 MAF Workflow 后 RunStreaming；硬性按图执行（节点失败 / 分支 / 并行 / WaitUser 全由确定性边驱动），LLM 只在 CallBrain / CallTool 节点内发挥智能。是 Synapse 子模块之三（与 Compiler 平级）。</description>
keywords: []
dependencies: []
status: spec
---

## Positioning

- **CBIMOrchestrator 是 FlowGraph 的「后端」**——拿 Compiler 产出的 `NeuralCircuit` IR，硬性按图执行。
- **核心决策：包一层 MAF `WorkflowBuilder` / `Workflow`，不重造**。遵用户明文要求。
- 平级 Compiler：Synapse 三 leaf 之一。LLM 只在 CallBrain / CallTool 节点内部发挥智能，节点间走确定性边。
- CBIM 负责：**IR → MAF Workflow** 翻译器 + CBIM 业务节点包（`BrainCallExecutor` / `BranchExecutor` / `ReturnExecutor`）+ 进度事件转译。

## 架构图

```mermaid
flowchart LR
    classDef cbim  fill:#fff3e0,stroke:#e65100,stroke-width:2px,color:#000;
    classDef cmp   fill:#e8f5e9,stroke:#1b5e20,color:#000;
    classDef brain fill:#f3e5f5,stroke:#4a148c,color:#000;
    classDef maf   fill:#bbdefb,stroke:#0d47a1,color:#000;

    IR["NeuralCircuit IR\n(来自 Compiler)"]

    subgraph ORC ["Orchestrator/ (本模块)"]
        FAC["CBIMOrchestrator\n.RunAsync(circuit, palette, callback, ct)"]
        C2W["CircuitToWorkflowCompiler\n(IR→MAF Workflow)"]
        BCE["BrainCallExecutor"]
        BRE["BranchExecutor"]
        RTE["ReturnExecutor"]
        MSG["CircuitMessage\n(节点间 envelope)"]
    end

    MAF["Microsoft.Agents.AI.Workflows\nWorkflowBuilder / Workflow /\nInProcessExecution.RunStreaming"]
    BB["BrainBase\n(调用目标)"]
    PFC["PrefrontalCortex\n(主脑 · 调用者)"]
    CB["IPrefrontalCallback\n(上报路由→Channel.OnOutput)"]

    PFC --> FAC
    IR --> FAC
    FAC --> C2W
    C2W --> BCE
    C2W --> BRE
    C2W --> RTE
    C2W --> MAF
    BCE -- InvokeAsync --> BB
    BCE -. ReportProgress .-> CB
    RTE -- YieldOutput --> FAC
    FAC -- BrainOutcome --> PFC

    class IR cmp;
    class FAC,C2W,BCE,BRE,RTE,MSG cbim;
    class MAF maf;
    class PFC,BB brain;
    class CB cbim;
```

## 类图

```mermaid
classDiagram
    class CBIMOrchestrator {
        +RunAsync(circuit, palette, callback, ct) Task~BrainOutcome~
        +CompileToMafWorkflow(circuit, palette) Workflow
    }

    class CircuitToWorkflowCompiler {
        <<static internal>>
        +Compile(circuit, palette, callback)$ Workflow
    }

    class CircuitMessage {
        +string CircuitId
        +string FromNodeId
        +string? BranchLabel
        +string LastSummary
        +IReadOnlyDictionary~string,BrainOutcome~ History
    }

    class BrainCallExecutor {
        <<Executor~CircuitMessage~>>
    }
    class BranchExecutor {
        <<Executor~CircuitMessage~>>
    }
    class ReturnExecutor {
        <<Executor~CircuitMessage,string~>>
    }

    class Workflow {
        <<MAF>>
    }
    class BrainBase {
        <<in Brain>>
        +InvokeAsync(invocation, ct)
    }
    class IPrefrontalCallback {
        <<in Synapse>>
        +ReportProgress(brainId, message)
    }
    class NeuralCircuit {
        <<in Compiler>>
    }

    CBIMOrchestrator ..> CircuitToWorkflowCompiler : uses
    CircuitToWorkflowCompiler ..> Workflow : builds
    CircuitToWorkflowCompiler ..> BrainCallExecutor : binds
    CircuitToWorkflowCompiler ..> BranchExecutor : binds
    CircuitToWorkflowCompiler ..> ReturnExecutor : binds
    BrainCallExecutor ..> BrainBase : invokes
    BrainCallExecutor ..> IPrefrontalCallback : reports
    CBIMOrchestrator ..> NeuralCircuit : reads
    BrainCallExecutor --> CircuitMessage
    BranchExecutor --> CircuitMessage
    ReturnExecutor --> CircuitMessage
```

## RunAsync 序流

```mermaid
sequenceDiagram
    participant PFC as PrefrontalCortex
    participant ORC as CBIMOrchestrator
    participant C2W as CircuitToWorkflowCompiler
    participant MAF as MAF Workflow
    participant EXEC as Executor (BrainCall/Branch/Return)
    participant BB as BrainBase
    participant CB as IPrefrontalCallback

    PFC->>ORC: RunAsync(circuit, palette, callback, ct)
    ORC->>C2W: Compile(circuit, palette, callback)
    C2W-->>ORC: Workflow
    ORC->>MAF: InProcessExecution.RunStreamingAsync(workflow)
    loop 逐节点
        MAF->>EXEC: ExecuteAsync(CircuitMessage)
        alt BrainCallExecutor
            EXEC->>BB: InvokeAsync(invocation, ct)
            BB-->>EXEC: BrainOutcome
            EXEC->>CB: ReportProgress("@orchestrator", "node {id} done")
            EXEC->>MAF: SendMessageAsync(next CircuitMessage)
        else BranchExecutor
            EXEC->>EXEC: eval(ConditionExpression)
            EXEC->>MAF: SendMessageAsync(msg with BranchLabel)
        else ReturnExecutor
            EXEC->>MAF: YieldOutputAsync(summary)
            EXEC->>MAF: RequestHaltAsync()
        end
    end
    MAF-->>ORC: WorkflowOutputEvent / ErrorEvent
    ORC-->>PFC: BrainOutcome (Summary / IsError)
```

## IR → MAF 节点映射

| CBIM IR 节点 | MAF Executor | 备注 |
|---------------|--------------|------|
| `CallBrainNode` | `BrainCallExecutor : Executor<CircuitMessage>` | 构造期扣 BrainBase + IPrefrontalCallback |
| `BranchNode` | `BranchExecutor : Executor<CircuitMessage>` | eval ConditionExpression 后 SendMessage 携 BranchLabel |
| `ReturnNode` | `ReturnExecutor : Executor<CircuitMessage, string>` | 渲染 SummaryTemplate + YieldOutput + RequestHalt |
| `CircuitEdge` | `AddEdge(from, to, condition: msg => msg.BranchLabel == edge.BranchLabel)` | BranchLabel 为 null 走无条件 AddEdge |

**CircuitMessage** 是节点间 envelope：`{ CircuitId, FromNodeId, BranchLabel?, LastSummary, History: Dict<nodeId, BrainOutcome> }`。`History` 是路经现场记账，Branch 表达式可引 `previous.summary contains "x"` / `node_n03.summary contains "x"`（v1 仅 contains/equals）。

## Contract Surface

```csharp
namespace CBIM.AgentSystem.Kernel.Synapse.Orchestrator;

using Microsoft.Agents.AI.Workflows;
using CBIM.AgentSystem.Brain;
using CBIM.AgentSystem.Kernel.Synapse;             // IPrefrontalCallback
using CBIM.AgentSystem.Kernel.Synapse.Compiler;    // NeuralCircuit

public sealed class CBIMOrchestrator
{
    public Task<BrainOutcome> RunAsync(
        NeuralCircuit circuit,
        IReadOnlyList<BrainBase> brainPalette,
        IPrefrontalCallback callback,
        CancellationToken ct);

    public Workflow CompileToMafWorkflow(
        NeuralCircuit circuit,
        IReadOnlyList<BrainBase> brainPalette);
}

public sealed class CircuitMessage
{
    public string CircuitId { get; }
    public string FromNodeId { get; }
    public string? BranchLabel { get; }
    public string LastSummary { get; }
    public IReadOnlyDictionary<string, BrainOutcome> History { get; }
}
```

## 失败 / 重试 / 图回滚

v1 走最简路径：

- 单节点失败（`BrainBase.InvokeAsync` 招异常 / IsError=true）→ BrainCallExecutor 调 `AddEventAsync(ExecutorFailedEvent)` + `RequestHaltAsync()`
- RunAsync 看到 WorkflowErrorEvent → 返 `BrainOutcome(IsError=true)`
- **不做自动重试 / 节点级重试 / fallback 路由**——交主脑下一轮重编译解决（fail-fast 上翻 → 主脑 LLM 重规划，表达性更强）
- **图状态不落盘重启**——v1 单进程；需恢复走 MAF `CheckpointManager`（默认不启）

## 进度回报

MAF `WorkflowEvent` 转译：

- `ExecutorInvokedEvent` → `callback.ReportProgress("@orchestrator", "running node {id}")`
- `ExecutorCompletedEvent` → `callback.ReportProgress("@orchestrator", "node {id} done")`
- `WorkflowOutputEvent` → 收集为 finalSummary
- `WorkflowErrorEvent` → 记 error

**本模块不直接接 Channel**——绕 `IPrefrontalCallback` 走，Channel 在依赖图上保持完整外层位置。

## 并发与并行

- 一个 Agent 同时只跑 1 个 NeuralCircuit（主脑装在 sequential `ChatClientAgent`）
- 图内并行走 MAF FanOut/FanIn（`ParallelNode` v1 不实装，占位）
- 多图 / 多 Agent 并发交给 `AgentSystem.ListInstances` + 多个 Channel，与本模块无关
- 单机约束——不考虑跨进程调度

## Dependencies

- `Microsoft.Agents.AI.Workflows` —— 核心 · **不重造引擎**
- `CBIM.AgentSystem.Brain` —— `BrainBase` / `BrainInvocation` / `BrainOutcome`
- `CBIM.AgentSystem.Kernel.Synapse` —— `IPrefrontalCallback`
- `CBIM.AgentSystem.Kernel.Synapse.Compiler` —— `NeuralCircuit` / `CircuitNode` 子类
- **不依赖** `CBIM.Channel`（进度绕 IPrefrontalCallback）
- **不依赖** `Kernel.Neuron`（K4：调 BrainBase 透传全 Neuron）
- **不依赖** `Microsoft.Agents.AI`（调脑区走 BrainBase 抽象，不拿 AIAgent）

## 铁律

- **O1 · 不重造 MAF** —— IR 路由 / 图验证 / Checkpoint / 并行 能交 MAF 都交；CBIM Executor 只包「调 BrainBase + eval ConditionExpression」业务表面
- **O2 · 图不在执行期修改** —— `NeuralCircuit` immutable；重规划 = 主脑重编译
- **O3 · Fail-fast 不 fail-creative** —— 节点失败 → 中断返主脑；不做启发式 fallback 跳节点
- **O4 · 上报绕 IPrefrontalCallback 走** —— 不直接接 Channel；依赖图上 Channel 保留外层位置
- **O5 · Compiler ⊥ Orchestrator** —— namespace 互不 using；中间仅共享抽象 `NeuralCircuit`（定义在 Compiler）

## Non-Goals

- 不实装 ParallelNode / WaitUserNode / CallToolNode（与 Compiler v1 范围一致）
- 不实装复杂表达式语言——v1 ConditionExpression 仅 contains / equals
- 不起独立进程 / 跨机调度——单机约束
- 不重造 MAF 检查点——需要时包 MAF `CheckpointManager` 加一个选项
- 不接管 SystemTool / MCP 装配——BrainBase.Neuron 负责

