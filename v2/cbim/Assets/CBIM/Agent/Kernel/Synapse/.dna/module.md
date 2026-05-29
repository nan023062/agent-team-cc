---
name: cbim-unity-agent-kernel-synapse
owner: architect
description: 突触——FlowGraph 引擎（本轮重定义为 CBIM 真正的核心）。承担「把用户自然语言流程编译为确定性 NeuralCircuit + 由 CBIMOrchestrator 硬性按图执行」全套机制。两 leaf 子模块：Compiler（NL 以 NeuralCircuit IR · LLM Function-calling 增量构建）+ Orchestrator（IR 以 MAF Workflow · 包 Microsoft.Agents.AI.Workflows 不重造引擎）。本子模块自身保留 SynapseToolFactory（v1 退为 FlowGraph 中 CallBrainNode 的底层 primitive，未来仅当 LLM 仍需直调脑区作为 1-node 退化路径时使用）+ IPrefrontalCallback + IBrainRegistry + PrefrontalCallbackAdapter（跨脑区上报协议，复用不变）。主脑 PrefrontalCortex 升级为「FlowGraph 编译器 + 监督者」双身份，运行期把图交给 Orchestrator 后退场，仅监督节点失败与 user 决策等待。
keywords: []
dependencies: []
status: spec
---

## Positioning

**Synapse 本轮重定义为 FlowGraph 引擎**——CBIM 真正的核心。上一轮仅是「跨脑区信号传递机制」（产 `__brain_call_*` AITool 集）；本轮升级为「把用户自然语言流程编译为确定性图 + 硬性执行」的全套机制。


## FlowGraph 全链路径（主脑装配期 以 运行期）

**装配期**（AgentSystem.OpenInstance）：

```
# Phase 1 · 装非主脑（与上轮一致，不动）
#   不多叙述

# Phase 2 · 装主脑（本轮重写重点）
callable           = brains.Where(b => !(b is PrefrontalCortex)).ToList()

# (a) 以前仅装 SynapseToolFactory 产物 → 今后同时装三类 AITool：
synapseTools       = SynapseToolFactory.Build(callable)        # 退化原语，允许 LLM 在不需要完整图时直调脑区
builder            = new NeuralCircuitBuilder(circuitId: Guid.NewGuid())
compilerTools      = CompilerToolFactory.Build(builder, callable)  # IR 构建工具集
# (b) 主脑加装一个 'callable' 静态实例变量以供 Orchestrator 访问（当 LLM 调 __circuit_commit 后）
# (c) 可选：未来加 OrchestratorToolFactory（如 __circuit_run / __circuit_resume），v1 不加，交主脑代码路径后调。

prefrontalCtx      = new NeuronAssemblyContext(
    chatClient: ...,
    memory: ...,
    standardAITools: synapseTools.Concat(compilerTools).ToList(),   # 三者并列 · 需动作时 LLM 选何者
    synapseAITools : Array.Empty<AITool>(),                          # SynapseAITools 字段本轮仅作历史兼容位，本轮不再独立填
    externalAdapter: null)
prefrontalNeuron   = NeuronFactory.Create(prefrontalDesc, prefrontalCtx)
prefrontal         = new PrefrontalCortex(..., neuron: prefrontalNeuron, ..., circuitBuilder: builder, callable: callable)
```

**运行期**（主脑接到 user request）：

```
PrefrontalCortex.InvokeAsync(invocation, ct):
  # 主脑 LLM 在 prompt 引导下优先走 FlowGraph 路径：逐步 __circuit_add_* → __circuit_commit
  llmResult = await Neuron.InvokeAsync(invocation, ct)
  if builder.Compiled != null:
      # FlowGraph 路径：LLM 完成了编译
      orchestrator = new CBIMOrchestrator()
      finalOutcome = await orchestrator.RunAsync(
          builder.Compiled, brainPalette: callable, PrefrontalCallback ?? ..., ct)
      return finalOutcome
  else:
      # 退化路径：LLM 只调了 SynapseToolFactory 顶层原语中的一些 __brain_call_*（未装图）
      # 这是「1-node 图」退化，避免于极简单问题（你好）还调 Orchestrator
      return new BrainOutcome(Summary: llmResult.Summary, ...)
```

**三件事同仪装到主脑 Neuron 上的安全性**：

- SynapseToolFactory 产出 `__brain_call_*`：必名足涨前缀，与 Compiler 的 `__circuit_*` 不名冲突。
- CompilerToolFactory 产出 `__circuit_*`：同上。
- LLM 从名字上能看出「这个是直接调」还是「这个是在编译图」。

