using System;

namespace CBIM.AgentSystem.Kernel.Synapse.Orchestrator
{
    /// <summary>
    /// <c>BranchNode.ConditionExpression</c> 的极简 evaluator——v1 只识 <c>contains</c> / <c>equals</c>。
    ///
    /// <para>语法 (v1)：</para>
    /// <code>
    ///   &lt;lhs&gt; &lt;op&gt; "&lt;rhs&gt;"
    /// </code>
    /// <para>其中：</para>
    /// <list type="bullet">
    ///   <item><c>lhs</c> 形如 <c>previous.summary</c> 或 <c>node_n03.summary</c>（无引号）。</item>
    ///   <item><c>op</c> 为 <c>contains</c> 或 <c>equals</c>（前后单空格分隔）。</item>
    ///   <item><c>rhs</c> 必须为双引号字符串字面量；不支持转义、不支持单引号。</item>
    /// </list>
    ///
    /// <para>返回值为字符串字面量 <c>"true"</c> 或 <c>"false"</c>——直接作为
    /// <see cref="CircuitMessage.BranchLabel"/> 喂给下游 MAF AddEdge 的 condition lambda。
    /// 这与 <c>CircuitEdge.BranchLabel</c>（由 LLM 在编译期写入 <c>"true"</c> / <c>"false"</c>）保持字面量一致。</para>
    ///
    /// <para>不支持的语法（AND / OR / NOT / 比较运算符 / 嵌套表达式 / 转义）一律抛
    /// <see cref="NotSupportedException"/>——留 <c>ExpressionEngine</c> 未来子模块扩充。</para>
    /// </summary>
    internal static class ConditionEvaluator
    {
        private const string LiteralTrue = "true";
        private const string LiteralFalse = "false";
        private const string OpContainsToken = " contains ";
        private const string OpEqualsToken = " equals ";

        public static string Evaluate(string conditionExpression, CircuitMessage message)
        {
            if (string.IsNullOrWhiteSpace(conditionExpression))
                throw new ArgumentException("ConditionExpression 不能为空。", nameof(conditionExpression));
            if (message == null)
                throw new ArgumentNullException(nameof(message));

            string expr = conditionExpression.Trim();

            string @operator;
            int opIndex;
            if ((opIndex = expr.IndexOf(OpContainsToken, StringComparison.Ordinal)) >= 0)
            {
                @operator = "contains";
            }
            else if ((opIndex = expr.IndexOf(OpEqualsToken, StringComparison.Ordinal)) >= 0)
            {
                @operator = "equals";
            }
            else
            {
                throw new NotSupportedException(
                    $"ConditionExpression 仅支持 'contains' 或 'equals' (v1)，未识别运算符: {expr}");
            }

            string lhs = expr.Substring(0, opIndex).Trim();
            string rhsPart = expr.Substring(opIndex + (@operator == "contains" ? OpContainsToken.Length : OpEqualsToken.Length)).Trim();

            string rhs = ParseQuotedLiteral(rhsPart, expr);
            string lhsValue = ResolveLhs(lhs, message, expr);

            bool result = @operator == "contains"
                ? lhsValue.IndexOf(rhs, StringComparison.Ordinal) >= 0
                : string.Equals(lhsValue, rhs, StringComparison.Ordinal);

            return result ? LiteralTrue : LiteralFalse;
        }

        private static string ParseQuotedLiteral(string rhsPart, string fullExpr)
        {
            if (rhsPart.Length < 2 || rhsPart[0] != '"' || rhsPart[rhsPart.Length - 1] != '"')
            {
                throw new NotSupportedException(
                    $"ConditionExpression rhs 必须为双引号字符串字面量 (v1, 不支持转义): {fullExpr}");
            }
            return rhsPart.Substring(1, rhsPart.Length - 2);
        }

        private static string ResolveLhs(string lhs, CircuitMessage message, string fullExpr)
        {
            const string previousSummary = "previous.summary";
            const string nodePrefix = "node_";
            const string summarySuffix = ".summary";

            if (lhs == previousSummary)
            {
                return message.LastSummary;
            }

            if (lhs.StartsWith(nodePrefix, StringComparison.Ordinal) &&
                lhs.EndsWith(summarySuffix, StringComparison.Ordinal))
            {
                string nodeId = lhs.Substring(nodePrefix.Length, lhs.Length - nodePrefix.Length - summarySuffix.Length);
                if (string.IsNullOrWhiteSpace(nodeId))
                {
                    throw new NotSupportedException(
                        $"ConditionExpression lhs 节点 Id 不能为空: {fullExpr}");
                }
                if (!message.History.TryGetValue(nodeId, out var outcome))
                {
                    throw new NotSupportedException(
                        $"ConditionExpression lhs 引用了未在 History 中的节点 '{nodeId}': {fullExpr}");
                }
                return outcome.Summary ?? string.Empty;
            }

            throw new NotSupportedException(
                $"ConditionExpression lhs 仅支持 'previous.summary' 或 'node_<id>.summary' (v1): {fullExpr}");
        }
    }
}
