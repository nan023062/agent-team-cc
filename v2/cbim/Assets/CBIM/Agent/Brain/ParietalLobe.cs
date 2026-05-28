using System;
using System.Threading.Tasks;
using CBIM.Memory;
using Microsoft.Extensions.AI;

namespace CBIM.AgentSystem.Brain
{
    /// <summary>
    /// ParietalLobe（顶叶）——架构脑。
    ///
    /// <para>职责：模块设计 / 知识蓝图 / 架构合规校验 / 协助 Hippocampus 落地裂变设计。</para>
    ///
    /// <para>本类完全继承 <see cref="BrainBase"/> 默认 InvokeAsync——架构脑的特化由
    /// <see cref="StandardBrainDescriptor.Soul"/> + <see cref="StandardBrainDescriptor.Capability"/>
    /// 上声明的 SystemTools / Skills 表达，<b>无</b>类层新增字段。</para>
    /// </summary>
    public sealed class ParietalLobe : BrainBase
    {
        public const string DefaultBrainId = "parietal-lobe";

        public ParietalLobe(
            StandardBrainDescriptor descriptor,
            IMemoryService memory,
            IChatClient chatClient,
            IPrefrontalCallback callback)
            : base(descriptor?.BrainId ?? throw new ArgumentNullException(nameof(descriptor)),
                   descriptor,
                   memory,
                   chatClient,
                   callback ?? throw new ArgumentNullException(nameof(callback),
                       "ParietalLobe 不允许 null callback——子脑区必须能向主脑回报。"))
        {
            if (descriptor.Kind != StandardBrainKind.ParietalLobe)
                throw new InvalidOperationException(
                    $"ParietalLobe 要求 descriptor.Kind=ParietalLobe（实际: {descriptor.Kind}）。");
        }

        /// <inheritdoc/>
        public override ValueTask DisposeAsync() => default;
    }
}
