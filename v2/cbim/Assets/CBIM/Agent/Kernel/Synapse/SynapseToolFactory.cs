using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;
using CBIM.AgentSystem.Brain;
using Microsoft.Extensions.AI;

namespace CBIM.AgentSystem.Kernel.Synapse
{
    /// <summary>
    /// 突触工具工厂——为主脑装配「<c>__brain_call_*</c>」AITool 集，承载跨脑区派发机制。
    ///
    /// <para>本类是 Brain → 其它脑区调度的唯一出口（K3 铁律）。Brain/PrefrontalCortex
    /// 不再内嵌函数生成逻辑——只调 <see cref="Build"/> 拿到 <c>IReadOnlyList&lt;AITool&gt;</c>
    /// 后挂到主脑 Neuron 装配上下文。</para>
    ///
    /// <para>K1 铁律：本工厂不感知任何具体脑区类型——只读 <c>BrainBase.BrainId</c> 派生函数名，
    /// 不读描述符中的语义字段（如 <c>StandardBrainKind</c>）。</para>
    ///
    /// <para>K4 铁律：不引用 <c>CBIM.AgentSystem.Kernel.Neuron</c>——Synapse ⊥ Neuron。</para>
    /// </summary>
    public static class SynapseToolFactory
    {
        /// <summary>
        /// 产出 <c>__brain_call_*</c> AITool 集。
        ///
        /// <para>函数命名规则：<c>"__brain_call_" + BrainId.Replace('.', '_').Replace('-', '_')</c>。
        /// 例：<c>motor-cortex.claude-code → __brain_call_motor_cortex_claude_code</c>。
        /// 这种命名是 LLM 可读的——函数名本身就是描述。</para>
        ///
        /// <para>参数 schema：<c>{ intent: string (required), structured: string? (optional, JSON payload),
        /// context: string? (optional, situational hint) }</c>。<br/>
        /// 实现注记：DNA 契约写的是 <c>structured: object / context: object</c>，但 msai
        /// <c>AIFunctionFactory</c> 反射出的 JSON Schema 对 <c>object?</c> 类型只能生成空 schema，
        /// LLM 难以使用——故工程上选择 <c>string?</c>（调用方传 JSON 文本）。这一选择不削弱
        /// 契约的语义：传 JSON 文本与传任意对象等价（皆为「不透明结构化载荷」）。</para>
        ///
        /// <para>主脑不会被工厂自动排除——「Callable 过滤」是装配方（AgentSystem.OpenInstance）
        /// 的责任。工厂只产工具，不做策略。</para>
        /// </summary>
        /// <param name="callableBrains">可调脑区清单。允许空列表（主脑无可调子脑区时合法）。</param>
        /// <returns>AITool 集合——按入参顺序生成，供主脑 Neuron 装配为 <c>ChatOptions.Tools</c>。</returns>
        public static IReadOnlyList<AITool> Build(IReadOnlyList<BrainBase> callableBrains)
        {
            if (callableBrains == null)
                throw new ArgumentNullException(nameof(callableBrains));

            var tools = new List<AITool>(callableBrains.Count);
            var seen = new HashSet<string>(StringComparer.Ordinal);

            foreach (var callable in callableBrains)
            {
                if (callable == null)
                    throw new ArgumentException("callableBrains 不允许 null 项。", nameof(callableBrains));
                if (!seen.Add(callable.BrainId))
                    throw new InvalidOperationException(
                        $"callableBrains 中 BrainId 重复: '{callable.BrainId}'——「BrainId 唯一」铁律违反。");

                tools.Add(BuildBrainCallFunction(callable));
            }

            return tools;
        }

        /// <summary>
        /// 为单个子脑区构造一个 <c>__brain_call_&lt;sanitized-id&gt;</c> AIFunction。
        ///
        /// <para>用 <see cref="BrainCallTrampoline"/> 实例方法而非 lambda，是为了让
        /// <see cref="AIFunctionFactory.Create(MethodInfo, object?, string?, string?, System.Text.Json.JsonSerializerOptions?)"/>
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
            var methodInfo = typeof(BrainCallTrampoline).GetMethod(
                nameof(BrainCallTrampoline.InvokeAsync),
                BindingFlags.Instance | BindingFlags.Public);
            if (methodInfo == null)
                throw new InvalidOperationException(
                    "未找到 BrainCallTrampoline.InvokeAsync——内部不变量违反。");

            return AIFunctionFactory.Create(methodInfo, target: trampoline, name: fnName, description: description);
        }

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
                [Description("Optional JSON-serialized structured payload; pass null when not needed.")] string? structured,
                [Description("Optional situational hint passed as Context['ctx']; pass null when not needed.")] string? context,
                CancellationToken cancellationToken)
            {
                var ctxDict = new Dictionary<string, object>(StringComparer.Ordinal);
                if (!string.IsNullOrEmpty(context))
                    ctxDict["ctx"] = context!;

                var invocation = new BrainInvocation(
                    CorrelationId: Guid.NewGuid().ToString("N"),
                    Intent: intent ?? string.Empty,
                    StructuredInput: structured,
                    Context: ctxDict);

                var outcome = await _callable.InvokeAsync(invocation, cancellationToken).ConfigureAwait(false);

                if (outcome.IsError)
                    return $"[brain '{_callable.BrainId}' error] {outcome.ErrorMessage ?? "unknown error"}";

                return outcome.Summary ?? string.Empty;
            }
        }
    }
}
