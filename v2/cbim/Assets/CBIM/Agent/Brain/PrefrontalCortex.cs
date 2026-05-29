using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using CBIM.AgentSystem.Kernel.Neuron;
using CBIM.AgentSystem.Kernel.Synapse;
using CBIM.AgentSystem.Kernel.Synapse.Compiler;
using CBIM.AgentSystem.Kernel.Synapse.Orchestrator;
using CBIM.Memory;

namespace CBIM.AgentSystem.Brain
{
    /// <summary>
    /// PrefrontalCortex（前额叶皮层）—— 主脑 / 调度中枢。
    /// 每个 AgentInstance 有且仅有 1 个；Channel.SendAsync 的实际投递目标。
    ///
    /// <para>「主脑唯一通路」铁律的物理护栏：</para>
    /// <list type="bullet">
    ///   <item><b>sealed</b>——不存在「External 主脑」的语法可能。</item>
    ///   <item><see cref="BrainBase.PrefrontalCallback"/> 永远为 <c>null</c>——自己不回报自己。</item>
    ///   <item>调度仅通过 <c>__brain_call_*</c> AITool 下发——其他脑区互不直调。</item>
    /// </list>
    ///
    /// <para>本轮（T14）FlowGraph 整合：双身份（编译器 + 监督者）。</para>
    /// <list type="bullet">
    ///   <item>装配期挂两类 AITool：
    ///     <c>__brain_call_*</c>（来自 <see cref="SynapseToolFactory"/>，退化路径用） +
    ///     <c>__circuit_*</c>（来自 <see cref="CompilerToolFactory"/>，FlowGraph 路径用），
    ///     拼到 <see cref="NeuronAssemblyContext.StandardAITools"/>。</item>
    ///   <item><see cref="InvokeAsync"/> 重写：每轮新建 <see cref="NeuralCircuitBuilder"/>
    ///     存入 <see cref="ActiveBuilder"/> 字段（CompilerToolFactory 装配期捕获的闭包
    ///     委托永远读最新值）；Neuron 跑完后查 <c>builder.Compiled</c>——
    ///     非 null 走 FlowGraph 路径（落盘 JSON + <see cref="CBIMOrchestrator"/> 执行），
    ///     null 走退化路径（直接返 Neuron 结果）。</item>
    ///   <item>JSON 落盘路径：<c>.cbim/agentsystem/sessions/{instanceId}/circuits/{circuitId}.json</c>
    ///     （D3 决策）。<see cref="_instanceId"/> 由 AgentSystem.OpenInstance 构造期注入。</item>
    /// </list>
    /// </summary>
    public sealed class PrefrontalCortex : BrainBase
    {
        public const string DefaultBrainId = "prefrontal-cortex";

        /// <summary>装配期注入的可调度子脑区清单——不含 PrefrontalCortex 自身。</summary>
        public IReadOnlyList<BrainBase> CallableBrains { get; }

        /// <summary>结果合并策略。本轮仅留枚举与字段；行为由后续 task 视需要实现。</summary>
        public PrefrontalAggregationStrategy Aggregation { get; set; } = PrefrontalAggregationStrategy.SummarizeBeforeReturn;

        /// <summary>
        /// Agent 内部脑区动态注册点——主脑用它支撑 Dream 裂变期间动态注册新脑区（K3 铁律下的
        /// 唯一跨脑区机制出口由 <see cref="CBIM.AgentSystem.Kernel.Synapse"/> 提供）。
        /// </summary>
        public IBrainRegistry BrainRegistry { get; }

        /// <summary>
        /// 本 PrefrontalCortex 所属 Agent 实例的 InstanceId——由 AgentSystem.OpenInstance 注入，
        /// 用于 FlowGraph 路径下 JSON 落盘路径定位。不为空白。
        /// </summary>
        private readonly string _instanceId;

        /// <summary>
        /// 本 Agent 的项目根目录（cwd）——FlowGraph 路径 JSON 落盘用作 <c>.cbim/...</c> 前缀。
        /// 由 AgentSystem.OpenInstance 注入；null 时落到当前进程 cwd（向下兼容现有 jsonl 落盘惯例）。
        /// </summary>
        private readonly string? _projectRoot;

