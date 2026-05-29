using System;
using CBIM.AgentSystem.Kernel.Neuron;
using CBIM.AgentSystem.Kernel.Synapse;
using CBIM.Memory;

namespace CBIM.AgentSystem.Brain.ClaudeCode
{
    /// <summary>
    /// <see cref="ExternalMotorCortex"/> 的首发桥接落地——把 Claude Code CLI 作为
    /// 外部运动皮层接入 CBIM 脑区体系。
    ///
    /// <para>本类是<b>极薄</b>包装：构造期校验描述符语义（EngineKind / BrainId）后，
    /// 将 <see cref="INeuron"/>（由 <see cref="NeuronFactory"/> 内部用
    /// <see cref="ClaudeCodeEngineAdapter"/> 装配的 <see cref="ExternalEngineNeuron"/>）
    /// 透传给基类——InvokeAsync / DisposeAsync 全部由 BrainBase 默认路径承接，本类不再 override。</para>
    /// </summary>
    public sealed class ClaudeCodeMotorCortex : ExternalMotorCortex
    {
        /// <summary>默认 BrainId——允许 Dream 裂变期产出 <c>"motor-cortex.claude-code.&lt;variant&gt;"</c> 变体。</summary>
        public const string DefaultBrainId = "motor-cortex.claude-code";

        public ClaudeCodeMotorCortex(
            ExternalMotorCortexDescriptor descriptor,
            IMemoryService memory,
            INeuron neuron,
            IPrefrontalCallback callback)
            : base(
                descriptor ?? throw new ArgumentNullException(nameof(descriptor)),
                memory,
                neuron,
                callback)
        {
            if (descriptor.EngineKind != ExternalEngineKind.ClaudeCode)
                throw new InvalidOperationException(
                    $"ClaudeCodeMotorCortex 要求 descriptor.EngineKind=ClaudeCode（实际: {descriptor.EngineKind}）。");

            if (descriptor.BrainId != DefaultBrainId &&
                !descriptor.BrainId.StartsWith(DefaultBrainId + ".", StringComparison.Ordinal))
                throw new InvalidOperationException(
                    $"ClaudeCodeMotorCortex BrainId 必须 = '{DefaultBrainId}' 或以 '{DefaultBrainId}.' 开头（实际: '{descriptor.BrainId}'）。");
        }
    }
}
