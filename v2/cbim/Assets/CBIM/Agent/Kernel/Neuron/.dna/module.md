---
name: cbim-unity-agent-kernel-neuron
owner: architect
description: 神经元——AIAgent 封装抽象（INeuron）+ 两实现（MsaiNeuron 走 ChatClientAgent 装配 · ExternalEngineNeuron 走 IExternalEngineAdapter 桥接）+ NeuronFactory 装配器（按 BrainDescriptor 子类分派）。本子模块承载「LLM 思维链单元」的封装机制，让 BrainBase 只持 INeuron 引用就拿到完整的 RunAsync 能力，不再感知 msai/external 分支。</description>
keywords: []
dependencies: []
status: spec
---

## Positioning

**神经元（Neuron）= 持 LLM 思维链能力的最小封装单元**。本 leaf 是 Kernel 层两子模块之一（与 Synapse 平级），承担「AIAgent 装配 + 引擎扩展点」机制。

之前（Brain 时代）：`BrainBase` 构造器内嵌 `if (descriptor is StandardBrainDescriptor) ChatClientAgent 装配 else if (ExternalMotorCortexDescriptor) 不装配`——装配分支与脑区职能纠缠。

本轮：把「持 LLM 思维链」机制独立为 `INeuron` 抽象 + `MsaiNeuron` / `ExternalEngineNeuron` 两实现 + `NeuronFactory` 工厂。BrainBase 仅持一个 `INeuron Neuron` 字段，调用 `Neuron.InvokeAsync(...)` 拿结果，**不感知 msai/external 分支**。

## 类型契约

```csharp
namespace CBIM.AgentSystem.Kernel.Neuron;

using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using CBIM.Memory;
using CBIM.AgentSystem.Brain;        // 仅描述符家族（K5 铁律）

/// 神经元——LLM 思维链单元抽象。
///
/// 持有「与一个 LLM 引擎对话的能力」。BrainBase 不感知背后是 msai 还是 external，
/// 只通过该抽象消费。
public interface INeuron : IAsyncDisposable
{
    /// 神经元在 AgentInstance 内的稳定标识——与 BrainId 同名（如 "prefrontal-cortex" / "motor-cortex.native"）。
    string NeuronId { get; }

    /// 引擎种别——主要供 Brain 层做能力体征判断（如「External 不可作为主脑」）。
    /// Msai | External
    NeuronKind Kind { get; }

    /// 核心执行——投递 BrainInvocation，返回 BrainOutcome。
    /// 不感知调用者是哪个脑区（脑区职责 = Brain 层；神经元只负责跑 LLM）。
    Task<BrainOutcome> InvokeAsync(BrainInvocation invocation, CancellationToken ct);

    /// 暴露底层 AIAgent 引用（仅供 Channel 持引用打 SendAsync 用）。
    /// MsaiNeuron 返回真实 ChatClientAgent；ExternalEngineNeuron 返回桥接 stub（NullAIAgent / 自定义包装）。
    AIAgent? UnderlyingAgent { get; }
}

public enum NeuronKind { Msai, External }

/// 标准 Msai 神经元——装配 ChatClientAgent + FunctionInvokingChatClient + AIFunction 集。
/// 走基类 BrainBase 默认 InvokeAsync 路径（包 ChatMessage → Agent.RunAsync → 翻译为 BrainOutcome）。
public sealed class MsaiNeuron : INeuron
{
    public string NeuronId { get; }
    public NeuronKind Kind => NeuronKind.Msai;
    public AIAgent? UnderlyingAgent => _agent;
    private readonly ChatClientAgent _agent;

    public MsaiNeuron(
        string neuronId,
        StandardBrainDescriptor descriptor,
        IChatClient chatClient,
        IMemoryService memory,
        IReadOnlyList<AITool> aiTools);  // 由装配方（NeuronFactory）准备好——含 SystemTools/Skills/Mcp 派生 + Synapse 产 __brain_call_*（仅主脑）

    public Task<BrainOutcome> InvokeAsync(BrainInvocation invocation, CancellationToken ct);
    public ValueTask DisposeAsync();
}

/// 外部引擎神经元——桥接 IExternalEngineAdapter（如 ClaudeCodeEngineAdapter）。
/// 不走 msai，InvokeAsync 路径 = Adapter.SubmitAsync → AwaitResultAsync → BrainOutcome。
public sealed class ExternalEngineNeuron : INeuron
{
    public string NeuronId { get; }
    public NeuronKind Kind => NeuronKind.External;
    public AIAgent? UnderlyingAgent => null;     // 外部引擎自带 LLM，无 AIAgent 句柄
    private readonly IExternalEngineAdapter _adapter;

    public ExternalEngineNeuron(
        string neuronId,
        ExternalMotorCortexDescriptor descriptor,
        IExternalEngineAdapter adapter,
        IMemoryService memory);

    public Task<BrainOutcome> InvokeAsync(BrainInvocation invocation, CancellationToken ct);
    public ValueTask DisposeAsync();
}

/// 神经元工厂——按 BrainDescriptor 子类分派构造。
/// 装配方（AgentSystem.OpenInstance）按描述符调本工厂，拿到 INeuron 实例后再传给 BrainBase 构造器。
public static class NeuronFactory
{
    /// 输入：BrainDescriptor + 上下文资源（IChatClient/Memory/AIFunction 集等）。
    /// 输出：INeuron 实例。
    /// 分派规则：
    ///   StandardBrainDescriptor          → MsaiNeuron
    ///   ExternalMotorCortexDescriptor    → ExternalEngineNeuron（需上下文带 IExternalEngineAdapter）
    /// 其他子类 → InvalidOperationException("unknown BrainDescriptor subclass")
    public static INeuron Create(
        BrainDescriptor descriptor,
        NeuronAssemblyContext ctx);
}

/// 神经元装配上下文——AgentSystem.OpenInstance 准备好后传入。
public sealed record NeuronAssemblyContext(
    IChatClient ChatClient,                              // msai 装配需要
    IMemoryService Memory,
    IReadOnlyList<AITool> StandardAITools,               // 来自 SystemTools/Skills/Mcp（不含 __brain_call_*）
    IReadOnlyList<AITool> SynapseAITools,                // 来自 SynapseToolFactory（仅主脑非空，其他脑区空 list）
    IExternalEngineAdapter? ExternalAdapter);            // External 装配时必填
```