        /// <summary>
        /// 本轮（T14）FlowGraph 路径核心字段——per-invocation builder 槽位。
        /// <see cref="InvokeAsync"/> 入口处 new + 写本字段；CompilerToolFactory 装配期捕获的
        /// 闭包委托 <c>() =&gt; ActiveBuilder</c> 永远读最新值；InvokeAsync 出口处清回 null。
        ///
        /// <para>internal 暴露给同程序集的 AgentSystem 装配期消费——其他类型不应感知本字段。</para>
        ///
        /// <para>线程模型：单 InvokeAsync 通道下不会并发；并发投递的设计由 Channel 层串行化。</para>
        /// </summary>
        internal NeuralCircuitBuilder? ActiveBuilder { get; private set; }

        /// <summary>
        /// 构造期仅做字段赋值 + 描述符 / CallableBrains 不变量校验。
        /// __brain_call_* / __circuit_* AITool 集已由 SynapseToolFactory / CompilerToolFactory
        /// 在装配期产出并经 NeuronAssemblyContext 注入到 <see cref="INeuron"/>，本构造器不再做工具装配。
        /// </summary>
        /// <param name="descriptor">主脑描述符——必须 Kind=PrefrontalCortex 且 IsPrefrontal=true。</param>
        /// <param name="memory">共享 Memory 实例。</param>
        /// <param name="neuron">主脑神经元；由 NeuronFactory 创建，已挂载 __brain_call_* / __circuit_* AITool 集。</param>
        /// <param name="callback">主脑自身的回调恒为 null（K3 铁律：自己不回报自己），参数保留以对齐基类签名。</param>
        /// <param name="callableBrains">装配期可调度的子脑区清单。</param>
        /// <param name="brainRegistry">脑区动态注册点（Dream 裂变期间用）。</param>
        /// <param name="instanceId">所属 Agent 实例 Id——FlowGraph 路径 JSON 落盘用。不为空白。</param>
        /// <param name="projectRoot">项目根目录；null = 当前进程 cwd。</param>
        public PrefrontalCortex(
            StandardBrainDescriptor descriptor,
            IMemoryService memory,
            INeuron neuron,
            IPrefrontalCallback? callback,
            IReadOnlyList<BrainBase> callableBrains,
            IBrainRegistry brainRegistry,
            string instanceId,
            string? projectRoot = null)
            : base(descriptor?.BrainId ?? throw new ArgumentNullException(nameof(descriptor)),
                   neuron,
                   memory,
                   callback: null)  // 「主脑回调恒为 null」铁律——参数保留仅为对齐, 内部强制 null
        {
            if (callableBrains == null)
                throw new ArgumentNullException(nameof(callableBrains));
            if (brainRegistry == null)
                throw new ArgumentNullException(nameof(brainRegistry));
            if (string.IsNullOrWhiteSpace(instanceId))
                throw new ArgumentException("PrefrontalCortex.InstanceId 不能为空——FlowGraph 路径 JSON 落盘必需。", nameof(instanceId));

            // ── 1. 描述符校验
            if (descriptor.Kind != StandardBrainKind.PrefrontalCortex)
                throw new InvalidOperationException(
                    $"PrefrontalCortex 要求 descriptor.Kind=PrefrontalCortex（实际: {descriptor.Kind}）。");
            if (!descriptor.IsPrefrontal)
                throw new InvalidOperationException(
                    "PrefrontalCortex 要求 descriptor.IsPrefrontal=true——「主脑唯一」铁律。");
            descriptor.EnsureInvariants();

            // ── 2. CallableBrains 浅复制 + 自指 / 重复 BrainId / 嵌套主脑 校验
            var copy = new List<BrainBase>(callableBrains.Count);
            var seen = new HashSet<string>(StringComparer.Ordinal);
            foreach (var b in callableBrains)
            {
                if (b == null)
                    throw new ArgumentException("CallableBrains 不允许 null 项。", nameof(callableBrains));
                if (ReferenceEquals(b, this))
                    throw new InvalidOperationException(
                        "PrefrontalCortex 不允许自己调自己——CallableBrains 不能含主脑自身。");
                if (b is PrefrontalCortex)
                    throw new InvalidOperationException(
                        $"CallableBrains 中不允许出现 PrefrontalCortex 类型脑区（'{b.BrainId}'）——「主脑唯一」铁律。");
                if (!seen.Add(b.BrainId))
                    throw new InvalidOperationException(
                        $"CallableBrains 中 BrainId 重复: '{b.BrainId}'。");
                copy.Add(b);
            }
            CallableBrains = copy;
            BrainRegistry = brainRegistry;
            _instanceId = instanceId;
            _projectRoot = projectRoot;
        }

