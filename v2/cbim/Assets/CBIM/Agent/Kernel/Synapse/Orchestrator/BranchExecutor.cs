using System;
using System.Threading;
using System.Threading.Tasks;
using CBIM.AgentSystem.Kernel.Synapse.Compiler;
using Microsoft.Agents.AI.Workflows;

namespace CBIM.AgentSystem.Kernel.Synapse.Orchestrator
{
    /// <summary>
    /// <c>BranchNode</c> 的 MAF Executor 包装——节点执行体里调
    /// <see cref="ConditionEvaluator.Evaluate"/> 求值，把分支标签写入
    /// <see cref="CircuitMessage.BranchLabel"/>，再 SendMessage 给下游。
    ///
    /// <para>路由由 MAF 负责：T12 <c>CircuitToWorkflowCompiler</c> 在 AddEdge 时
    /// 注入 condition lambda <c>msg => msg.BranchLabel == edge.BranchLabel</c>，
    /// 自然只有匹配的出边会接到本消息。</para>
    /// <para>BranchNode 不产生新 outcome——上游 LastSummary 透传，History 不变。</para>
    /// </summary>
    internal sealed class BranchExecutor : Executor<CircuitMessage>
    {
        private readonly string _nodeId;
        private readonly BranchNode _node;

        public BranchExecutor(string nodeId, BranchNode node)
            : base(nodeId)
        {
            if (string.IsNullOrWhiteSpace(nodeId))
                throw new ArgumentException("BranchExecutor.nodeId 不能为空。", nameof(nodeId));
            if (node == null)
                throw new ArgumentNullException(nameof(node));

            _nodeId = nodeId;
            _node = node;
        }

        public override async ValueTask HandleAsync(
            CircuitMessage message,
            IWorkflowContext context,
            CancellationToken cancellationToken = default)
        {
            if (message == null)
                throw new ArgumentNullException(nameof(message));

            string matchedLabel;
            try
            {
                matchedLabel = ConditionEvaluator.Evaluate(_node.ConditionExpression, message);
            }
            catch (Exception ex)
            {
                var failure = new CircuitExecutionException(
                    _nodeId,
                    $"ConditionExpression 评估失败: {ex.Message}",
                    ex);
                await context.AddEventAsync(new ExecutorFailedEvent(_nodeId, failure), cancellationToken).ConfigureAwait(false);
                await context.RequestHaltAsync().ConfigureAwait(false);
                return;
            }

            var next = message.WithNext(
                newFromNodeId: _nodeId,
                newLastSummary: message.LastSummary,
                appendOutcome: null,
                newBranchLabel: matchedLabel);

            await context.SendMessageAsync(next, targetId: null, cancellationToken).ConfigureAwait(false);
        }
    }
}
