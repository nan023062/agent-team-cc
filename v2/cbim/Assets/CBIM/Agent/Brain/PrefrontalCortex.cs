using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;
using CBIM.Memory;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

namespace CBIM.AgentSystem.Brain
{
    /// <summary>
    /// PrefrontalCortex（前额叶皮层）—— 主脑 / 调度中枢。
    /// 每个 AgentInstance 有且仅有 1 个；Channel.SendAsync 的实际投递目标。
    ///
    /// <para>「主脑唯一通路」铁律的物理护栏：</para>
    /// <list type="bullet">
    ///   <item><b>sealed</b>——不存在「External 主脑」的语法可能。</item>
    ///   <item><see cref="BrainBase.PrefrontalCallback"/> 永远为 <c>null</c>——自己不回报自己。</item>
    ///   <item>调度仅通过 <c>__brain_call_*</c> AIFunction 下发——其他脑区互不直调。</item>
    /// </list>
    ///
    /// <para>装配机制：构造期为 <see cref="CallableBrains"/> 中每个子脑区生成一个
    /// <c>__brain_call_&lt;sanitized-id&gt;</c> AIFunction，把 base.Agent 重建为带这些
    /// Tools 的 ChatClientAgent。msai 的 ChatClientAgent 不可变——基类装配产出的第一份
    /// Agent 实例会被丢弃，仅本构造期发生一次。</para>
    /// </summary>
    public sealed class PrefrontalCortex : BrainBase
    {
        public const string DefaultBrainId = "prefrontal-cortex";

        /// <summary>装配期注入的可调度子脑区清单——不含 PrefrontalCortex 自身。</summary>
        public IReadOnlyList<BrainBase> CallableBrains { get; }

        /// <summary>结果合并策略——init-only，仅装配方可设置。</summary>
        public PrefrontalAggregationStrategy Aggregation { get; init; } = PrefrontalAggregationStrategy.SummarizeBeforeReturn;

        public PrefrontalCortex(
            StandardBrainDescriptor descriptor,
            IMemoryService memory,
            IChatClient chatClient,
            IReadOnlyList<BrainBase> callableBrains)
            : base(descriptor?.BrainId ?? throw new ArgumentNullException(nameof(descriptor)),
                   descriptor,
                   memory,
                   chatClient,
                   callback: null)  // 「主脑回调恒为 null」铁律
        {
            // task-1 BrainBase 接受 chatClient 后直接装配出 base.Agent；本构造体接下来
            // 会用 __brain_call_* 工具集重建 Agent，那份首装实例会被替换掉。
            if (chatClient == null)
                throw new ArgumentNullException(nameof(chatClient));
            if (callableBrains == null)
                throw new ArgumentNullException(nameof(callableBrains));

            // ── 1. 描述符校验（task-1 留下的下游传递：descriptor.EnsureInvariants 是 public，
            //       本 task-2 在构造期就调用以拦截上游传入坏 descriptor，不依赖 BrainConfig）
            if (descriptor.Kind != StandardBrainKind.PrefrontalCortex)
                throw new InvalidOperationException(
                    $"PrefrontalCortex 要求 descriptor.Kind=PrefrontalCortex（实际: {descriptor.Kind}）。");
            if (!descriptor.IsPrefrontal)
                throw new InvalidOperationException(
                    "PrefrontalCortex 要求 descriptor.IsPrefrontal=true——「主脑唯一」铁律。");
            descriptor.EnsureInvariants();

            // ── 2. CallableBrains 浅复制 + 自指 / 重复 BrainId 校验
            var copy = new List<BrainBase>(callableBrains.Count);
            var seen = new HashSet<string>(StringComparer.Ordinal);
            foreach (var b in callableBrains)
            {
                if (b == null)
                    throw new ArgumentException("CallableBrains 不允许 null 项。", nameof(callableBrains));
                if (ReferenceEquals(b, this))
                    throw new InvalidOperationException(
                        "PrefrontalCortex 不允许自己调自己——CallableBrains 不能含主脑自身。");
                if (b is PrefrontalCortex)
                    throw new InvalidOperationException(
                        $"CallableBrains 中不允许出现 PrefrontalCortex 类型脑区（'{b.BrainId}'）——「主脑唯一」铁律。");
                if (!seen.Add(b.BrainId))
                    throw new InvalidOperationException(
                        $"CallableBrains 中 BrainId 重复: '{b.BrainId}'。");
                copy.Add(b);
            }
            CallableBrains = copy;

            // ── 3. 装配 __brain_call_* AIFunction 列表 + 重建 base.Agent
            var tools = new List<AITool>(copy.Count);
            foreach (var callable in copy)
            {
                tools.Add(BuildBrainCallFunction(callable));
            }

            var opts = new ChatClientAgentOptions
            {
                Name = descriptor.Capability.Name,
                Description = descriptor.Capability.Identity,
                Instructions = descriptor.Soul,
                ChatOptions = new ChatOptions { Tools = tools },
            };

            Agent = chatClient.AsAIAgent(opts);  // 替换基类首装产物
        }

