using System;
using CBIM.AgentSystem.Kernel.Neuron;
using CBIM.AgentSystem.Kernel.Synapse;
using CBIM.Memory;

namespace CBIM.AgentSystem.Brain
{
    /// <summary>
    /// NativeMotorCortex —— 由 <see cref="MsaiNeuron"/> 驱动的本地运动皮层。BrainConfig.Default 默认装 1 个。
    ///
    /// <para>BrainId 约定：默认 <c>"motor-cortex.native"</c>；允许 Dream 裂变期产出
    /// <c>"motor-cortex.&lt;specialty&gt;"</c> 子型号（如 <c>"motor-cortex.refactor"</c>）——
    /// 由 <see cref="StandardBrainDescriptor.BrainId"/> 携带，本类只验前缀。</para>
    ///
    /// <para>能力下发：<see cref="StandardBrainDescriptor.Capability"/> 上声明的
    /// SystemTools / McpList 默认全部下发到本脑区——由 AgentSystem.OpenInstanceAsync
    /// 在装配期挂到 <see cref="NeuronAssemblyContext"/>，再由 NeuronFactory 透传给
    /// 底层 ChatClientAgent 的 <c>ChatOptions.Tools</c>，本类不再直接消费。</para>
    /// </summary>
    public sealed class NativeMotorCortex : MotorCortex
    {
        public const string DefaultBrainId = "motor-cortex.native";

        public NativeMotorCortex(
            StandardBrainDescriptor descriptor,
            IMemoryService memory,
            INeuron neuron,
            IPrefrontalCallback callback)
            : base(descriptor?.BrainId ?? throw new ArgumentNullException(nameof(descriptor)),
                   neuron,
                   memory,
                   callback)
        {
            if (descriptor.Kind != StandardBrainKind.NativeMotorCortex)
                throw new InvalidOperationException(
                    $"NativeMotorCortex 要求 descriptor.Kind=NativeMotorCortex（实际: {descriptor.Kind}）。");
        }
    }
}
