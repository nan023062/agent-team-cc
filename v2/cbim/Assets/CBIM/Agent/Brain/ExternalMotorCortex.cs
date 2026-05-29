using System;
using CBIM.AgentSystem.Kernel.Neuron;
using CBIM.AgentSystem.Kernel.Synapse;
using CBIM.Memory;

namespace CBIM.AgentSystem.Brain
{
    /// <summary>
    /// ExternalMotorCortex —— 桥接外部 agent 引擎（Claude Code / Cursor / Cline 等）的运动皮层抽象。
    ///
    /// <para>「外部 AI 工具 = 会干活的肌肉」哲学的物理落地——本抽象类是 OO 层面整个
    /// CBIM 唯一允许的 External 分支点（其他脑区无 External 变体）。</para>
    ///
    /// <para>结构差异（T4 后）：</para>
    /// <list type="bullet">
    ///   <item>本类不再持 <see cref="IExternalEngineAdapter"/>——已下沉到 <see cref="ExternalEngineNeuron"/>
    ///         内部。NeuronFactory 在装配期为 <see cref="ExternalMotorCortexDescriptor"/> 路径创建
    ///         ExternalEngineNeuron 并注入 Adapter。</item>
    ///   <item><see cref="BrainBase.Agent"/> 透传 <c>Neuron.UnderlyingAgent</c>，ExternalEngineNeuron 返回 <c>null</c>。</item>
    ///   <item><see cref="BrainBase.InvokeAsync"/> 默认实现透传给 <see cref="BrainBase.Neuron"/>——
    ///         Neuron 走 Adapter 二阶段路径，本类无须 override。</item>
    /// </list>
    ///
    /// <para>本类仍持 <see cref="ShareMode"/>——MemoryShareMode 是 Brain 层语义（描述符语义保留在 Brain，K5），
    /// 非 Neuron 实现细节。</para>
    /// </summary>
    public abstract class ExternalMotorCortex : MotorCortex
    {
        /// <summary>Memory 与外部引擎的共享桥模式——从描述符透传。</summary>
        public MemoryShareMode ShareMode { get; }

        protected ExternalMotorCortex(
            ExternalMotorCortexDescriptor descriptor,
            IMemoryService memory,
            INeuron neuron,
            IPrefrontalCallback callback)
            : base(descriptor?.BrainId ?? throw new ArgumentNullException(nameof(descriptor)),
                   neuron,
                   memory,
                   callback)
        {
            ShareMode = descriptor.MemoryShareMode;
        }
    }
}
