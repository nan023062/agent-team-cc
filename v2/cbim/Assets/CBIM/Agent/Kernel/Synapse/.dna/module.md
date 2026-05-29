---
name: cbim-unity-agent-kernel-synapse
owner: architect
description: 突触——脑区间派发协议（SynapseToolFactory · IPrefrontalCallback · IBrainRegistry · PrefrontalCallbackAdapter）。本子模块承载「脑区之间如何互相调」的机制：主脑通过 __brain_call_* AITool 集投递子任务到目标脑区，子脑区通过 IPrefrontalCallback 上报中间进度/最终结果，BrainRegistry 维护可调度脑区集合（Dream 裂变出新 MotorCortex 时动态注册）。Brain 层只消费本子模块产物，不感知函数命名规则/参数 schema/回调路由细节。
keywords: []
dependencies: []
status: spec
---

## Positioning

**突触（Synapse）= 脑区间信号传递机制的最小封装单元**。本 leaf 是 Kernel 层两子模块之二（与 Neuron 平级），承担「主脑如何派发子任务到其他脑区 + 子脑区如何上报」机制。

之前（Brain 时代）：PrefrontalCortex 构造器内嵌 `BuildBrainCallFunction(callable)` + `BrainCallTrampoline`——函数命名规则（`__brain_call_motor_cortex_native`）、参数 schema、调用路由、结果回填都缠在 PrefrontalCortex 类里。

本轮：把「跨脑区信号通路」全套机制下沉为独立 leaf。Brain/PrefrontalCortex 仅调 `SynapseToolFactory.Build(callableBrains)` 拿到 `IReadOnlyList<AITool>`，以及 `IPrefrontalCallback` 表达「子脑区 → 主脑」上报接口。谁叫什么名 / 如何路由 / 如何超时 ——不再是 Brain 的事。

## 类型契约

```csharp
namespace CBIM.AgentSystem.Kernel.Synapse;

using Microsoft.Extensions.AI;
using CBIM.AgentSystem.Brain;        // 仅 BrainBase 引用（K5 铁律）

/// 突触工具工厂——产生主脑可调用的 __brain_call_* AITool 集。
///
/// 调用方（PrefrontalCortex 装配期）传入可调脑区的引用集，拿到一组 AITool 后
/// 挂到主脑 Neuron 装配上下文的 SynapseAITools 中。
public static class SynapseToolFactory
{
    /// 产生 __brain_call_* AITool 集。
    /// 函数命名规则："__brain_call_" + BrainId.Replace('.', '_').Replace('-', '_')
    ///   例："motor-cortex.native"      → "__brain_call_motor_cortex_native"
    ///         "motor-cortex.claude-code" → "__brain_call_motor_cortex_claude_code"
    /// 参数 schema：{ intent: string (required), structured?: object, context?: object }
    /// 处理器：调 callable.InvokeAsync(BrainInvocation) 后取 outcome.Summary 回填 ToolMessage。
    /// 备注：主脑不会被包进可调集（调用方责任过滤；工厂不隐含过滤）。
    public static IReadOnlyList<AITool> Build(IReadOnlyList<BrainBase> callableBrains);
}

/// 主脑回调接口——子脑区只可「上报」，不可「下发」。
/// 跨脑区数据流必经主脑中转——主脑唯一调度铁律的物理护栏。
public interface IPrefrontalCallback
{
    /// 上报中间状态（如长任务进度）；主脑可选择透传到 Channel.OnOutput。
    void ReportProgress(string brainId, string message);

    /// 上报最终产出——主脑路由（默认合入下一次 LLM 上下文）。
    void ReportOutcome(string brainId, BrainOutcome outcome);
}

/// 默认回调连接器——把上报路由给主脑实例或主脑 Neuron。
/// 本轮实装可为占位类（虚函数 + 日志）；产出机制在后续轮足。
public sealed class PrefrontalCallbackAdapter : IPrefrontalCallback
{
    public PrefrontalCallbackAdapter(Func<string, BrainOutcome, Task> onOutcome);
    public void ReportProgress(string brainId, string message);
    public void ReportOutcome(string brainId, BrainOutcome outcome);
}

/// 脑区注册表——Dream 裂变产出新 MotorCortex 时在该表注册。
public interface IBrainRegistry
{
    void RegisterBrain(BrainBase brain);          // 裂变产出调
    bool UnregisterBrain(string brainId);         // HR 责任（本轮不实装但保留接口）
    BrainBase? Find(string brainId);
    IReadOnlyList<BrainBase> All();
}

/// 默认内存实现——一床粗锁 + Dictionary<string, BrainBase>。
public sealed class InMemoryBrainRegistry : IBrainRegistry { ... }
```

## 主脑装配期消费 SynapseToolFactory

