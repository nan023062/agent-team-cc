using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Reflection;
using System.Text.RegularExpressions;
using CBIM.AgentSystem.Brain;
using Microsoft.Extensions.AI;

namespace CBIM.AgentSystem.Kernel.Synapse.Compiler
{
    /// <summary>
    /// 编译器工具工厂——为主脑 Neuron 产出 <c>__circuit_*</c> IR 构建 AITool 集（6 个）：
    /// <list type="bullet">
    ///   <item><c>__circuit_start(sourceRequest)</c>——LLM 显式宣告开始编译；幂等校验。</item>
    ///   <item><c>__circuit_add_call_brain(label, targetBrainId, intent, structuredInputJson?)</c>——
    ///         追加 CallBrain 节点；校验 <c>targetBrainId</c> 必须在 <paramref name="callableBrains"/> 集合内。</item>
    ///   <item><c>__circuit_add_branch(label, conditionExpression)</c>——追加 Branch 节点；
    ///         极简正则校验 <c>&lt;token&gt; contains|equals "&lt;value&gt;"</c>。</item>
    ///   <item><c>__circuit_add_return(label, summaryTemplate)</c>——追加 Return 节点。</item>
    ///   <item><c>__circuit_add_edge(fromNodeId, toNodeId, branchLabel?)</c>——追加边。</item>
    ///   <item><c>__circuit_commit()</c>——冻结成 <see cref="NeuralCircuit"/>。</item>
    /// </list>
    ///
    /// <para>K3 铁律：所有跨脑区机制只走 Synapse 出口；本工厂与 <c>SynapseToolFactory</c> 并列，
    /// 构成主脑「能做的事」工具表面。C2 铁律：本工厂产物只挂主脑——由调用方
    /// <c>PrefrontalCortex</c>（T14）在装配期注入 <c>NeuronAssemblyContext.StandardAITools</c>。</para>
    ///
    /// <para>K6 铁律：本工厂不引用 <c>Orchestrator</c> 命名空间。</para>
    ///
    /// <para>异常映射（C3 铁律：校验失败必回退）：</para>
    /// <list type="bullet">
    ///   <item>Builder 即时校验抛 <see cref="ArgumentException"/> / <see cref="InvalidOperationException"/>
    ///         → handler catch 后重抛 <see cref="InvalidOperationException"/>，
    ///         FunctionInvokingChatClient 把 message 反给 LLM 让其重调。</item>
    ///   <item>Builder.Commit 整体校验抛 <see cref="CircuitCompilationException"/>
    ///         → handler catch 后重抛 <see cref="InvalidOperationException"/>（msg 保留 Reason），
    ///         FunctionInvokingChatClient 同样反给 LLM。</item>
    /// </list>
    /// </summary>
    public static class CompilerToolFactory
    {
        /// <summary>
        /// 产出 6 个 <c>__circuit_*</c> AITool。
        ///
        /// <para>返回顺序：<c>[start, add_call_brain, add_branch, add_return, add_edge, commit]</c>——
        /// 与编译流程同序，便于 LLM 按工具描述自然推断使用顺序。</para>
        /// </summary>
        /// <param name="builderProvider">取当前 per-invocation builder 的委托。装配期闭包；
        /// 每次工具调用都重新求值（典型：PrefrontalCortex._activeBuilder 字段读取器）。
        /// 不为 null；委托返 null 时 handler 抛 <see cref="InvalidOperationException"/>
        /// （= 工具被在 InvokeAsync 窗口外调用，应视为契约违反）。</param>
        /// <param name="callableBrains">主脑可调子脑区清单；仅用于
        /// <c>__circuit_add_call_brain</c> 校验 <c>targetBrainId</c> 合法。允许空列表
        /// （主脑无可调子脑区时合法），但 LLM 这种场景下也不应调 <c>add_call_brain</c>。不为 null。</param>
        /// <returns>AITool 集合（6 个）。</returns>
        public static IReadOnlyList<AITool> Build(
            Func<NeuralCircuitBuilder> builderProvider,
            IReadOnlyList<BrainBase> callableBrains)
        {
            if (builderProvider == null)
                throw new ArgumentNullException(nameof(builderProvider));
            if (callableBrains == null)
                throw new ArgumentNullException(nameof(callableBrains));

            // 预先构建 BrainId 集合用于校验——避免 handler 每次调用都遍历 list。
            var callableBrainIds = new HashSet<string>(StringComparer.Ordinal);
            var callableBrainIdsOrdered = new List<string>(callableBrains.Count);
            foreach (var brain in callableBrains)
            {
                if (brain == null)
                    throw new ArgumentException("callableBrains 不允许 null 项。", nameof(callableBrains));
                if (!callableBrainIds.Add(brain.BrainId))
                    throw new InvalidOperationException(
                        $"callableBrains 中 BrainId 重复: '{brain.BrainId}'——「BrainId 唯一」铁律违反。");
                callableBrainIdsOrdered.Add(brain.BrainId);
            }

            var tools = new List<AITool>(6)
            {
                BuildStartTool(builderProvider),
                BuildAddCallBrainTool(builderProvider, callableBrainIds, callableBrainIdsOrdered),
                BuildAddBranchTool(builderProvider),
                BuildAddReturnTool(builderProvider),
                BuildAddEdgeTool(builderProvider),
                BuildCommitTool(builderProvider),
            };
            return tools;
        }