        /// <summary>
        /// 主脑 InvokeAsync——FlowGraph 双路径调度入口。
        ///
        /// <para>流程：</para>
        /// <list type="number">
        ///   <item>新建 per-invocation <see cref="NeuralCircuitBuilder"/>，写入 <see cref="ActiveBuilder"/> 字段；
        ///         CompilerToolFactory 装配期捕获的闭包委托从此处读到最新 builder。</item>
        ///   <item>调 <see cref="BrainBase.Neuron"/>.<see cref="INeuron.InvokeAsync"/>——
        ///         LLM 自决调 <c>__circuit_*</c> 编图 或 <c>__brain_call_*</c> 退化派发。</item>
        ///   <item>查 <c>builder.Compiled</c>——
        ///     <list type="bullet">
        ///       <item>非 null：FlowGraph 路径——JSON 落盘审计 → 调 <see cref="CBIMOrchestrator"/>.RunAsync 执行图。</item>
        ///       <item>null：退化路径——LLM 直接产文本 或 已 __brain_call_* 拿到结果；返 Neuron 原 outcome。</item>
        ///     </list>
        ///   </item>
        ///   <item>finally 清回 <see cref="ActiveBuilder"/>=null——下一轮 InvokeAsync 重新开始。</item>
        /// </list>
        ///
        /// <para>异常策略（C3 铁律：校验失败必回退）：</para>
        /// <list type="bullet">
        ///   <item>JSON 落盘失败 → 不阻塞执行；记录到 ErrorMessage 通过 BrainOutcome 透出（v1 简化版：
        ///     不分裂为单独事件流）。后续切片可改为 SessionEvent 写入。</item>
        ///   <item>Orchestrator 执行异常 → 直接上抛由调用方（Channel / 上一层主脑）决定如何处理。</item>
        /// </list>
        /// </summary>
        public override async Task<BrainOutcome> InvokeAsync(BrainInvocation invocation, CancellationToken ct)
        {
            if (invocation == null)
                throw new ArgumentNullException(nameof(invocation));

            // 1) 新建 per-invocation builder——CircuitId 用新 Guid，SourceRequest 取 invocation.Intent
            //    （即用户自然语言请求；NeuralCircuitBuilder 构造期会校验非空）。
            var builder = new NeuralCircuitBuilder(
                circuitId: Guid.NewGuid().ToString(),
                sourceRequest: invocation.Intent);
            ActiveBuilder = builder;

            try
            {
                // 2) 跑 Neuron——LLM 用挂在 NeuronAssemblyContext.StandardAITools 上的
                //    __circuit_* / __brain_call_* 工具自决编图或直派。
                var llmOutcome = await Neuron.InvokeAsync(invocation, ct).ConfigureAwait(false);

                // 3) 分支：是否产出已 commit 的 NeuralCircuit
                if (builder.Compiled != null)
                {
                    return await RunFlowGraphPathAsync(builder.Compiled, ct).ConfigureAwait(false);
                }

                // 4) 退化路径——LLM 没编图（或 commit 失败抛 IOE 被 FunctionInvokingChatClient
                //    回包给 LLM 让其澄清）；直接返 Neuron 拿到的 outcome（含 LLM 最终文本或
                //    __brain_call_* 触发的子脑区结果）。
                return llmOutcome;
            }
            finally
            {
                ActiveBuilder = null;  // 清场——下一轮 InvokeAsync 重新开始
            }
        }

        /// <summary>
        /// FlowGraph 路径：落盘 JSON 审计 → 调 Orchestrator 执行。
        /// </summary>
        private async Task<BrainOutcome> RunFlowGraphPathAsync(NeuralCircuit circuit, CancellationToken ct)
        {
            // 4a) JSON 落盘——失败不阻塞执行（仅作审计），异常吞掉但记录。
            //     v1 简化策略：失败时把 reason 拼到后续 BrainOutcome.ErrorMessage（如果有），
            //     成功时静默；后续切片可换 SessionEvent 通道。
            string? persistError = null;
            try
            {
                await PersistCircuitJsonAsync(circuit, ct).ConfigureAwait(false);
            }
            catch (OperationCanceledException)
            {
                throw;
            }
            catch (Exception ex)
            {
                persistError = $"circuit JSON 落盘失败: {ex.Message}";
            }

            // 4b) 调 Orchestrator 跑图。callback 走 noop adapter——主脑自身没有回报通路（K3 铁律：
            //     主脑回调恒为 null），FlowGraph 内子脑区上报由 Orchestrator 自己消费 + 转 callback；
            //     用 noop 让 callback 调用静默（与 PrefrontalCortex.PrefrontalCallback==null 同语义）。
            var orchestrator = new CBIMOrchestrator();
            var outcome = await orchestrator
                .RunAsync(circuit, CallableBrains, NoopPrefrontalCallback.Instance, ct)
                .ConfigureAwait(false);

            // 4c) 若落盘有错且 outcome 是成功的，把落盘错误附到 ErrorMessage——不改 IsError
            //     （图执行成功就是成功；落盘只是审计）。
            if (persistError != null && !outcome.IsError)
            {
                return new BrainOutcome(
                    Summary: outcome.Summary,
                    StructuredOutput: outcome.StructuredOutput,
                    SideEffects: outcome.SideEffects,
                    IsError: false,
                    ErrorMessage: persistError);
            }
            return outcome;
        }