**Q：LLM 会不会乱选（都应该调 __circuit_* 结果调了 __brain_call_*）**：全靠主脑 Soul 引导。默认 prompt 加一句「任何需要调脑区的请求都走『先编译图』路径；只有闲聊 / 查询 / 调 1 脑区 且 无后续动作 时才可直调 __brain_call_*」。

## SynapseToolFactory 可能的未来去向

两个选项：

| 选项 | 一句话 | 裁决 |
|------|-------|------|
| 保留 · 退化 primitive | 允许主脑 LLM 在极简场景下绕过 Compiler / Orchestrator 直调 | 选 · v1 |
| 删除 | 任何动作都必 以 图，即使 1-node | v2 可选 |

**为什么 v1 保留**：双路径冲突在 LLM Function-calling 场景下可接受（主脑 prompt 引导足够表达），删除会让「主脑说个『你好』都编个图」这种过度强制发生，产生体验不适。重访时机：v1 接入 + 1 周生产使用统计后。

## 为什么重定义为 FlowGraph

上一轮架构下，主脑 PrefrontalCortex 接到 user NL 后靠 LLM 实时决策「下一步该调谁」——靠的是 prompt + AIFunction 触发。三大问题：

1. **Skill 文档「第一步 / 第二步」不可靠**——写在 .md 里的「请先调架构脑、再调运动脑」是「建议」不是「铁律」，模型可能呆。
2. **传统 agent 靠「模型自觉」执行流程**——上轮 SynapseToolFactory 只是把「能调谁」告诉 LLM，LLM 仍是「自己决定调谁」。这是反模式（上轮 T2 交付的 SynapseToolFactory 逆转不了「执行流程靠 LLM 自觉」本质）。
3. **复杂分支逻辑难管理**——「如果退款 > 1000 需审批」写在 prompt 里是「请你判断一下」，写成图上的条件分支节点是「这里必选 A 或 B」。

FlowGraph 解决路径：

- **NL 以 编译为 NeuralCircuit（神经回路·图 IR）**——「建议」变「铁律」。
- **CBIMOrchestrator 硬性按图执行**——LLM 只在节点内部（CallBrain / CallTool 调用期）发挥智能，节点间传递是确定性边。
- **复杂分支逻辑写为专门节点类型**（`BranchNode`），条件在 IR 中明文表达。

## 与 MAF 的关系

本子模块本轮明确裁决：**包 `Microsoft.Agents.AI.Workflows`，不重造引擎**。起子模块 Orchestrator 负责「NeuralCircuit IR 以 MAF `Workflow`」翻译，业务节点装为 `Executor` 子类，MAF 提供 SuperStep 调度 / Checkpoint / FanOut / RequestPort 全部现成能力。

为什么不重造：重造 以 三倍工作量；装配 MAF 以 0 成本获得检查点 / 可视化 / RequestPort（人机交互）/ 并行调度。**不重造 = 架构裁集中最难坚持但最关键的一条**。

## 与上轮定位差别

| 上一轮（已余存） | 本轮 |
|---------------------|------|
| Synapse = 跨脑区信号传递机制 | Synapse = FlowGraph 引擎 |
| 唯一产物：`__brain_call_*` AITool 集 | Compiler IR 构建工具集 + Orchestrator MAF Workflow + SynapseToolFactory 退化原语 |
| 主脑亲自迮d代子脑区调用（LLM 接「下一步」决策） | 主脑产 NeuralCircuit 后退场，Orchestrator 接手驱动（确定性执行） |
| 只能 Sequence（LLM 一次一步） | 原生支持 Sequence / Branch / （占位）Parallel / WaitUser |

## 本子模块现有产物去向

- **SynapseToolFactory 保留**——退为 FlowGraph 中「调某个脑区」节点的底层 primitive（`CallBrainNode` 执行期可仅走 1-node 退化路径，避免每次都需装走 Orchestrator，同时向后兼容，避免一次性删除带来的胶水裂隔）。未来在 100% 节点化后可考虑删除。
- **IPrefrontalCallback / PrefrontalCallbackAdapter / IBrainRegistry / InMemoryBrainRegistry 全部保留**——跨脑区上报协议 + 动态脑区注册是 FlowGraph 上下文下同样需要的机制。

## Children（本轮新增 2 个 leaf）