        /// <summary>
        /// 取当前 builder 或抛——所有 trampoline 的统一入口闸门。
        /// 委托返 null 意味着「LLM 在 InvokeAsync 窗口外调了 __circuit_*」，
        /// 这违反 T14 设计（builder per-invocation），抛 <see cref="InvalidOperationException"/>
        /// 由 handler 转 InvocationException 回 LLM（与 Builder 即时校验失败同语义）。
        /// </summary>
        private static NeuralCircuitBuilder ResolveBuilder(Func<NeuralCircuitBuilder> builderProvider)
        {
            var builder = builderProvider();
            if (builder == null)
                throw new InvalidOperationException(
                    "No active NeuralCircuitBuilder——__circuit_* 工具仅在 PrefrontalCortex.InvokeAsync 窗口内有效。");
            return builder;
        }

        // -------- 工具构造（每个走自己的 trampoline 实例方法以保留参数名 + Description）--------

        private static AIFunction BuildStartTool(Func<NeuralCircuitBuilder> builderProvider)
        {
            var trampoline = new StartTrampoline(builderProvider);
            var method = ResolveMethod(typeof(StartTrampoline), nameof(StartTrampoline.Invoke));
            return AIFunctionFactory.Create(
                method,
                target: trampoline,
                name: "__circuit_start",
                description:
                    "Declare the beginning of neural-circuit compilation. " +
                    "Call this once before any __circuit_add_* tool. " +
                    "Idempotency: must NOT be called after __circuit_commit succeeded.");
        }

        private static AIFunction BuildAddCallBrainTool(
            Func<NeuralCircuitBuilder> builderProvider,
            HashSet<string> callableBrainIds,
            IReadOnlyList<string> callableBrainIdsOrdered)
        {
            var trampoline = new AddCallBrainTrampoline(builderProvider, callableBrainIds, callableBrainIdsOrdered);
            var method = ResolveMethod(typeof(AddCallBrainTrampoline), nameof(AddCallBrainTrampoline.Invoke));
            return AIFunctionFactory.Create(
                method,
                target: trampoline,
                name: "__circuit_add_call_brain",
                description:
                    "Declare a step that dispatches user intent to a specific brain. " +
                    "Use after __circuit_start; can be chained. " +
                    "Returns the new node id (e.g. 'n01') for later __circuit_add_edge wiring.");
        }

        private static AIFunction BuildAddBranchTool(Func<NeuralCircuitBuilder> builderProvider)
        {
            var trampoline = new AddBranchTrampoline(builderProvider);
            var method = ResolveMethod(typeof(AddBranchTrampoline), nameof(AddBranchTrampoline.Invoke));
            return AIFunctionFactory.Create(
                method,
                target: trampoline,
                name: "__circuit_add_branch",
                description:
                    "Declare a conditional branch node. " +
                    "conditionExpression must match: '<token> contains \"<value>\"' OR '<token> equals \"<value>\"' " +
                    "where <token> is 'previous.summary' or 'node_<id>.summary'. " +
                    "Returns the new node id; wire >=2 outgoing edges via __circuit_add_edge with branchLabel " +
                    "'true' or 'false'.");
        }

        private static AIFunction BuildAddReturnTool(Func<NeuralCircuitBuilder> builderProvider)
        {
            var trampoline = new AddReturnTrampoline(builderProvider);
            var method = ResolveMethod(typeof(AddReturnTrampoline), nameof(AddReturnTrampoline.Invoke));
            return AIFunctionFactory.Create(
                method,
                target: trampoline,
                name: "__circuit_add_return",
                description:
                    "Declare a terminal node that yields the final summary back to the main brain. " +
                    "summaryTemplate may contain placeholders such as '{previous.summary}' or '{node_n03.summary}' " +
                    "that Orchestrator resolves at execution time. " +
                    "At least one Return node is required for __circuit_commit to succeed.");
        }