## 与 BrainBase 的协作

`BrainBase` 改造为：

```csharp
public abstract class BrainBase : IAsyncDisposable
{
    public string BrainId { get; }
    public IMemoryService Memory { get; }
    public INeuron Neuron { get; }                       // 本轮重要变动：BrainBase 仅持 INeuron
    protected IPrefrontalCallback PrefrontalCallback { get; }

    /// 默认实现：透传给 Neuron.InvokeAsync。
    /// 任何脑区都可重写（如 PrefrontalCortex 在 InvokeAsync 前后做汇总）。
    public virtual Task<BrainOutcome> InvokeAsync(BrainInvocation invocation, CancellationToken ct)
        => Neuron.InvokeAsync(invocation, ct);
}
```

**关键变动**：BrainBase 不再有 `AIAgent Agent { get; }` 字段——上层（Channel）需要 AIAgent 时走 `instance.Prefrontal.Neuron.UnderlyingAgent`（仅主脑 Channel 路径用得到）。

## 装配流程（AgentSystem.OpenInstance 期）

```
foreach descriptor in brainConfig.Brains:
    standardAITools = BuildStandardAITools(descriptor)              # SystemTools + Skills + Mcp 派生
    synapseAITools = descriptor.IsPrefrontal
                     ? SynapseToolFactory.Build(callableBrains)     # 主脑独有
                     : Array.Empty<AITool>();
    externalAdapter = descriptor is ExternalMotorCortexDescriptor e
                     ? ExternalEngineAdapterRegistry.Resolve(e.EngineKind, e.AdapterConfig)
                     : null;

    ctx = new NeuronAssemblyContext(chatClient, memory, standardAITools, synapseAITools, externalAdapter);
    neuron = NeuronFactory.Create(descriptor, ctx);
    brain = BrainKindToConcreteClass(descriptor, neuron, memory, prefrontalCallback);
    brains.Add(brain);
```

注意：`callableBrains` 在主脑装配前需先完成「装配其他脑区拿到引用集」——OpenInstance 内部按「先装非主脑 → 再装主脑」两阶段顺序进行。

## 测试视角

- BrainBase 测试可 mock `INeuron`——不再需要 mock `IChatClient` + `AIAgent`。
- MsaiNeuron 测试聚焦「装配后 InvokeAsync 跑通 + AITool 集挂载正确」。
- ExternalEngineNeuron 测试聚焦「Adapter 桥接路径 + Memory 共享桥不漏」。
- NeuronFactory 测试聚焦「描述符 → 神经元类型的分派」。

## Dependencies

- `Microsoft.Agents.AI`——`AIAgent` / `AIAgentBuilder` / `ChatClientAgent`
- `Microsoft.Extensions.AI`——`IChatClient` / `AITool` / `AIFunction` / `FunctionInvokingChatClient`
- `CBIM.Memory`——`IMemoryService`（注入字段类型）
- `CBIM.AgentSystem.Brain`（**仅描述符家族**）——`BrainDescriptor` / `StandardBrainDescriptor` / `ExternalMotorCortexDescriptor` / `IExternalEngineAdapter`（K5 铁律：只读描述符做分派，不读脑区类型）
- **不依赖** `CBIM.AgentSystem.Kernel.Synapse`——Neuron ⊥ Synapse（K4 铁律）

## 铁律（继承 Kernel 父铁律 K1-K5）

- 不感知具体脑区类型（K1）
- 是 Brain 层调用 LLM 的唯一出口（K2）
- 不实现具体外部引擎（外部引擎适配走 `Brain/ClaudeCode/` 的 `ClaudeCodeEngineAdapter`，本子模块仅持 `IExternalEngineAdapter` 抽象）

## Non-Goals

- 不实现具体外部引擎适配——`ExternalEngineNeuron` 只持 `IExternalEngineAdapter`，具体如 `ClaudeCodeEngineAdapter` 仍在 `Brain/ClaudeCode/`
- 不引入并发模型——`InvokeAsync` 由调用方控制并发
- 不接管 BrainConfig 校验——「主脑唯一 / 至少一个 MotorCortex」仍在 BrainConfig

## Emergent Insights

1. **「神经元」是「持 LLM 的最小单元」的高带宽命名**——Executor 没说清楚执行什么，Neuron 直接说清楚「持 LLM 思维链的最小单元」。命名即文档。
2. **NeuronKind 枚举优于运行期类型判别**——Brain 层做「External 不可作为主脑」校验时，Kind 枚举比 `neuron is ExternalEngineNeuron` 更稳定（未来加新 NeuronKind 不破坏现有校验代码）。

