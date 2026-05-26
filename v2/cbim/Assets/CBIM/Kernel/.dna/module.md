---
name: cbim-unity-kernel
owner: architect
description: CBIM execution engine: BT primitives (Node/Status/Composite/Decorator), Blackboard, Runner, and the execution/dream root flowcharts. Depends on Storage for snapshots and on Memory's read/write API for the CRUD sub-loop.
keywords: []
dependencies: []
status: spec
---

## Positioning

CBIM 的原生 C# 执行引擎。承载行为树原语（Node / Status / Composite / Decorator / Blackboard / Runner）、执行根流程图拓扑、记忆 CRUD 子循环。唯一入口是 `Engine.Tick(blackboard)`——形态与 Python 的 `Runner.run(bb)` 一致。

严格对齐 `v1/kernel/engine/`。每一个原语（Status 枚举、Node 基类、Sequence、Selector、LoopSeq、SwitchBranch、ForEach、AlwaysSuccess、ModeBranch、Trace、Timeout、Retry、Catch）都有 1:1 的 C# 对照，**同名同语义**。Python 的 `main_loop.py` 拓扑被翻译成 C# 的 `BuildExecutionRoot()` 构造器。读 Python 源码就是 C# 移植版的文档。

## Responsibility（一句话）

以 tick 驱动流程图，承载快照 / yield / resume，向 host（Unity 场景或 LLM 客户端）抛出派工请求。

## Sub-Areas（仅为子目录，不再切 asmdef）

从 `.dna/` 视角这是 leaf 模块（只对应一个 asmdef `CBIM.Server.Kernel`），但代码内部按目录与 Python 布局对齐，方便交叉对照：

| 目录 | 用途 | Python 对应物 |
|------|------|--------------|
| `Core/` | Node / Status / Blackboard / 组合节点 / 装饰器 / Runner。铁律：跨 tick 无状态。 | `v1/kernel/engine/core/` |
| `Execution/Actions/` | 叶节点——InitTick、ModeClassify、DirectReply、DispatchCoreAgent、DispatchWork、ArchExecYield、ConvergeJudge、Respond、FlushMemory、ContextRetrieval | `v1/kernel/engine/execution/actions/` |
| `Execution/Tree/` | `BuildExecutionRoot()`——静态拓扑构造器 | `v1/kernel/engine/execution/tree/main_loop.py` |
| `Execution/Loops/` | 进程内驱动的子循环（首批是 MemoryCrud；ArchExec / HrExec 在 v3.5+ 是进程外 yield） | `v1/kernel/engine/execution/loops/` |
| `Persistence/` | 黑板 JSON 快照、resume.json、trace.jsonl——全部经 Storage | `v1/kernel/engine/persistence/` |
| `Api/` | 公共表面：`Engine.Tick`、`Engine.Resume`、`BtResult`、`DispatchRequest`、`Task` | `v1/kernel/engine/execution/api/` |

以目录而非嵌套 asmdef 组织，是为了避免 asmdef 依赖图臃肿；C1 边界落在**模块层**（即 asmdef），不落在每个子目录。模块内部类用 C# `internal` 可见性在 asmdef 内强制封装。

## Public Contract

```csharp
public static class Engine
{
    BtResult Tick(string userRequest);                            // 新 tick
    BtResult Resume(string tickId, object dispatchResult);         // 继续 yielded tick
    IReadOnlyList<TickStatus> ListRunningTicks();
    void Abort(string tickId, string reason);
}
```

`BtResult.Kind ∈ {Done, Yield, Error}`。当 `Yield` 时，host 读 `BtResult.DispatchRequest`（agent_type、agent_file、prompt、subtask_id、required_capability），然后按自己想要的方式跑那个 agent（在 Unity 里大概率是经场景侧适配器走 HTTP 调 LLM 提供商），再调 `Resume(tickId, dispatchResult)` 续跑。**契约形态与 Python 的 `bt_tick` / `bt_tick_resume` 完全相同。**