        private static AIFunction BuildAddEdgeTool(Func<NeuralCircuitBuilder> builderProvider)
        {
            var trampoline = new AddEdgeTrampoline(builderProvider);
            var method = ResolveMethod(typeof(AddEdgeTrampoline), nameof(AddEdgeTrampoline.Invoke));
            return AIFunctionFactory.Create(
                method,
                target: trampoline,
                name: "__circuit_add_edge",
                description:
                    "Connect two declared nodes. " +
                    "branchLabel MUST be provided when fromNodeId is a Branch node (one edge per outcome), " +
                    "and MUST be null otherwise. " +
                    "Returns 'ok' on success.");
        }

        private static AIFunction BuildCommitTool(Func<NeuralCircuitBuilder> builderProvider)
        {
            var trampoline = new CommitTrampoline(builderProvider);
            var method = ResolveMethod(typeof(CommitTrampoline), nameof(CommitTrampoline.Invoke));
            return AIFunctionFactory.Create(
                method,
                target: trampoline,
                name: "__circuit_commit",
                description:
                    "Freeze the in-progress graph into an immutable NeuralCircuit. " +
                    "Whole-graph validation runs: >=1 ReturnNode, reachability from start, no cycles, " +
                    "Branch out-degree >=2 with non-empty branchLabel on each outgoing edge. " +
                    "On failure the LLM must clarify with the user instead of forcing execution.");
        }

        private static MethodInfo ResolveMethod(Type trampolineType, string methodName)
        {
            var method = trampolineType.GetMethod(methodName, BindingFlags.Instance | BindingFlags.Public);
            if (method == null)
                throw new InvalidOperationException(
                    $"未找到 {trampolineType.Name}.{methodName}——内部不变量违反。");
            return method;
        }

        // -------- Trampolines（每个工具一份，构造期捕获 builder/校验集闭包；参数名 + Description
        //          通过实例方法签名暴露给 AIFunctionFactory 反射，避免 lambda 参数名被擦成 arg0/arg1）--------

        private sealed class StartTrampoline
        {
            private readonly Func<NeuralCircuitBuilder> _builderProvider;

            public StartTrampoline(Func<NeuralCircuitBuilder> builderProvider) { _builderProvider = builderProvider; }

            public string Invoke(
                [Description("The original user natural-language request that motivates this circuit. " +
                             "Echoed back for LLM bookkeeping; the value is already captured by the builder ctor.")]
                string sourceRequest)
            {
                var builder = ResolveBuilder(_builderProvider);
                if (builder.Compiled != null)
                    throw new InvalidOperationException(
                        "__circuit_start 不可在 __circuit_commit 成功后再次调用——Builder 已冻结。");
                // sourceRequest 在 builder ctor 已注入；此处仅作 LLM 显式开场动作 + 幂等护栏。
                return "started";
            }
        }

        private sealed class AddCallBrainTrampoline
        {
            private readonly Func<NeuralCircuitBuilder> _builderProvider;
            private readonly HashSet<string> _callableBrainIds;
            private readonly IReadOnlyList<string> _callableBrainIdsOrdered;

            public AddCallBrainTrampoline(
                Func<NeuralCircuitBuilder> builderProvider,
                HashSet<string> callableBrainIds,
                IReadOnlyList<string> callableBrainIdsOrdered)
            {
                _builderProvider = builderProvider;
                _callableBrainIds = callableBrainIds;
                _callableBrainIdsOrdered = callableBrainIdsOrdered;
            }

            public string Invoke(
                [Description("Short human-readable label for this step; surfaces in audit / visualization.")]
                string label,
                [Description("Target brain id; MUST be one of the callable brains exposed to the main brain.")]
                string targetBrainId,
                [Description("Natural-language task description for the target brain.")]
                string intent,
                [Description("Optional JSON-serialized structured payload; pass null when not needed.")]
                string? structuredInputJson)
            {
                var builder = ResolveBuilder(_builderProvider);
                if (!_callableBrainIds.Contains(targetBrainId ?? string.Empty))
                {
                    var available = _callableBrainIdsOrdered.Count == 0
                        ? "<empty>"
                        : string.Join(", ", _callableBrainIdsOrdered);
                    throw new InvalidOperationException(
                        $"targetBrainId '{targetBrainId}' 不在可调脑区集合; 可选: {available}");
                }
                try
                {
                    return builder.AddCallBrain(label, targetBrainId, intent, structuredInputJson);
                }
                catch (ArgumentException ex)
                {
                    throw new InvalidOperationException(ex.Message);
                }
                catch (InvalidOperationException)
                {
                    throw;
                }
            }
        }