| 子模块 | 一句话职责 | 状态 |
|--------|------------|------|
| `Compiler/` | NL 以 NeuralCircuit IR 编译器 · LLM Function-calling 增量构建 | spec |
| `Orchestrator/` | NeuralCircuit 以 MAF Workflow + 硬性执行 · 包 Microsoft.Agents.AI.Workflows | spec |

**三者并列、互不引用**（K4 + K6）——Compiler / Orchestrator 与本子模块自身留下的 SynapseToolFactory 三者在同一层级，互不 using。中间额额面上由上级（PrefrontalCortex 在 主脑装配期）装配。

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

**本 parent 本身仅依赖**（SynapseToolFactory / IPrefrontalCallback / IBrainRegistry / PrefrontalCallbackAdapter / InMemoryBrainRegistry 代码体 · 仍在本 parent 目录）：

- `Microsoft.Extensions.AI` —— `AIFunction` / `AIFunctionFactory` / `AITool`（SynapseToolFactory 产出）
- `CBIM.AgentSystem.Brain`（**仅 `BrainBase` + `BrainInvocation` + `BrainOutcome`**）——SynapseToolFactory 需调 `callable.InvokeAsync(...)`；K5 铁律：不读描述符中的任何语义字段（如 `StandardBrainKind`）
- **不依赖** `CBIM.AgentSystem.Kernel.Neuron`——Synapse 与 Neuron 互不引用（K4 铁律）
- **不依赖** `Microsoft.Agents.AI`——本 parent 产生的是 AITool 抽象，不装配具体 AIAgent

**Children leaf 依赖**（仅供参考，详细见各 leaf .dna）：

- `Compiler/` 依赖：`Microsoft.Extensions.AI` + `CBIM.AgentSystem.Brain` 仅 `BrainBase`。**不** 依赖 `Orchestrator/`（K6）。
- `Orchestrator/` 依赖：`Microsoft.Agents.AI.Workflows` + `CBIM.AgentSystem.Brain` + `Compiler/`（仅 `NeuralCircuit` 读取） + parent `IPrefrontalCallback`。**不** 反路依赖 `Compiler/`。

## 铁律（继承 Kernel 父铁律 K1-K5）

- **K1 不感知具体脑区类型**——只读 `BrainBase.BrainId` 生成函数名 / 调 BrainBase.InvokeAsync，不判别类型。
- **K3 跨脑区机制唯一出口**——Brain 不准自定义另一套 `__brain_call_*` 生成逻辑 / 另一套 NeuralCircuit 执行引擎。
- **IPrefrontalCallback 接口极小化**——只 ReportProgress / ReportOutcome，防止反向调度。
- **K6 三 leaf 互不引用**（本轮新增）——`Compiler/` / `Orchestrator/` / `SynapseToolFactory`（本子模块自身原有顶层代码）三者在同一层级，**互不 using**。跨三者装配由上级（PrefrontalCortex 在主脑装配期）完成，避免该三者语义交叉。违反例：Compiler 里 using Orchestrator 类型 = 设计错误（说明「编译后必须怎么执行」被漏动用事到了编译期）。
- **K7 NeuralCircuit 是不可变 IR**（本轮新增）——commit 后包含的 Nodes / Edges 冻结，Orchestrator 只读不改。「重规划」走「主脑发起新一轮编译」路径，产出新 CircuitId。

## Non-Goals

- 不接管「谁可被主脑调」过滤策略——该责任在装配方（AgentSystem.OpenInstance）
- 不接管「主脑超时 / 重试」策略——该责任在 PrefrontalCortex.InvokeAsync 重写中
- 不发明新的并发模型——InMemoryBrainRegistry 用粗锁足够
- 不产出跨 Agent 的脑区调度抽象——跨 Agent 协作是未来 HR 责任

## Emergent Insights

1. **「函数命名规则」是机制不是策略**——之前 `__brain_call_` 前缀推到 PrefrontalCortex 里，似乎是「主脑职能」，其实是「跨脑区机制」。下沉后语义才清晰。
2. **突触不是调度器**——名字重要：上轮叫 Scheduler 让人误以为「本子模块告诉主脑何时调谁」，其实不是——本子模块只提供「主脑可调谁的工具集 + 上报接口」，什么时候调哪个完全是主脑 LLM 决定。Synapse 讲出「信号通路」本质。
3. **`__brain_call_*` 这种隐藏在索引下的函数名是 LLM 可读的**——LLM 看到 `__brain_call_motor_cortex_claude_code` 能从名字推出「这是调名为 motor-cortex.claude-code 的脑区」，不需额外 description。命名 = 描述。

