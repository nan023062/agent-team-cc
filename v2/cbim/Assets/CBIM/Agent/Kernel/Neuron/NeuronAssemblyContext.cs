using System;
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
    ///
    /// <para>类型形态：C# 8 兼容性铁律——本类型为 <c>sealed class</c> 而非 <c>record</c>
    /// （records 需要 C# 9 / IsExternalInit；Unity 2020.3 不可用）。值语义由构造期参数注入 +
    /// 只读属性表达；本上下文是装配期一次性结构，不需要 with-expression。</para>
    /// </summary>
    public sealed class NeuronAssemblyContext
    {
        /// <summary>底层 LLM 客户端（msai 路径必填；External 路径可为 null）。</summary>
        public IChatClient? ChatClient { get; }

        /// <summary>共享 Memory 实例。</summary>
        public IMemoryService Memory { get; }

        /// <summary>SystemTools / Skills / Mcp 派生 AITool 集（不含 __brain_call_*）。</summary>
        public IReadOnlyList<AITool> StandardAITools { get; }

        /// <summary>SynapseToolFactory 产 __brain_call_* AITool 集（仅主脑非空）。</summary>
        public IReadOnlyList<AITool> SynapseAITools { get; }

        /// <summary>外部引擎适配器（External 装配必填，其他传 null）。</summary>
        public IExternalEngineAdapter? ExternalAdapter { get; }

        /// <summary>
        /// 构造期仅做字段写入 + 非 null 校验（除 ChatClient / ExternalAdapter 按路径可空外）。
        /// 命名参数风格保留 record positional 写法的可读性。
        /// </summary>
        public NeuronAssemblyContext(
            IChatClient? ChatClient,
            IMemoryService Memory,
            IReadOnlyList<AITool> StandardAITools,
            IReadOnlyList<AITool> SynapseAITools,
            IExternalEngineAdapter? ExternalAdapter)
        {
            if (Memory == null)
                throw new ArgumentNullException(nameof(Memory));
            if (StandardAITools == null)
                throw new ArgumentNullException(nameof(StandardAITools));
            if (SynapseAITools == null)
                throw new ArgumentNullException(nameof(SynapseAITools));

            this.ChatClient = ChatClient;
            this.Memory = Memory;
            this.StandardAITools = StandardAITools;
            this.SynapseAITools = SynapseAITools;
            this.ExternalAdapter = ExternalAdapter;
        }
    }
}
