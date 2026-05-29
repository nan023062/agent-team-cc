using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using CBIM.AgentSystem.Brain;
using CBIM.AgentSystem.Kernel.Synapse;
using CBIM.AgentSystem.Kernel.Synapse.Compiler;
using Microsoft.Agents.AI.Workflows;

namespace CBIM.AgentSystem.Kernel.Synapse.Orchestrator
{
    /// <summary>
    /// FlowGraph 执行引擎门面——主脑（PrefrontalCortex）拿到 <see cref="NeuralCircuit"/> 编译产物后，
    /// 通过本类驱动 MAF Workflow 执行，最终拿回一个 <see cref="BrainOutcome"/>。
    ///
    /// <para>设计定位：</para>
    /// <list type="bullet">
    ///   <item>本类是 <c>CBIM.AgentSystem.Kernel.Synapse.Orchestrator</c> 子模块的唯一外部入口。
    ///     内部装配走 <see cref="CircuitToWorkflowCompiler"/>（T12）；执行驱动绑定 MAF
    ///     <see cref="InProcessExecution"/>（O1 铁律：不重造引擎）。</item>
    ///   <item>事件转译：MAF <see cref="WorkflowEvent"/> → <see cref="IPrefrontalCallback.ReportProgress"/>。
    ///     本类不直接接触 Channel（O4 铁律：上报绕 callback）。</item>
    ///   <item>失败语义：fail-fast——任何 <see cref="WorkflowErrorEvent"/> 或
    ///     <see cref="ExecutorFailedEvent"/> 直接转 <see cref="BrainOutcome.IsError"/>=true，
    ///     不重试、不 fallback（O3 铁律）。</item>
    /// </list>
    ///
    /// <para>K6 铁律：本类只依赖 T8 IR（<see cref="NeuralCircuit"/> 与节点）+ T11 Executor 包
    /// + T12 翻译器 + MAF Workflow API + <see cref="IPrefrontalCallback"/>。不引 Compiler 子模块
    /// 的 <c>CompilerToolFactory</c>、不引 Synapse 顶层的 <c>SynapseToolFactory</c>、不引
    /// <c>CBIM.AgentSystem.Kernel.Neuron</c>（K4）、不引 <c>CBIM.Channel</c>（O4）。</para>
    /// </summary>
    public sealed class CBIMOrchestrator
    {
        /// <summary>
        /// 入口 envelope 的 <see cref="CircuitMessage.FromNodeId"/>——v1 用固定字面量，
        /// 仅作下游 BrainCallExecutor 引用 <see cref="CircuitMessage.History"/> 时的「无前驱」标记。
        /// </summary>
        private const string OrchestratorEntryNodeId = "@orchestrator-start";

        /// <summary>
        /// 进度 / 错误转译时的发送方 <c>brainId</c>——区别于具体 BrainBase Id；
        /// 主脑侧 <see cref="IPrefrontalCallback"/> 适配器收到该值时知是「图执行框架自身」的事件。
        /// </summary>
        private const string OrchestratorReporterId = "@orchestrator";

