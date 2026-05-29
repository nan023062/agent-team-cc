using System;
using System.Threading;
using System.Threading.Tasks;
using CBIM.AgentSystem.Brain;
using Microsoft.Agents.AI;

namespace CBIM.AgentSystem.Kernel.Neuron
{
    /// <summary>
    /// 神经元——LLM 思维链单元抽象。
    ///
    /// <para>持有「与一个 LLM 引擎对话的能力」。BrainBase 不感知背后是 msai 还是 external，
    /// 只通过该抽象消费 LLM 能力。两实现：<see cref="MsaiNeuron"/>（msai 装配） /
    /// <see cref="ExternalEngineNeuron"/>（外部引擎桥接）。</para>
    ///
    /// <para>K2 铁律：本接口是 Brain 层调用 LLM 的<b>唯一出口</b>——任何脑区想调 LLM
    /// 必须经 <see cref="InvokeAsync"/>，不允许直接 <c>new ChatClientAgent</c> 或调
    /// <c>IChatClient</c>。</para>
    /// </summary>
    public interface INeuron : IAsyncDisposable
    {
        /// <summary>神经元在 AgentInstance 内的稳定标识——与 BrainId 同名（如 "prefrontal-cortex" / "motor-cortex.native"）。</summary>
        string NeuronId { get; }

        /// <summary>引擎种别——供 Brain 层做能力体征判断。</summary>
        NeuronKind Kind { get; }

        /// <summary>
        /// 核心执行——投递 <see cref="BrainInvocation"/>，返回 <see cref="BrainOutcome"/>。
        /// 不感知调用者是哪个脑区（脑区职责 = Brain 层；神经元只负责跑 LLM）。
        /// </summary>
        Task<BrainOutcome> InvokeAsync(BrainInvocation invocation, CancellationToken ct);

        /// <summary>
        /// 暴露底层 <see cref="AIAgent"/> 引用（仅供 Channel 持引用打 SendAsync 用）。
        /// <see cref="MsaiNeuron"/> 返回真实 ChatClientAgent；<see cref="ExternalEngineNeuron"/>
        /// 返回 <c>null</c>（外部引擎自带 LLM，无 AIAgent 句柄）。
        /// </summary>
        AIAgent? UnderlyingAgent { get; }
    }
}
