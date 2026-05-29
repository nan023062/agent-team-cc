using System;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using CBIM.AgentSystem.Kernel.Synapse.Compiler;
using Microsoft.Agents.AI.Workflows;

namespace CBIM.AgentSystem.Kernel.Synapse.Orchestrator
{
    /// <summary>
    /// <c>ReturnNode</c> 的 MAF Executor 包装——终止节点：渲染 <c>SummaryTemplate</c> →
    /// <see cref="IWorkflowContext.YieldOutputAsync"/> →
    /// <see cref="IWorkflowContext.RequestHaltAsync"/>，把最终文本作为 Workflow 输出冒出去
    /// 由 T13 Orchestrator 门面层包装成 <c>BrainOutcome</c> 回主脑。
    ///
    /// <para>v1 模板占位符语法（与 <c>ConditionEvaluator</c> 的 lhs 保持字面量一致）：</para>
    /// <list type="bullet">
    ///   <item><c>{previous.summary}</c> → <see cref="CircuitMessage.LastSummary"/></item>
    ///   <item><c>{node_&lt;id&gt;.summary}</c> → <see cref="CircuitMessage.History"/>[id].Summary</item>
    /// </list>
    /// <para>未在 History 中的 <c>node_xxx</c> 占位符按空串替换——v1 模板不抛错（与 ConditionExpression
    /// 严格求值不同：模板缺字段大概率是 LLM 写错小节点 id，由 ReturnNode 自身的 Summary 包容降级）。</para>
    /// </summary>
    internal sealed class ReturnExecutor : Executor<CircuitMessage, string>
    {
        private static readonly Regex PlaceholderRegex = new Regex(
            @"\{previous\.summary\}|\{node_(?<id>[A-Za-z0-9_\-]+)\.summary\}",
            RegexOptions.Compiled | RegexOptions.CultureInvariant);

        private readonly string _nodeId;
        private readonly ReturnNode _node;

        public ReturnExecutor(string nodeId, ReturnNode node)
            : base(nodeId)
        {
            if (string.IsNullOrWhiteSpace(nodeId))
                throw new ArgumentException("ReturnExecutor.nodeId 不能为空。", nameof(nodeId));
            if (node == null)
                throw new ArgumentNullException(nameof(node));

            _nodeId = nodeId;
            _node = node;
        }

        public override async ValueTask<string> HandleAsync(
            CircuitMessage message,
            IWorkflowContext context,
            CancellationToken cancellationToken = default)
        {
            if (message == null)
                throw new ArgumentNullException(nameof(message));

            string rendered = RenderTemplate(_node.SummaryTemplate, message);

            await context.YieldOutputAsync(rendered, cancellationToken).ConfigureAwait(false);
            await context.RequestHaltAsync().ConfigureAwait(false);

            return rendered;
        }

        private static string RenderTemplate(string template, CircuitMessage message)
        {
            return PlaceholderRegex.Replace(template, match =>
            {
                if (match.Value == "{previous.summary}")
                {
                    return message.LastSummary ?? string.Empty;
                }

                string nodeId = match.Groups["id"].Value;
                if (message.History.TryGetValue(nodeId, out var outcome))
                {
                    return outcome.Summary ?? string.Empty;
                }
                return string.Empty;
            });
        }
    }
}
