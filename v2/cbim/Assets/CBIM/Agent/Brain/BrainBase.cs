using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using CBIM.Memory;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

namespace CBIM.AgentSystem.Brain
{
    /// <summary>
    /// 脑区契约公共基类。
    ///
    /// <para>本轮重要变动：基类直接持 msai 装配的 ChatClientAgent —— 所有具体脑区天生
    /// 具备 LLM 思维链 + Function Invoking 闭环。<see cref="ExternalMotorCortex"/>
    /// 是唯一例外（外部引擎自带 LLM，<see cref="Agent"/> 字段语义重定义为 null）。</para>
    ///
    /// <para>「同一具身一份记忆」铁律的物理落地：<see cref="Memory"/> 由 AgentInstance 在
    /// 装配期注入，所有脑区共享同一 <see cref="IMemoryService"/> 实例。</para>
    ///
    /// <para>「主脑唯一通路」铁律的物理护栏：<see cref="PrefrontalCallback"/> 是子脑区
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
        /// msai 运行体——基类装配。
        /// <see cref="ExternalMotorCortex"/> 路径下为 <c>null</c>（外部引擎自带 LLM）。
        /// 字段为 <c>protected set</c>，仅允许子类在自身构造路径内重定义。
        /// </summary>
        public AIAgent? Agent { get; protected set; }

        /// <summary>
        /// 主脑回调——子脑区通过该回调向 PrefrontalCortex 汇报结果。
        /// 主脑自身恒为 <c>null</c>（自己不回报自己）。
        /// </summary>
        protected IPrefrontalCallback? PrefrontalCallback { get; }

        /// <summary>
        /// 构造期完成三件事：
        ///   1. 字段写入与必要校验（BrainId / Memory 非空）；
        ///   2. 根据描述符子类分派 msai 装配——<see cref="StandardBrainDescriptor"/> 路径用
        ///      <see cref="ChatClientAgentExtensions.AsAIAgent(IChatClient,ChatClientAgentOptions)"/>
        ///      构造 <see cref="Microsoft.Agents.AI.AIAgent"/>；
        ///   3. <see cref="ExternalMotorCortexDescriptor"/> 路径下 <see cref="Agent"/> 保持 <c>null</c>
        ///      （子类自决——典型如 <c>ExternalMotorCortex</c> 走 Adapter 路径）。
        /// </summary>
        /// <param name="brainId">脑区唯一 Id。不为空白。</param>
        /// <param name="descriptor">脑区描述符；类型决定装配分支。</param>
        /// <param name="memory">共享 Memory 实例。不为 null。</param>
        /// <param name="chatClient">底层 LLM 客户端。<see cref="StandardBrainDescriptor"/> 路径下不为 null；<see cref="ExternalMotorCortexDescriptor"/> 路径下可为 null。</param>
        /// <param name="callback">主脑回调；主脑自身传 <c>null</c>，其他脑区由 AgentInstance 装配期注入。</param>
        protected BrainBase(
            string brainId,
            BrainDescriptor descriptor,
            IMemoryService memory,
            IChatClient? chatClient,
            IPrefrontalCallback? callback)
        {
            if (string.IsNullOrWhiteSpace(brainId))
                throw new ArgumentException("BrainBase.BrainId 不能为空", nameof(brainId));
            if (descriptor == null)
                throw new ArgumentNullException(nameof(descriptor));
            if (memory == null)
                throw new ArgumentNullException(
                    nameof(memory),
                    "BrainBase.Memory 不允许 null——「同一具身一份记忆」铁律由构造期强制。");

            BrainId = brainId;
            Memory = memory;
            PrefrontalCallback = callback;

            if (descriptor is StandardBrainDescriptor std)
            {
                if (chatClient == null)
                    throw new ArgumentNullException(
                        nameof(chatClient),
                        "StandardBrainDescriptor 路径下 IChatClient 不能为 null——基类需用它装配 msai AIAgent。");

                var opts = new ChatClientAgentOptions
                {
                    Name = std.Capability.Name,
                    Description = std.Capability.Identity,
                    Instructions = std.Soul,
                };

                Agent = chatClient.AsAIAgent(opts);
            }
            else if (descriptor is ExternalMotorCortexDescriptor)
            {
                // 外部引擎自带 LLM——Agent 保持 null；子类（ExternalMotorCortex）走 Adapter 路径。
                Agent = null;
            }
            else
            {
                throw new InvalidOperationException(
                    $"未识别的 BrainDescriptor 子类: {descriptor.GetType().FullName}");
            }
        }

        /// <summary>
        /// 投递子任务到本脑区。
        ///
        /// 默认实现：把 <see cref="BrainInvocation.Intent"/> 包成一条 user
        /// <see cref="ChatMessage"/> 投给 <see cref="Agent"/>.RunAsync，取 response.Text 作为
        /// <see cref="BrainOutcome.Summary"/>，SideEffects 返回空列表。
        ///
        /// <see cref="ExternalMotorCortex"/> 等子类重写为「Adapter.SubmitAsync + AwaitResultAsync」路径。
        /// </summary>
        public virtual async Task<BrainOutcome> InvokeAsync(BrainInvocation invocation, CancellationToken ct)
        {
            if (invocation == null)
                throw new ArgumentNullException(nameof(invocation));
            if (Agent == null)
                throw new InvalidOperationException(
                    $"BrainBase.InvokeAsync 默认实现要求 Agent 非 null（脑区 '{BrainId}'）；"
                    + "ExternalMotorCortex 等无 Agent 的脑区必须重写 InvokeAsync。");

            var message = new ChatMessage(ChatRole.User, invocation.Intent);
            var response = await Agent.RunAsync(message, cancellationToken: ct).ConfigureAwait(false);

            return new BrainOutcome(
                Summary: response.Text ?? string.Empty,
                StructuredOutput: null,
                SideEffects: Array.Empty<SideEffect>(),
                IsError: false,
                ErrorMessage: null);
        }

        /// <summary>
        /// 释放本脑区占用的资源。
        /// AgentInstance 的释放顺序保证调用：MotorCortex → 其他脑区 → Prefrontal。
        /// 实现需做到多次调用幂等。
        /// </summary>
        public abstract ValueTask DisposeAsync();
    }
}