## Dependencies

- `CBIM.Memory`——CRUD 子循环的读写叶与 FlushMemory 动作经此调用。
- `CBIM.Storage`——黑板 / resume / trace 持久化经此落盘。
- `Core/` **不准用任何 Unity 引擎 API**（引擎必须能在纯 C# 的 Edit Mode 下测）；只有 `Persistence/` 与 `Api/` 才允许通过 Storage 间接触到 `Application.persistentDataPath`。

## 铁律

1. **节点对象 `self` 上不存任何跨 tick 状态。** 这条对齐 Python README §2。每个 tick 内部的局部变量没事，但活过 tick 的实例字段一律禁止。这条铁律是"组合节点能从 resume.json 重建"的根本前提。
2. **`bb.RunnerResumePath` 的唯一写者是 Runner。** 组合节点读它来跳过已完成的子节点，**绝不**改它。
3. **本模块不嵌 LLM 客户端**——与 Python 内核 PR-D 之后的形态一致。ModeClassify 只走规则（规则没命中即 "execution"）；任何 LLM 驱动的决策只发生在 yield 出去由外部 agent 完成的位点。
4. **进程内子循环不准 yield。** MemoryCrud 是纯进程内子循环，**不走** Runner 往返。进程外的工作（ArchExecYield、DispatchWork、DispatchCoreAgent）通过设置 `bb.PendingDispatch` 并返回 `RUNNING` 来 yield。

## Implementation Order（本模块内部）

对齐父模块整体顺序的第 3-5 步：

1. `Core/` 原语——Status、Node、Blackboard、Sequence、Selector、SwitchBranch、ForEach、LoopSeq、AlwaysSuccess。（装饰器下一步发。）
2. `Core/` 装饰器——Trace、Timeout、Retry、Catch。
3. `Core/Runner.cs` + `Persistence/`——快照 / resume / trace。
4. `Execution/Actions/` 最小集——InitTick、ModeClassify、DirectReply、Respond。足够跑通对话分支。
5. `Execution/Tree/BuildExecutionRoot.cs`——把上述节点装成 v3.5 拓扑。执行分支的叶（DispatchWork、ArchExecYield、ConvergeJudge、FlushMemory）此阶段先以 yield 桩件存在，由 host 在外部完成。
6. `Execution/Loops/MemoryCrud.cs`——进程内子循环，接 `CBIM.Memory.MemoryService`。
7. `Api/Engine.cs` + `BtResult` / `DispatchRequest` / `Task` 数据类——公共表面。

## Mirror in Python kernel

按以下顺序读 Python 源码，即可定位每个 C# 部件的语义来源：

| C# 类 | Python 源文件 |
|-------|--------------|
| `Status`、`Node` | `v1/kernel/engine/core/node.py` |
| `Blackboard` | `v1/kernel/engine/core/blackboard.py` |
| `Sequence` / `Selector` / `LoopSeq` / `SwitchBranch` / `ForEach` / `AlwaysSuccess` / `ModeBranch` | `v1/kernel/engine/core/composite.py` |
| `Trace` / `Timeout` / `Retry` / `Catch` | `v1/kernel/engine/core/decorator.py` |
| `Runner` | `v1/kernel/engine/core/runner.py` |
| `BuildExecutionRoot` | `v1/kernel/engine/execution/tree/main_loop.py` |
| `Engine.Tick` / `Engine.Resume` | `v1/kernel/engine/execution/api/bt_tick.py` |
| `BtResult` / `DispatchRequest` / `Task` | `v1/kernel/engine/execution/api/result.py` |
| `MemoryCrud` 子循环 | `v1/kernel/engine/execution/loops/memory_crud.py` |

这套 1:1 映射就是本模块的交付物：Python 与 C# 两套内核同步前进，`design/` 下的设计稿对两边同时适用。
