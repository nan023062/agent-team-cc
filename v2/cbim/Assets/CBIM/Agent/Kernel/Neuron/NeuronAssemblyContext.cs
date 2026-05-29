using System.Collections.Generic;
using CBIM.AgentSystem.Brain;
using CBIM.Memory;
using Microsoft.Extensions.AI;

namespace CBIM.AgentSystem.Kernel.Neuron
{
    /// <summary>
    /// 神经元装配上下文——<c>AgentSystem.OpenInstance</c> 准备好后传给
    /// <see cref="NeuronFactory.Create"/>。
    ///
    /// <para>字段消费规则：</para>
    /// <list type="bullet">
    ///   <item><see cref="ChatClient"/>——MsaiNeuron 装配走它包 FunctionInvokingChatClient + ChatClientAgent；
    ///         ExternalEngineNeuron 不消费。</item>
    ///   <item><see cref="Memory"/>——两路径均注入到神经元（供日后 Memory 触发用，本轮 InvokeAsync 不直接读）。</item>
    ///   <item><see cref="StandardAITools"/>——SystemTools / Skills / Mcp 派生（不含 __brain_call_*）。
    ///         仅 MsaiNeuron 消费。</item>
    ///   <item><see cref="SynapseAITools"/>——SynapseToolFactory 产 __brain_call_* AITool（仅主脑非空，
    ///         其他脑区传 <see cref="System.Array.Empty{T}"/>）。仅 MsaiNeuron 消费。</item>
    ///   <item><see cref="ExternalAdapter"/>——External 装配时必填；其他装配传 <c>null</c>。</item>
    /// </list>
    /// </summary>
    /// <param name="ChatClient">底层 LLM 客户端（msai 路径必填；External 路径可为 null）。</param>
    /// <param name="Memory">共享 Memory 实例。</param>
    /// <param name="StandardAITools">SystemTools / Skills / Mcp 派生 AITool 集（不含 __brain_call_*）。</param>
    /// <param name="SynapseAITools">SynapseToolFactory 产 __brain_call_* AITool 集（仅主脑非空）。</param>
    /// <param name="ExternalAdapter">外部引擎适配器（External 装配必填，其他传 null）。</param>
    public sealed record NeuronAssemblyContext(
        IChatClient ChatClient,
        IMemoryService Memory,
        IReadOnlyList<AITool> StandardAITools,
        IReadOnlyList<AITool> SynapseAITools,
        IExternalEngineAdapter? ExternalAdapter);
}
