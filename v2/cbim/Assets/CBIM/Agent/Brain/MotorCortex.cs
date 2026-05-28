using System;
using CBIM.Memory;
using Microsoft.Extensions.AI;

namespace CBIM.AgentSystem.Brain
{
    /// <summary>
    /// MotorCortex（运动皮层）—— 抽象基类。
    ///
    /// <para>「副作用唯一出口」铁律的物理护栏：所有「改变世界状态」动作走
    /// MotorCortex 任一具体子类（<see cref="NativeMotorCortex"/> /
    /// <see cref="ExternalMotorCortex"/>）。</para>
    ///
    /// <para>BrainId 强制以 <c>"motor-cortex."</c> 开头（构造期校验）——这是
    /// BrainConfig 「至少一个 MotorCortex」校验所依赖的前缀约定。</para>
    ///
    /// <para>本类<b>不</b>重写 <see cref="BrainBase.InvokeAsync"/>——具体行为由子类决定：
    /// Native 走 msai Agent.RunAsync 默认路径；External 走 Adapter 路径并自行重写。</para>
    /// </summary>
    public abstract class MotorCortex : BrainBase
    {
        public const string BrainIdPrefix = "motor-cortex.";

        protected MotorCortex(
            string brainId,
            BrainDescriptor descriptor,
            IMemoryService memory,
            IChatClient? chatClient,
            IPrefrontalCallback callback)
            : base(brainId, descriptor, memory, chatClient,
                   callback ?? throw new ArgumentNullException(nameof(callback),
                       "MotorCortex 不允许 null callback——子脑区必须能向主脑回报。"))
        {
            if (!brainId.StartsWith(BrainIdPrefix, StringComparison.Ordinal))
                throw new InvalidOperationException(
                    $"MotorCortex BrainId 必须以 '{BrainIdPrefix}' 开头（实际: '{brainId}'）。");
        }
    }
}