        /// <summary>
        /// 为单个子脑区构造一个 <c>__brain_call_&lt;sanitized-id&gt;</c> AIFunction。
        ///
        /// <para>命名规则：BrainId 中 <c>.</c> / <c>-</c> 替换为 <c>_</c>，得到符合 LLM 函数
        /// 名约束的 identifier。例：<c>motor-cortex.claude-code</c> → <c>__brain_call_motor_cortex_claude_code</c>。</para>
        ///
        /// <para>用 <see cref="BrainCallTrampoline"/> 实例的方法而非 lambda，是为了让
        /// <see cref="AIFunctionFactory.Create(System.Delegate,string?,string?,System.Text.Json.JsonSerializerOptions?)"/>
        /// 拿到带名字 + <see cref="DescriptionAttribute"/> 的参数（lambda 的参数名在反射后会被擦成
        /// arg0/arg1/…，无法产出可用的 JSON schema 描述）。</para>
        /// </summary>
        private static AIFunction BuildBrainCallFunction(BrainBase callable)
        {
            string sanitized = callable.BrainId.Replace('.', '_').Replace('-', '_');
            string fnName = "__brain_call_" + sanitized;
            string description =
                $"Dispatch sub-task to brain '{callable.BrainId}'. " +
                $"Use when the user request is best handled by this sub-region.";

            var trampoline = new BrainCallTrampoline(callable);
            // 走 MethodInfo 重载——避开 Func<> cast 在 nullable-annotated 参数上的签名匹配歧义，
            // 同时让 AIFunctionFactory 直接读到原始 MethodInfo 的参数名（intent /
            // structured_input / context）+ [Description] attribute 用于 JSON schema。
            var methodInfo = typeof(BrainCallTrampoline).GetMethod(
                nameof(BrainCallTrampoline.InvokeAsync),
                BindingFlags.Instance | BindingFlags.Public);
            if (methodInfo == null)
                throw new InvalidOperationException(
                    "未找到 BrainCallTrampoline.InvokeAsync——内部不变量违反。");

            return AIFunctionFactory.Create(methodInfo, target: trampoline, name: fnName, description: description);
        }

        /// <inheritdoc/>
        public override ValueTask DisposeAsync() => default;

        /// <summary>
        /// 把对一个具体子脑区的调用包成「带参数名 + Description」的实例方法，
        /// 供 <see cref="AIFunctionFactory"/> 产出含正确 JSON schema 的 AIFunction。
        /// 每个子脑区一份实例——构造期捕获 callable 引用。
        /// </summary>
        private sealed class BrainCallTrampoline
        {
            private readonly BrainBase _callable;

            public BrainCallTrampoline(BrainBase callable)
            {
                _callable = callable;
            }

            public async Task<string> InvokeAsync(
                [Description("Natural-language task description for the sub-region brain.")] string intent,
                [Description("Optional JSON-serialized structured payload; pass null when not needed.")] string? structured_input,
                [Description("Optional situational hint passed as Context['ctx']; pass null when not needed.")] string? context,
                CancellationToken cancellationToken)
            {
                var ctxDict = new Dictionary<string, object>(StringComparer.Ordinal);
                if (!string.IsNullOrEmpty(context))
                    ctxDict["ctx"] = context!;

                var invocation = new BrainInvocation(
                    CorrelationId: Guid.NewGuid().ToString("N"),
                    Intent: intent ?? string.Empty,
                    StructuredInput: structured_input,
                    Context: ctxDict);

                var outcome = await _callable.InvokeAsync(invocation, cancellationToken).ConfigureAwait(false);

                if (outcome.IsError)
                    return $"[brain '{_callable.BrainId}' error] {outcome.ErrorMessage ?? "unknown error"}";

                return outcome.Summary ?? string.Empty;
            }
        }
    }
}
