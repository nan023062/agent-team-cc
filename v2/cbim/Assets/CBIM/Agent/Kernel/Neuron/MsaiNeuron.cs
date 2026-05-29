using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using CBIM.AgentSystem.Brain;
using CBIM.Memory;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

namespace CBIM.AgentSystem.Kernel.Neuron
{
    /// <summary>
    /// 标准 Msai 神经元——装配 <see cref="ChatClientAgent"/> + <see cref="FunctionInvokingChatClient"/>
    /// + AITool 集（StandardAITools + SynapseAITools）。
    ///
    /// <para>InvokeAsync 路径：把 <see cref="BrainInvocation.Intent"/> 包成 user
    /// <see cref="ChatMessage"/> 投给内部 ChatClientAgent.RunAsync，取 response.Text
    /// 作为 <see cref="BrainOutcome.Summary"/>。</para>
    /// </summary>
    public sealed class MsaiNeuron : INeuron
    {
        public string NeuronId { get; }
        public NeuronKind Kind => NeuronKind.Msai;
        public AIAgent? UnderlyingAgent => _agent;

        private readonly ChatClientAgent _agent;
        private readonly IChatClient _invokingChatClient;
        private readonly IMemoryService _memory;
        private int _disposed;

        /// <summary>
        /// 装配单元：
        /// <list type="number">
        ///   <item>用描述符的 <see cref="StandardBrainDescriptor.Capability"/>.Name / Identity / Soul 构造 <see cref="ChatClientAgentOptions"/>。</item>
        ///   <item>把 <paramref name="chatClient"/> 包成 <see cref="FunctionInvokingChatClient"/>——让 LLM 触发的 tool call 自动闭环。</item>
        ///   <item>把 <paramref name="aiTools"/>（已合并 StandardAITools + SynapseAITools）放进 <c>options.ChatOptions.Tools</c>。</item>
        ///   <item><c>new ChatClientAgent(invoking, options)</c> 拿到运行体。</item>
        /// </list>
        /// </summary>
        /// <param name="neuronId">神经元 Id（=BrainId）。不为空。</param>
        /// <param name="descriptor">标准脑区描述符——读 Soul / Capability 字段。</param>
        /// <param name="chatClient">底层 LLM 客户端。不为 null。</param>
        /// <param name="memory">共享 Memory 实例。不为 null。</param>
        /// <param name="aiTools">已合并的 AITool 集（StandardAITools + SynapseAITools）。不为 null（可空集）。</param>
        public MsaiNeuron(
            string neuronId,
            StandardBrainDescriptor descriptor,
            IChatClient chatClient,
            IMemoryService memory,
            IReadOnlyList<AITool> aiTools)
        {
            if (string.IsNullOrWhiteSpace(neuronId))
                throw new ArgumentException("MsaiNeuron.NeuronId 不能为空", nameof(neuronId));
            if (descriptor == null)
                throw new ArgumentNullException(nameof(descriptor));
            if (chatClient == null)
                throw new ArgumentNullException(nameof(chatClient));
            if (memory == null)
                throw new ArgumentNullException(nameof(memory));
            if (aiTools == null)
                throw new ArgumentNullException(nameof(aiTools));

            NeuronId = neuronId;
            _memory = memory;

            // 包 FunctionInvokingChatClient——让 LLM 返回 tool_call 时框架自动派发到 AIFunction 并回填结果。
            _invokingChatClient = new FunctionInvokingChatClient(chatClient);

            var options = new ChatClientAgentOptions
            {
                Name = descriptor.Capability.Name,
                Description = descriptor.Capability.Identity,
                Instructions = descriptor.Soul,
            };

            // aiTools 已是装配方按 StandardAITools + SynapseAITools 合并一次性传入；空集时 options.ChatOptions 留 null。
            if (aiTools.Count > 0)
            {
                var tools = new List<AITool>(aiTools.Count);
                foreach (var t in aiTools)
                {
                    if (t == null)
                        throw new ArgumentException("MsaiNeuron.aiTools 不允许 null 项。", nameof(aiTools));
                    tools.Add(t);
                }
                options.ChatOptions = new ChatOptions { Tools = tools };
            }

            _agent = new ChatClientAgent(_invokingChatClient, options);
        }

        /// <inheritdoc/>
        public async Task<BrainOutcome> InvokeAsync(BrainInvocation invocation, CancellationToken ct)
        {
            if (invocation == null)
                throw new ArgumentNullException(nameof(invocation));

            var message = new ChatMessage(ChatRole.User, invocation.Intent ?? string.Empty);
            var result = await _agent.RunAsync(message, cancellationToken: ct).ConfigureAwait(false);

            return new BrainOutcome(
                Summary: result.Text ?? string.Empty,
                StructuredOutput: null,
                SideEffects: Array.Empty<SideEffect>(),
                IsError: false,
                ErrorMessage: null);
        }

        /// <inheritdoc/>
        public async ValueTask DisposeAsync()
        {
            if (Interlocked.Exchange(ref _disposed, 1) != 0)
                return;

            // FunctionInvokingChatClient 实现了 IDisposable / IAsyncDisposable——按声明顺序释放。
            if (_invokingChatClient is IAsyncDisposable ad)
                await ad.DisposeAsync().ConfigureAwait(false);
            else if (_invokingChatClient is IDisposable d)
                d.Dispose();
        }
    }
}