        // 极简条件表达式校验：'<token> contains "<value>"' 或 '<token> equals "<value>"'。
        // <token> 形如 'previous.summary' 或 'node_n03.summary'。
        // 与 T11 ConditionEvaluator 的可解析子集一致；rhs 必为双引号字符串字面量。
        private static readonly Regex s_conditionRegex = new Regex(
            "^\\s*(previous\\.summary|node_n\\d{2}\\.summary)\\s+(contains|equals)\\s+\"[^\"]*\"\\s*$",
            RegexOptions.Compiled);

        private sealed class AddBranchTrampoline
        {
            private readonly Func<NeuralCircuitBuilder> _builderProvider;

            public AddBranchTrampoline(Func<NeuralCircuitBuilder> builderProvider) { _builderProvider = builderProvider; }

            public string Invoke(
                [Description("Short human-readable label for this branch node; surfaces in audit / visualization.")]
                string label,
                [Description("Condition expression. Must be: '<token> contains \"<value>\"' OR " +
                             "'<token> equals \"<value>\"' where <token> is 'previous.summary' or 'node_<id>.summary'.")]
                string conditionExpression)
            {
                var builder = ResolveBuilder(_builderProvider);
                if (string.IsNullOrWhiteSpace(conditionExpression) ||
                    !s_conditionRegex.IsMatch(conditionExpression))
                {
                    throw new InvalidOperationException(
                        "conditionExpression 形式不合法; 仅支持 '<token> contains \"<value>\"' 或 " +
                        "'<token> equals \"<value>\"', 其中 <token> 为 'previous.summary' 或 'node_n<NN>.summary'。" +
                        $"实际收到: '{conditionExpression}'");
                }
                try
                {
                    return builder.AddBranch(label, conditionExpression);
                }
                catch (ArgumentException ex)
                {
                    throw new InvalidOperationException(ex.Message);
                }
                catch (InvalidOperationException)
                {
                    throw;
                }
            }
        }

        private sealed class AddReturnTrampoline
        {
            private readonly Func<NeuralCircuitBuilder> _builderProvider;

            public AddReturnTrampoline(Func<NeuralCircuitBuilder> builderProvider) { _builderProvider = builderProvider; }

            public string Invoke(
                [Description("Short human-readable label for this return node; surfaces in audit / visualization.")]
                string label,
                [Description("Final summary template; may include placeholders '{previous.summary}' " +
                             "or '{node_<id>.summary}' resolved by Orchestrator at execution time.")]
                string summaryTemplate)
            {
                var builder = ResolveBuilder(_builderProvider);
                try
                {
                    return builder.AddReturn(label, summaryTemplate);
                }
                catch (ArgumentException ex)
                {
                    throw new InvalidOperationException(ex.Message);
                }
                catch (InvalidOperationException)
                {
                    throw;
                }
            }
        }

        private sealed class AddEdgeTrampoline
        {
            private readonly Func<NeuralCircuitBuilder> _builderProvider;

            public AddEdgeTrampoline(Func<NeuralCircuitBuilder> builderProvider) { _builderProvider = builderProvider; }

            public string Invoke(
                [Description("Source node id (returned by a prior __circuit_add_* call).")]
                string fromNodeId,
                [Description("Target node id (returned by a prior __circuit_add_* call).")]
                string toNodeId,
                [Description("Branch label; MUST be supplied when fromNodeId is a Branch node " +
                             "(use 'true'/'false' to match Branch evaluation), MUST be null otherwise.")]
                string? branchLabel)
            {
                var builder = ResolveBuilder(_builderProvider);
                try
                {
                    builder.AddEdge(fromNodeId, toNodeId, branchLabel);
                    return "ok";
                }
                catch (ArgumentException ex)
                {
                    throw new InvalidOperationException(ex.Message);
                }
                catch (InvalidOperationException)
                {
                    throw;
                }
            }
        }

        private sealed class CommitTrampoline
        {
            private readonly Func<NeuralCircuitBuilder> _builderProvider;

            public CommitTrampoline(Func<NeuralCircuitBuilder> builderProvider) { _builderProvider = builderProvider; }

            public string Invoke()
            {
                var builder = ResolveBuilder(_builderProvider);
                try
                {
                    var circuit = builder.Commit();
                    return
                        $"committed circuit {circuit.CircuitId} with " +
                        $"{circuit.Nodes.Count} nodes, {circuit.Edges.Count} edges";
                }
                catch (CircuitCompilationException ex)
                {
                    // C3：commit 失败必回退——把 Reason 透到 LLM，让主脑产「澄清问题」回用户。
                    throw new InvalidOperationException($"commit 失败: {ex.Reason}");
                }
                catch (InvalidOperationException)
                {
                    throw;
                }
            }
        }
    }
}
