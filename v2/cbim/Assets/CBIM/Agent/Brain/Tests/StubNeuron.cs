#if UNITY_INCLUDE_TESTS
using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using CBIM.AgentSystem.Brain;
using CBIM.AgentSystem.Kernel.Neuron;
using Microsoft.Agents.AI;

namespace CBIM.AgentSystem.Brain.Tests
{
    /// <summary>
    /// 测试用 <see cref="INeuron"/> 桩——不接 LLM、不接 ChatClient。
    ///
    /// <para>用途：T4 后 BrainBase / Brain 子类不再直接持 IChatClient——
    /// 测试要直接喂 INeuron。本桩按队列返预设 outcome（或 FIFO 队列空时用默认值），
    /// 计数 InvokeAsync 与 DisposeAsync 调用次数。</para>
    ///
    /// <para><see cref="UnderlyingAgent"/> 恒返 null——不模拟 msai 装配；
    /// 需要走 msai 闭环的测试请用 PrefrontalCortex 端到端 fixture（TestMsaiNeuron 路径）。</para>
    /// </summary>
    internal sealed class StubNeuron : INeuron
    {
        private readonly Queue<BrainOutcome> _outcomeQueue = new Queue<BrainOutcome>();
        private readonly BrainOutcome _defaultOutcome;
        private readonly List<string>? _disposalLog;
        private readonly string _label;

        public string NeuronId { get; }
        public NeuronKind Kind { get; }
        public AIAgent? UnderlyingAgent => null;

        public int CallCount { get; private set; }
        public int DisposeCallCount { get; private set; }
        public BrainInvocation? LastInvocation { get; private set; }

        public StubNeuron(string neuronId, BrainOutcome defaultOutcome)
            : this(neuronId, defaultOutcome, kind: NeuronKind.Msai, disposalLog: null, label: "neuron")
        {
        }

        public StubNeuron(
            string neuronId,
            BrainOutcome defaultOutcome,
            NeuronKind kind,
            List<string>? disposalLog,
            string label)
        {
            if (string.IsNullOrWhiteSpace(neuronId))
                throw new ArgumentException("StubNeuron.NeuronId 不能为空", nameof(neuronId));
            if (defaultOutcome == null)
                throw new ArgumentNullException(nameof(defaultOutcome));

            NeuronId = neuronId;
            Kind = kind;
            _defaultOutcome = defaultOutcome;
            _disposalLog = disposalLog;
            _label = label ?? "neuron";
        }

        /// <summary>追加一条「下一次 InvokeAsync 的产出」（FIFO）。</summary>
        public void EnqueueOutcome(BrainOutcome outcome)
        {
            if (outcome == null) throw new ArgumentNullException(nameof(outcome));
            _outcomeQueue.Enqueue(outcome);
        }

        public Task<BrainOutcome> InvokeAsync(BrainInvocation invocation, CancellationToken ct)
        {
            if (invocation == null) throw new ArgumentNullException(nameof(invocation));
            CallCount++;
            LastInvocation = invocation;
            BrainOutcome next = _outcomeQueue.Count > 0 ? _outcomeQueue.Dequeue() : _defaultOutcome;
            return Task.FromResult(next);
        }

        public ValueTask DisposeAsync()
        {
            DisposeCallCount++;
            _disposalLog?.Add(_label);
            return default;
        }
    }
}
#endif
