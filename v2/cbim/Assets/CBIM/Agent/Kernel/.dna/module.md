---
name: cbim-unity-agent-kernel
owner: architect
description: Agent 内部运行内核（神经系统层）——本轮把原 Brain 内嵌的 msai 装配 + 调度协议下沉为独立子模块。两子模块：Neuron（神经元 · AIAgent 封装 + 引擎扩展点）与 Synapse（突触 · 脑区间派发协议）。Brain 从「拥有 msai」回归为「拥有神经元」，BrainBase 仅持 INeuron 引用——脑区义涵纯化（前额叶/顶叶/海马体/运动皮层只承担调度策略与脑区职责），跨脑区机制下沉到 Kernel。命名沿用神经解剖学：神经元承载 LLM 思维链（msai/external），突触承载脑区间信号传递（__brain_call_* AITool + 回调）。</description>
keywords: []
dependencies: []
status: spec
---

## Positioning

- **神经系统层**——位于 `Agent/` 与 `Agent/Brain/` 之间的中间机制层。
- 承接两件之前内嵌于 Brain 的机制：**神经元装配**（LLM 思维链单元）+ **突触派发**（脑区间信号传递 / FlowGraph 引擎）。
- 让 Brain 层只关注脑区策略（调度 / 推理 / 记忆 / 动作），不再混入「如何挂 LLM」「脑区如何互调」。
- **机制层 vs 策略层**：Kernel 是机制层，保持稳定；Brain 是策略层，可演化。

## 架构图（三层模型中的位置）

```mermaid
flowchart TD
    classDef facade fill:#fce4ec,stroke:#880e4f,color:#000;
    classDef brain  fill:#f3e5f5,stroke:#4a148c,color:#000;
    classDef kernel fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px,color:#000;
    classDef msai   fill:#bbdefb,stroke:#0d47a1,color:#000;

    AS["AgentSystem\n(装配方)"]

    subgraph BRAIN["Agent/Brain (脑区策略层)"]
        PFC["PrefrontalCortex"]
        PL["ParietalLobe"]
        HC["Hippocampus"]
        MC["MotorCortex 家族"]
    end

    subgraph KERNEL["Agent/Kernel (本模块 · 神经系统机制层)"]
        NEU["Neuron/\nINeuron · MsaiNeuron · ExternalEngineNeuron · NeuronFactory"]
        SYN["Synapse/\nFlowGraph 引擎\n(Compiler + Orchestrator + SynapseToolFactory)"]
    end

    subgraph MS["Microsoft 包"]
        MSAI["Microsoft.Agents.AI"]
        MSEXT["Microsoft.Extensions.AI"]
        MSWF["Microsoft.Agents.AI.Workflows"]
    end

    AS -- OpenInstance 装配 --> BRAIN
    AS -- NeuronFactory.Create --> NEU
    AS -- SynapseToolFactory.Build --> SYN
    BRAIN -- 持 INeuron --> NEU
    PFC -- 持 FlowGraph 工具 --> SYN
    NEU --> MSAI
    NEU --> MSEXT
    SYN --> MSWF

    class AS facade;
    class PFC,PL,HC,MC brain;
    class NEU,SYN kernel;
    class MSAI,MSEXT,MSWF msai;
```

**依赖方向**：Brain → Kernel 单向不反向。Kernel 不感知任何具体脑区类型。

## 类图（Kernel 内核心类型 + 与 Brain 的边界）

```mermaid
classDiagram
    class BrainBase {
        <<abstract · in Agent/Brain>>
        +string BrainId
        +INeuron Neuron
        +InvokeAsync(invocation) Task~BrainOutcome~
    }

    class INeuron {
        <<interface · Neuron/>>
        +string NeuronId
        +NeuronKind Kind
        +AIAgent? UnderlyingAgent
        +InvokeAsync(invocation, ct) Task~BrainOutcome~
    }

    class NeuronFactory {
        <<static · Neuron/>>
        +Create(descriptor, ctx)$ INeuron
    }

    class SynapseToolFactory {
        <<static · Synapse/>>
        +Build(callableBrains)$ IReadOnlyList~AITool~
    }

    class IPrefrontalCallback {
        <<interface · Synapse/>>
        +ReportProgress(brainId, message)
        +ReportOutcome(brainId, outcome)
    }

    class IBrainRegistry {
        <<interface · Synapse/>>
        +RegisterBrain(brain)
        +Find(brainId) BrainBase
    }

    class CompilerToolFactory {
        <<static · Synapse/Compiler/>>
        +Build(builder, callable)$ IReadOnlyList~AITool~
    }

    class CBIMOrchestrator {
        <<class · Synapse/Orchestrator/>>
        +RunAsync(circuit, palette, callback, ct) Task~BrainOutcome~
    }

    BrainBase --> INeuron : holds
    NeuronFactory ..> INeuron : creates
    SynapseToolFactory ..> BrainBase : reads BrainId
    CBIMOrchestrator ..> BrainBase : invokes
```

## Children

| 子模块 | 一句话职责 |
|--------|------------|
| `Neuron/` | 神经元——`INeuron` 抽象 + `MsaiNeuron` / `ExternalEngineNeuron` + `NeuronFactory` |
| `Synapse/` | 突触（FlowGraph 引擎）——`Compiler` / `Orchestrator` + 顶层 `SynapseToolFactory` / `IPrefrontalCallback` / `IBrainRegistry` |

**Neuron ⊥ Synapse**：两子模块互不引用；各自被 Brain 层装配点独立调用。

## Dependencies

- `Microsoft.Agents.AI` —— Neuron 装配 `AIAgent`
- `Microsoft.Extensions.AI` —— `IChatClient` / `AIFunction` / `AITool`
- `Microsoft.Agents.AI.Workflows` —— Synapse/Orchestrator 包装
- `CBIM.Memory` —— `IMemoryService`
- `CBIM.AgentSystem.Brain`（**仅描述符家族 + BrainBase**）—— K5
- **不依赖** `CBIM.Tools` / `Skills` / `Mcp` / `Workspace` / `Channel`

## 铁律

- **K1 · 机制不感知策略** —— Kernel 不引用任何具体脑区类型；脑区类型变更不触发 Kernel 修改
- **K2 · Neuron 是唯一 LLM 出口** —— Brain 不准 `new ChatClientAgent` / 直调 `IChatClient`
- **K3 · Synapse 是唯一跨脑区机制出口** —— `__brain_call_*` / FlowGraph / Registry 都在 Synapse
- **K4 · Neuron ⊥ Synapse** —— 互不引用；双方互引 = 设计错误
- **K5 · 描述符语义保留在 Brain** —— Kernel 仅按描述符子类分派，不解读语义字段

## Non-Goals

- 不发明新的 Brain 抽象——Brain 契约不变
- 不接管 BrainConfig 校验——主脑唯一 / 至少一 MotorCortex 仍在 BrainConfig
- 不实现具体外部引擎——`ExternalEngineNeuron` 仅持 `IExternalEngineAdapter`
- 不引入新并发模型——Registry 用粗锁 InMemory

