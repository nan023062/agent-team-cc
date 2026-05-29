using System;
using CBIM.AgentSystem.Kernel.Neuron;
using CBIM.AgentSystem.Kernel.Synapse;
using CBIM.Memory;

namespace CBIM.AgentSystem.Brain
{
    /// <summary>
    /// Hippocampus（海马体）——记忆学习脑。
    ///
    /// <para>日间职责：Memory 读写（<see cref="IMemoryService"/> 的唯一被推荐写入责任脑区）。</para>
    ///
    /// <para>夜间职责（Dream tick）：从累积记忆中提炼能力 / 知识增长信号 → 产出
    /// FissionProposal。<b>本切片不实装裂变信号评估器</b>——FissionProposal 类型 +
    /// 信号评估器 + AIFunction <c>analyze_fission</c> 由后续 Dream 实施切片落地，
    /// 本类先占类名 + 命名空间。</para>
    ///
    /// <para>本类完全继承 <see cref="BrainBase"/> 默认 InvokeAsync——具体能力由
    /// <see cref="StandardBrainDescriptor.Soul"/> + <see cref="StandardBrainDescriptor.Capability"/>
    /// 上声明的 SystemTools / Skills 表达。</para>
    /// </summary>
    public sealed class Hippocampus : BrainBase
    {
        public const string DefaultBrainId = "hippocampus";

        public Hippocampus(
            StandardBrainDescriptor descriptor,
            IMemoryService memory,
            INeuron neuron,
            IPrefrontalCallback callback)
            : base(descriptor?.BrainId ?? throw new ArgumentNullException(nameof(descriptor)),
                   neuron,
                   memory,
                   callback ?? throw new ArgumentNullException(nameof(callback),
                       "Hippocampus 不允许 null callback——子脑区必须能向主脑回报。"))
        {
            if (descriptor.Kind != StandardBrainKind.Hippocampus)
                throw new InvalidOperationException(
                    $"Hippocampus 要求 descriptor.Kind=Hippocampus（实际: {descriptor.Kind}）。");
        }
    }
}