```csharp
// AgentSystem.OpenInstance（主脑装配阶段）
var callable = brains.Where(b => !(b is PrefrontalCortex)).ToList();
var synapseTools = SynapseToolFactory.Build(callable);

var prefrontalCtx = new NeuronAssemblyContext(
    chatClient: ...,
    memory: ...,
    standardAITools: prefrontalDesc.StandardTools,           // SystemTools/Skills/Mcp 派生（主脑默认空）
    synapseAITools: synapseTools,                            // 仅主脑非空
    externalAdapter: null);
var prefrontalNeuron = NeuronFactory.Create(prefrontalDesc, prefrontalCtx);
var prefrontal = new PrefrontalCortex(prefrontalNeuron, memory, callbackAdapter, brainRegistry);
```

**“Callable” 过滤责任在装配方**：谁可以被主脑调叫是 Brain 层決定（默认「除主脑外所有」，未来可加「MotorCortex 优先 / Hippocampus 仅 Dream 期可调」等策略）。Synapse 不什么装配。

## SynapseToolFactory.Build 伪代码

```
for each callable in callableBrains:
    name = "__brain_call_" + callable.BrainId.Replace('.', '_').Replace('-', '_')
    description = $"Dispatch sub-task to brain '{callable.BrainId}'. "
                  + $"Use when: <role description from descriptor.Soul 首行或 BrainId 映射>"
    parameters schema = {
        intent: { type: "string", required: true },
        structured: { type: "object", required: false },
        context: { type: "object", required: false }
    }
    handler = async (args, ct) => {
        invocation = new BrainInvocation(
            CorrelationId: Guid.NewGuid().ToString(),
            Intent: args.intent,
            StructuredInput: args.structured,
            Context: args.context ?? new Dictionary<string, object>()
        );
        outcome = await callable.InvokeAsync(invocation, ct);
        return outcome.Summary;  // 作为 ToolMessage 回填 LLM
    };
    tool = AIFunctionFactory.Create(name, description, parameters schema, handler);
    tools.Add(tool);
return tools;
```

## IBrainRegistry 与 Dream 裂变

裂变路径（Dream tick）：

```
Hippocampus 产出 CapabilityFissionProposal
   ↓ ReportOutcome → PrefrontalCortex
   ↓ 主脑 LLM 决策裂变
   ↓ 调 __brain_call_motor_cortex_native(「使用 NeuronFactory 创建 NewMotorCortex · 在 IBrainRegistry 注册」)
   ↓ NativeMotorCortex 执行装配 + RegisterBrain(newMotor)
   ↓ AgentInstance 重装（CloseInstance + OpenInstance）——主脑 SynapseToolFactory.Build 重跑拿到新的 __brain_call_*。
```

**为什么重装而不动态注入 AIFunction**：动态注入 `ChatClientAgent.AIFunctions` 需考虑跟踪中调用的上下文 / 状态，代价比「CloseInstance + OpenInstance」高许多。初期实装走后者。后期如果需要在不重装下添加脑区（如重要对话中间裂变），再升级为动态注入。

## Dependencies

- `Microsoft.Extensions.AI`——`AIFunction` / `AIFunctionFactory` / `AITool`（工厂产出）
- `CBIM.AgentSystem.Brain`（**仅 BrainBase + BrainInvocation + BrainOutcome**）——工厂需调 `callable.InvokeAsync(...)`；K5 铁律：不读描述符中的任何语义字段（如 `StandardBrainKind`）
- **不依赖** `CBIM.AgentSystem.Kernel.Neuron`——Synapse ⊥ Neuron（K4 铁律）
- **不依赖** `Microsoft.Agents.AI`——Synapse 产生的是 AITool 抽象，不装配具体 AIAgent

## 铁律（继承 Kernel 父铁律 K1-K5）

- 不感知具体脑区类型（K1）——只读 `BrainBase.BrainId` 生成函数名，不判别类型
- 是跨脑区机制唯一出口（K3）——Brain 不准自定义另一套 __brain_call_* 生成逻辑
- IPrefrontalCallback 接口极小化——只 ReportProgress / ReportOutcome，防止反向调度

## Non-Goals

- 不接管「谁可被主脑调」过滤策略——该责任在装配方（AgentSystem.OpenInstance）
- 不接管「主脑超时 / 重试」策略——该责任在 PrefrontalCortex.InvokeAsync 重写中
- 不发明新的并发模型——InMemoryBrainRegistry 用粗锁足够
- 不产出跨 Agent 的脑区调度抽象——跨 Agent 协作是未来 HR 责任

## Emergent Insights

1. **「函数命名规则」是机制不是策略**——之前 `__brain_call_` 前缀推到 PrefrontalCortex 里，似乎是「主脑职能」，其实是「跨脑区机制」。下沉后语义才清晰。
2. **突触不是调度器**——名字重要：上轮叫 Scheduler 让人误以为「本子模块告诉主脑何时调谁」，其实不是——本子模块只提供「主脑可调谁的工具集 + 上报接口」，什么时候调哪个完全是主脑 LLM 决定。Synapse 讲出「信号通路」本质。
3. **`__brain_call_*` 这种隐藏在索引下的函数名是 LLM 可读的**——LLM 看到 `__brain_call_motor_cortex_claude_code` 能从名字推出「这是调名为 motor-cortex.claude-code 的脑区」，不需额外 description。命名 = 描述。

