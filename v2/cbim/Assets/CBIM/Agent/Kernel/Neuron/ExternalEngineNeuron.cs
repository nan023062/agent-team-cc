using System;
using System.Threading;
using System.Threading.Tasks;
using CBIM.AgentSystem.Brain;
using CBIM.Memory;
using Microsoft.Agents.AI;

namespace CBIM.AgentSystem.Kernel.Neuron
{
    /// <summary>
    /// 外部引擎神经元——桥接 <see cref="IExternalEngineAdapter"/>（如 ClaudeCodeEngineAdapter）。
    ///
    /// <para>不走 msai；<see cref="InvokeAsync"/> 路径 = Adapter.SubmitAsync → AwaitResultAsync →
    /// 直接返回 Adapter 内部构造的 <see cref="BrainOutcome"/>。</para>
    ///
    /// <para><see cref="UnderlyingAgent"/> 恒为 <c>null</c>——外部引擎自带 LLM，无 AIAgent 句柄。</para>
    /// </summary>
    public sealed class ExternalEngineNeuron : INeuron
    {
        public string NeuronId { get; }
        public NeuronKind Kind => NeuronKind.External;
        public AIAgent? UnderlyingAgent => null;

        private readonly IExternalEngineAdapter _adapter;
        private readonly IMemoryService _memory;
        private int _disposed;

        /// <param name="neuronId">神经元 Id（=BrainId · 必为 "motor-cortex." 开头）。</param>
        /// <param name="descriptor">外部运动皮层描述符——本构造期不读语义字段，仅持引用供子类回查。</param>
        /// <param name="adapter">外部引擎适配器。不为 null。</param>
        /// <param name="memory">共享 Memory 实例。不为 null。</param>
        public ExternalEngineNeuron(
            string neuronId,
            ExternalMotorCortexDescriptor descriptor,
            IExternalEngineAdapter adapter,
            IMemoryService memory)
        {
            if (string.IsNullOrWhiteSpace(neuronId))
                throw new ArgumentException("ExternalEngineNeuron.NeuronId 不能为空", nameof(neuronId));
            if (descriptor == null)
                throw new ArgumentNullException(nameof(descriptor));
            if (adapter == null)
                throw new ArgumentNullException(nameof(adapter));
            if (memory == null)
                throw new ArgumentNullException(nameof(memory));

            NeuronId = neuronId;
            _adapter = adapter;
            _memory = memory;
        }

        /// <inheritdoc/>
        public async Task<BrainOutcome> InvokeAsync(BrainInvocation invocation, CancellationToken ct)
        {
            if (invocation == null)
                throw new ArgumentNullException(nameof(invocation));

            var jobId = await _adapter.SubmitAsync(invocation, ct).ConfigureAwait(false);
            var outcome = await _adapter.AwaitResultAsync(jobId, ct).ConfigureAwait(false);
            return outcome;
        }

        /// <inheritdoc/>
        public async ValueTask DisposeAsync()
        {
            if (Interlocked.Exchange(ref _disposed, 1) != 0)
                return;

            await _adapter.DisposeAsync().ConfigureAwait(false);
        }
    }
}
