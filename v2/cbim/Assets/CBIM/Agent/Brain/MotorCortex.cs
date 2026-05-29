using System;
using CBIM.AgentSystem.Kernel.Neuron;
using CBIM.AgentSystem.Kernel.Synapse;
using CBIM.Memory;

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
    /// <para>本类<b>不</b>重写 <see cref="BrainBase.InvokeAsync"/>——具体执行已由
    /// <see cref="BrainBase.Neuron"/> 承接：Native 路径由 MsaiNeuron 跑 Agent.RunAsync；
    /// External 路径由 ExternalEngineNeuron 跑 Adapter.SubmitAsync + AwaitResultAsync。</para>
    /// </summary>
    public abstract class MotorCortex : BrainBase
    {
        public const string BrainIdPrefix = "motor-cortex.";

        protected MotorCortex(
            string brainId,
            INeuron neuron,
            IMemoryService memory,
            IPrefrontalCallback callback)
            : base(brainId, neuron, memory,
                   callback ?? throw new ArgumentNullException(nameof(callback),
                       "MotorCortex 不允许 null callback——子脑区必须能向主脑回报。"))
        {
            if (!brainId.StartsWith(BrainIdPrefix, StringComparison.Ordinal))
                throw new InvalidOperationException(
                    $"MotorCortex BrainId 必须以 '{BrainIdPrefix}' 开头（实际: '{brainId}'）。");
        }
    }
}
