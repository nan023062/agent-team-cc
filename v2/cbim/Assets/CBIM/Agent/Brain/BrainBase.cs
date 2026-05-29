using System;
using System.Threading;
using System.Threading.Tasks;
using CBIM.AgentSystem.Kernel.Neuron;
using CBIM.AgentSystem.Kernel.Synapse;
using CBIM.Memory;
using Microsoft.Agents.AI;

namespace CBIM.AgentSystem.Brain
{
    /// <summary>
    /// 脑区契约公共基类。
    ///
    /// <para>本轮重要变动（T4）：基类不再持有 <c>IChatClient</c> 也不再做 msai 装配——
    /// 所有 LLM 思维链能力已下沉到 <see cref="CBIM.AgentSystem.Kernel.Neuron.INeuron"/>（K2 铁律：
    /// Neuron 是 Brain 层调用 LLM 的唯一出口）。基类只持 <see cref="Neuron"/> 抽象引用，
    /// 默认 <see cref="InvokeAsync"/> 透传给 <c>Neuron.InvokeAsync</c>；msai 还是 ExternalEngine
    /// 由 NeuronFactory 在装配期决定，基类与子类无感。</para>
    ///
    /// <para>「同一具身一份记忆」铁律的物理落地：<see cref="Memory"/> 由 AgentInstance 在
    /// 装配期注入，所有脑区共享同一 <see cref="IMemoryService"/> 实例。</para>
    ///
    /// <para>「主脑唯一通路」铁律（K3）的物理护栏：<see cref="PrefrontalCallback"/> 是子脑区
    /// 向 PrefrontalCortex 回报的唯一通路；接口极小化（仅 ReportProgress / ReportOutcome），
    /// 反向调度兄弟脑区在类型层面被杜绝。主脑自身的本字段恒为 null。</para>
    /// </summary>
    public abstract class BrainBase : IAsyncDisposable
    {
        /// <summary>脑区在 AgentInstance 内的唯一标识。</summary>
        public string BrainId { get; }

        /// <summary>共享的 Memory 实例——不允许 null（构造期校验）。</summary>
        public IMemoryService Memory { get; }

        /// <summary>
        /// 神经元——LLM 思维链单元。本字段是 Brain 层调用 LLM 的唯一出口（K2 铁律）。
        /// 由 AgentSystem 装配期通过 NeuronFactory 创建并注入；BrainBase 与子类不感知其具体实现
        /// （<see cref="MsaiNeuron"/> 还是 <see cref="ExternalEngineNeuron"/>）。
        /// </summary>
        public INeuron Neuron { get; }

        /// <summary>
        /// 透传 <see cref="Neuron"/> 的底层 <see cref="AIAgent"/> 引用——保留旧字段名以兼容
        /// 已持引用打 <c>SendAsync</c> 的 Channel 等调用方。
        /// <see cref="ExternalEngineNeuron"/> 路径下恒为 <c>null</c>（外部引擎自带 LLM，无 AIAgent 句柄）。
        /// </summary>
        public AIAgent? Agent => Neuron.UnderlyingAgent;

        /// <summary>
        /// 主脑回调——子脑区通过该回调向 PrefrontalCortex 汇报结果。
        /// 主脑自身恒为 <c>null</c>（自己不回报自己）。
        /// </summary>
        protected IPrefrontalCallback? PrefrontalCallback { get; }

        /// <summary>
        /// 构造期仅做字段写入与非空校验。
        /// LLM 装配（msai ChatClientAgent / external Adapter）已下沉到 NeuronFactory；
        /// 子类构造器只须做语义校验（Kind / BrainId 前缀等）并透传给本基类。
        /// </summary>
        /// <param name="brainId">脑区唯一 Id。不为空白。</param>
        /// <param name="neuron">神经元（LLM 出口）。由 NeuronFactory 创建。不为 null。</param>
        /// <param name="memory">共享 Memory 实例。不为 null。</param>
        /// <param name="callback">主脑回调；主脑自身传 <c>null</c>，其他脑区由装配期注入。</param>
        protected BrainBase(
            string brainId,
            INeuron neuron,
            IMemoryService memory,
            IPrefrontalCallback? callback)
        {
            if (string.IsNullOrWhiteSpace(brainId))
                throw new ArgumentException("BrainBase.BrainId 不能为空", nameof(brainId));
            if (neuron == null)
                throw new ArgumentNullException(
                    nameof(neuron),
                    "BrainBase.Neuron 不允许 null——K2 铁律要求 Brain 层 LLM 出口唯一。");
            if (memory == null)
                throw new ArgumentNullException(
                    nameof(memory),
                    "BrainBase.Memory 不允许 null——「同一具身一份记忆」铁律由构造期强制。");

            BrainId = brainId;
            Neuron = neuron;
            Memory = memory;
            PrefrontalCallback = callback;
        }

        /// <summary>
        /// 投递子任务到本脑区。
        ///
        /// 默认实现：直接透传给 <see cref="Neuron"/>.InvokeAsync——
        /// msai / external 的路径差异在 NeuronFactory 装配期已决定，本层无感。
        /// 如需特化（如主脑的聚合策略），子类可重写。
        /// </summary>
        public virtual Task<BrainOutcome> InvokeAsync(BrainInvocation invocation, CancellationToken ct)
        {
            if (invocation == null)
                throw new ArgumentNullException(nameof(invocation));
            return Neuron.InvokeAsync(invocation, ct);
        }

        /// <summary>
        /// 释放本脑区占用的资源。
        /// 默认实现释放 <see cref="Neuron"/>；子类如持有额外资源需重写并最后调用 base。
        /// AgentInstance 的释放顺序保证调用：MotorCortex → 其他脑区 → Prefrontal。
        /// 实现需做到多次调用幂等。
        /// </summary>
        public virtual async ValueTask DisposeAsync()
        {
            await Neuron.DisposeAsync().ConfigureAwait(false);
        }
    }
}