        /// <summary>
        /// 落盘 NeuralCircuit JSON 到 <c>.cbim/agentsystem/sessions/{instanceId}/circuits/{circuitId}.json</c>。
        ///
        /// <para>NeuralCircuit / CircuitNode 是接口/抽象类层级，System.Text.Json 直接序列化无法
        /// 多态展开节点子类——这里投影到一个扁平 DTO 树，包含 type discriminator 字段以利
        /// 离线工具解析。</para>
        /// </summary>
        private async Task PersistCircuitJsonAsync(NeuralCircuit circuit, CancellationToken ct)
        {
            string root = _projectRoot ?? Directory.GetCurrentDirectory();
            string dir = Path.Combine(root, ".cbim", "agentsystem", "sessions", _instanceId, "circuits");
            Directory.CreateDirectory(dir);

            string path = Path.Combine(dir, circuit.CircuitId + ".json");

            var dto = new
            {
                circuitId = circuit.CircuitId,
                sourceRequest = circuit.SourceRequest,
                startNodeId = circuit.StartNodeId,
                compiledAt = circuit.CompiledAt,
                nodes = circuit.Nodes.Select(ProjectNode).ToList(),
                edges = circuit.Edges.Select(e => new
                {
                    fromNodeId = e.FromNodeId,
                    toNodeId = e.ToNodeId,
                    branchLabel = e.BranchLabel,
                }).ToList(),
            };

            string json = JsonSerializer.Serialize(dto, new JsonSerializerOptions { WriteIndented = true });

            // File.WriteAllTextAsync 在 netstandard 2.0 / Unity 2020.3 不可用——用 FileStream + StreamWriter 统一路径。
            using (var fs = new FileStream(path, FileMode.Create, FileAccess.Write, FileShare.None))
            using (var sw = new StreamWriter(fs))
            {
                await sw.WriteAsync(json).ConfigureAwait(false);
            }
        }

        /// <summary>投影 <see cref="CircuitNode"/> 子类为 JSON 友好 DTO + type discriminator。</summary>
        private static object ProjectNode(CircuitNode node)
        {
            switch (node)
            {
                case CallBrainNode cb:
                    return new
                    {
                        type = "callBrain",
                        nodeId = cb.NodeId,
                        label = cb.Label,
                        targetBrainId = cb.TargetBrainId,
                        intent = cb.Intent,
                        structuredInputJson = cb.StructuredInputJson,
                    };
                case BranchNode bn:
                    return new
                    {
                        type = "branch",
                        nodeId = bn.NodeId,
                        label = bn.Label,
                        conditionExpression = bn.ConditionExpression,
                    };
                case ReturnNode rn:
                    return new
                    {
                        type = "return",
                        nodeId = rn.NodeId,
                        label = rn.Label,
                        summaryTemplate = rn.SummaryTemplate,
                    };
                default:
                    return new
                    {
                        type = "unknown",
                        nodeId = node.NodeId,
                        label = node.Label,
                        runtimeType = node.GetType().FullName,
                    };
            }
        }

        /// <summary>
        /// 空回调——FlowGraph 路径调 <see cref="CBIMOrchestrator.RunAsync"/> 时占位用。
        /// 主脑 PrefrontalCallback 恒为 null（K3 铁律），但 Orchestrator API 要求 non-null callback——
        /// 用本类静默丢弃所有事件（与 K3 语义一致）。
        /// </summary>
        private sealed class NoopPrefrontalCallback : IPrefrontalCallback
        {
            public static readonly NoopPrefrontalCallback Instance = new NoopPrefrontalCallback();

            private NoopPrefrontalCallback() { }

            public void ReportProgress(string brainId, string message) { }

            public void ReportOutcome(string brainId, BrainOutcome outcome) { }
        }
    }
}