        /// <summary>
        /// 执行一个已编译好的 <see cref="NeuralCircuit"/>。
        ///
        /// <para>主流程：</para>
        /// <list type="number">
        ///   <item>非空校验 + <see cref="NeuralCircuit.Nodes"/> 非空校验。</item>
        ///   <item>调 <see cref="CircuitToWorkflowCompiler.Compile"/> 装出 MAF <see cref="Workflow"/>。</item>
        ///   <item>构造入口 <see cref="CircuitMessage"/>——<see cref="CircuitMessage.LastSummary"/>
        ///     取 <see cref="NeuralCircuit.SourceRequest"/>（首节点的 BrainInvocation 上文）；
        ///     <see cref="CircuitMessage.History"/> 空。</item>
        ///   <item><see cref="InProcessExecution.RunStreamingAsync"/> 启动流式执行。</item>
        ///   <item>迭代 <see cref="StreamingRun.WatchStreamAsync"/>——
        ///     <see cref="ExecutorInvokedEvent"/> / <see cref="ExecutorCompletedEvent"/> 转
        ///     <see cref="IPrefrontalCallback.ReportProgress"/>；
        ///     <see cref="WorkflowOutputEvent"/>（由 <see cref="ReturnExecutor"/> 产）收 finalSummary；
        ///     <see cref="WorkflowErrorEvent"/> / <see cref="ExecutorFailedEvent"/> 累入 errors。</item>
        ///   <item>循环结束（halt 或 stream 完成）后据 errors / finalSummary 产 <see cref="BrainOutcome"/>。</item>
        /// </list>
        ///
        /// <para>失败转译：</para>
        /// <list type="bullet">
        ///   <item>循环中收到任何错误事件 → <see cref="BrainOutcome.IsError"/>=true，
        ///     <see cref="BrainOutcome.ErrorMessage"/> 由收到的错误消息以 <c>"; "</c> 拼接。</item>
        ///   <item>halt 但 finalSummary 仍为 null（无 ReturnNode 触发输出）→
        ///     <see cref="BrainOutcome.IsError"/>=true，错误描述固定字符串。</item>
        ///   <item><see cref="OperationCanceledException"/> 直接上抛——cancellation ≠ 节点失败，
        ///     由主脑或更上层决定如何处理。</item>
        /// </list>
        /// </summary>
        /// <param name="circuit">已 commit 的编译产物。不为 null；<see cref="NeuralCircuit.Nodes"/> 不为空。</param>
        /// <param name="brainPalette">本次执行可调脑区集合——所有 <c>CallBrainNode.TargetBrainId</c>
        ///   必须能在此找到（否则 T12 装配期抛 <see cref="CircuitExecutionException"/>）。</param>
        /// <param name="callback">主脑回调通路。不为 null；debug 路径可用
        ///   <see cref="CompileToMafWorkflow"/>。</param>
        /// <param name="ct">取消令牌——传给 MAF 与 stream 迭代。</param>
        public async Task<BrainOutcome> RunAsync(
            NeuralCircuit circuit,
            IReadOnlyList<BrainBase> brainPalette,
            IPrefrontalCallback callback,
            CancellationToken ct)
        {
            if (circuit == null)
                throw new ArgumentNullException(nameof(circuit));
            if (brainPalette == null)
                throw new ArgumentNullException(nameof(brainPalette));
            if (callback == null)
                throw new ArgumentNullException(nameof(callback));
            if (circuit.Nodes.Count == 0)
            {
                throw new ArgumentException(
                    "NeuralCircuit.Nodes 为空——图无可执行节点。",
                    nameof(circuit));
            }

            // 1) 翻译 IR → MAF Workflow。装配期错误（palette 缺脑区 / 边引用未知节点 / 不支持节点类型）
            //    会在此处抛出，O3 铁律下不被捕获——直接以异常上抛由调用方处理。
            Workflow workflow = CircuitToWorkflowCompiler.Compile(circuit, brainPalette, callback);

            // 2) 入口 envelope。FromNodeId 用固定标记字面量，下游 BrainCallExecutor 不会回查
            //    History[@orchestrator-start]，因为此时 History 为空。
            var startMessage = new CircuitMessage(
                circuitId: circuit.CircuitId,
                fromNodeId: OrchestratorEntryNodeId,
                branchLabel: null,
                lastSummary: circuit.SourceRequest,
                history: new Dictionary<string, BrainOutcome>(StringComparer.Ordinal));

            // 3) 启 stream run。RunStreamingAsync 返 ValueTask<StreamingRun>，
            //    StreamingRun 实现 IAsyncDisposable。
            await using StreamingRun run = await InProcessExecution
                .RunStreamingAsync(workflow, startMessage, cancellationToken: ct)
                .ConfigureAwait(false);

            string? finalSummary = null;
            List<string>? errors = null;

            // 4) 迭代事件流。WatchStreamAsync 文档约定：流在 RequestHaltEvent / cancellation 时自然结束。
            //    OperationCanceledException 直接透传（cancellation ≠ 节点失败）。
            await foreach (WorkflowEvent ev in run.WatchStreamAsync(ct).ConfigureAwait(false))
            {
                switch (ev)
                {
                    case ExecutorFailedEvent failed:
                    {
                        // 节点级失败：记录后继续消费（MAF 自己会冒 RequestHaltEvent 终结流）。
                        string message = failed.Data?.Message ?? "executor failed without exception";
                        (errors ??= new List<string>()).Add(
                            $"node '{failed.ExecutorId}': {message}");
                        break;
                    }

                    case WorkflowErrorEvent error:
                    {
                        // 工作流级失败（含 unhandled exception）。
                        string message = error.Exception?.Message ?? "unknown workflow error";
                        (errors ??= new List<string>()).Add(message);
                        break;
                    }

                    case WorkflowOutputEvent output:
                    {
                        // ReturnExecutor.YieldOutputAsync 产 string；其他类型保守起见忽略。
                        if (output.Data is string text)
                        {
                            finalSummary = text;
                        }
                        break;
                    }

                    case ExecutorInvokedEvent invoked:
                    {
                        callback.ReportProgress(
                            OrchestratorReporterId,
                            $"running node {invoked.ExecutorId}");
                        break;
                    }

                    case ExecutorCompletedEvent completed:
                    {
                        callback.ReportProgress(
                            OrchestratorReporterId,
                            $"node {completed.ExecutorId} done");
                        break;
                    }
                }
            }

            // 5) 终态转译。
            if (errors != null && errors.Count > 0)
            {
                return new BrainOutcome(
                    Summary: string.Empty,
                    StructuredOutput: null,
                    SideEffects: Array.Empty<SideEffect>(),
                    IsError: true,
                    ErrorMessage: string.Join("; ", errors));
            }

            if (finalSummary == null)
            {
                return new BrainOutcome(
                    Summary: string.Empty,
                    StructuredOutput: null,
                    SideEffects: Array.Empty<SideEffect>(),
                    IsError: true,
                    ErrorMessage: "circuit halted without return: no ReturnNode 触发 WorkflowOutputEvent。");
            }

            return new BrainOutcome(
                Summary: finalSummary,
                StructuredOutput: null,
                SideEffects: Array.Empty<SideEffect>(),
                IsError: false,
                ErrorMessage: null);
        }

