using System;
using System.Collections.Generic;
using CBIM.AgentSystem.Kernel.Neuron;
using CBIM.AgentSystem.Kernel.Synapse;
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
    /// <para>本轮（T7）重要变动：</para>
    /// <list type="bullet">
    ///   <item>构造期不再装配 <c>__brain_call_*</c> AIFunction——该装配已下沉到
    ///     <see cref="SynapseToolFactory"/>，由 AgentSystem 装配期通过
    ///     <c>NeuronAssemblyContext.SynapseAITools</c> 注入 <see cref="INeuron"/>。
    ///     主脑的「调度执行」改由 LLM 在 <see cref="INeuron"/> 内部决定（K3 铁律）。</item>
    ///   <item>不再持有 <c>IChatClient</c>，不再 new <c>ChatClientAgent</c>——
    ///     LLM 装配统一走 NeuronFactory（K2 铁律）。</item>
    ///   <item>新增 <see cref="BrainRegistry"/>——主脑用它支撑 Dream 裂变期间动态注册新脑区。</item>
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
        /// 构造期仅做字段赋值 + 描述符 / CallableBrains 不变量校验。
        /// __brain_call_* AITool 集已由 SynapseToolFactory 在装配期产出并经 NeuronAssemblyContext
        /// 注入到 <see cref="INeuron"/>，本构造器不再做工具装配。
        /// </summary>
        /// <param name="descriptor">主脑描述符——必须 Kind=PrefrontalCortex 且 IsPrefrontal=true。</param>
        /// <param name="memory">共享 Memory 实例。</param>
        /// <param name="neuron">主脑神经元；由 NeuronFactory 创建，已挂载 __brain_call_* AITool 集。</param>
        /// <param name="callback">主脑自身的回调恒为 null（K3 铁律：自己不回报自己），参数保留以对齐基类签名。</param>
        /// <param name="callableBrains">装配期可调度的子脑区清单。</param>
        /// <param name="brainRegistry">脑区动态注册点（Dream 裂变期间用）。</param>
        public PrefrontalCortex(
            StandardBrainDescriptor descriptor,
            IMemoryService memory,
            INeuron neuron,
            IPrefrontalCallback? callback,
            IReadOnlyList<BrainBase> callableBrains,
            IBrainRegistry brainRegistry)
            : base(descriptor?.BrainId ?? throw new ArgumentNullException(nameof(descriptor)),
                   neuron,
                   memory,
                   callback: null)  // 「主脑回调恒为 null」铁律——参数保留仅为对齐, 内部强制 null
        {
            if (callableBrains == null)
                throw new ArgumentNullException(nameof(callableBrains));
            if (brainRegistry == null)
                throw new ArgumentNullException(nameof(brainRegistry));

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
        }
    }
}
