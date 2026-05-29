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
    /// <c>CallBrainNode</c> 的 MAF Executor 包装——节点执行体里调
    /// <see cref="BrainBase.InvokeAsync"/> 投递 Intent 到目标脑区，再把 outcome 沿
    /// <see cref="CircuitMessage"/> 传给下游。
    ///
    /// <para>O1 铁律：不重造执行引擎——继承 MAF <see cref="Executor{TInput}"/>，让 MAF
    /// 负责消息路由 / SuperStep 调度 / Checkpoint。</para>
    /// <para>O3 铁律：fail-fast——<see cref="BrainBase.InvokeAsync"/> 抛异常或返回
    /// <see cref="BrainOutcome.IsError"/>=true 时，不重试、不 fallback；直接 AddEvent
    /// <see cref="ExecutorFailedEvent"/> + <see cref="IWorkflowContext.RequestHaltAsync"/>，
    /// 主脑下一轮拿 IsError 结果自行决定是否重编。</para>
    /// <para>O4 铁律：上报绕 <see cref="IPrefrontalCallback"/>——本类不感知 Channel 存在。</para>
    /// </summary>
    internal sealed class BrainCallExecutor : Executor<CircuitMessage>
    {
        private readonly string _nodeId;
        private readonly CallBrainNode _node;
        private readonly BrainBase _brain;
        private readonly IPrefrontalCallback _callback;

        public BrainCallExecutor(
            string nodeId,
            CallBrainNode node,
            BrainBase brain,
            IPrefrontalCallback callback)
            : base(nodeId)
        {
            if (string.IsNullOrWhiteSpace(nodeId))
                throw new ArgumentException("BrainCallExecutor.nodeId 不能为空。", nameof(nodeId));
            if (node == null)
                throw new ArgumentNullException(nameof(node));
            if (brain == null)
                throw new ArgumentNullException(nameof(brain));
            if (callback == null)
                throw new ArgumentNullException(nameof(callback));

            // T11 装配期校验：palette 中拿到的 BrainBase 必须与节点声明的 TargetBrainId 对齐——
            // 这是 T12 CircuitToWorkflowCompiler 调用前最后一道护栏（fail-fast）。
            if (!string.Equals(brain.BrainId, node.TargetBrainId, StringComparison.Ordinal))
            {
                throw new CircuitExecutionException(
                    nodeId,
                    $"BrainPalette 提供的 BrainId='{brain.BrainId}' 与 CallBrainNode.TargetBrainId='{node.TargetBrainId}' 不匹配。");
            }

            _nodeId = nodeId;
            _node = node;
            _brain = brain;
            _callback = callback;
        }

        public override async ValueTask HandleAsync(
            CircuitMessage message,
            IWorkflowContext context,
            CancellationToken cancellationToken = default)
        {
            if (message == null)
                throw new ArgumentNullException(nameof(message));

            _callback.ReportProgress("@orchestrator", $"running node {_nodeId} (brain={_brain.BrainId})");

            var invocationContext = new Dictionary<string, object>
            {
                ["previous"] = message.LastSummary,
            };

            var invocation = new BrainInvocation(
                CorrelationId: Guid.NewGuid().ToString(),
                Intent: _node.Intent,
                StructuredInput: _node.StructuredInputJson,
                Context: invocationContext);

            BrainOutcome outcome;
            try
            {
                outcome = await _brain.InvokeAsync(invocation, cancellationToken).ConfigureAwait(false);
            }
            catch (OperationCanceledException)
            {
                // 取消透传给 MAF——不视作节点失败。
                throw;
            }
            catch (Exception ex)
            {
                var failure = new CircuitExecutionException(_nodeId, ex.Message, ex);
                await context.AddEventAsync(new ExecutorFailedEvent(_nodeId, failure), cancellationToken).ConfigureAwait(false);
                await context.RequestHaltAsync().ConfigureAwait(false);
                return;
            }

            if (outcome.IsError)
            {
                var failure = new CircuitExecutionException(_nodeId, outcome.ErrorMessage ?? "unknown error");
                await context.AddEventAsync(new ExecutorFailedEvent(_nodeId, failure), cancellationToken).ConfigureAwait(false);
                await context.RequestHaltAsync().ConfigureAwait(false);
                return;
            }

            _callback.ReportProgress("@orchestrator", $"node {_nodeId} done");

            var next = message.WithNext(
                newFromNodeId: _nodeId,
                newLastSummary: outcome.Summary,
                appendOutcome: outcome,
                newBranchLabel: null);

            await context.SendMessageAsync(next, targetId: null, cancellationToken).ConfigureAwait(false);
        }
    }
}