        /// <summary>
        /// 仅供测试 / debug：直接返回编译产出的 MAF <see cref="Workflow"/>，不启执行。
        /// 内部用 <see cref="NullPrefrontalCallback.Instance"/> 占位 callback——本路径
        /// 不会触发 <see cref="BrainCallExecutor"/>（执行才会），callback 不会被实际调用。
        /// </summary>
        public Workflow CompileToMafWorkflow(
            NeuralCircuit circuit,
            IReadOnlyList<BrainBase> brainPalette,
            IPrefrontalCallback callback)
        {
            if (circuit == null)
                throw new ArgumentNullException(nameof(circuit));
            if (brainPalette == null)
                throw new ArgumentNullException(nameof(brainPalette));
            if (callback == null)
                throw new ArgumentNullException(nameof(callback));

            return CircuitToWorkflowCompiler.Compile(circuit, brainPalette, callback);
        }
    }

    /// <summary>
    /// 空回调——供 <see cref="CBIMOrchestrator.CompileToMafWorkflow"/> 等 debug 路径占位。
    /// 不向外暴露，避免被生产路径误用。
    /// </summary>
    internal sealed class NullPrefrontalCallback : IPrefrontalCallback
    {
        public static readonly NullPrefrontalCallback Instance = new NullPrefrontalCallback();

        private NullPrefrontalCallback() { }

        public void ReportProgress(string brainId, string message) { }

        public void ReportOutcome(string brainId, BrainOutcome outcome) { }
    }
}
