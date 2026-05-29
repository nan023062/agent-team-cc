#if UNITY_INCLUDE_TESTS
using System;
using System.Collections.Generic;
using NUnit.Framework;
using CBIM.AgentSystem.Brain;
using CBIM.AgentSystem.Kernel.Synapse.Orchestrator;

namespace CBIM.AgentSystem.Kernel.Synapse.Orchestrator.Tests
{
    /// <summary>
    /// T11 ConditionEvaluator 测试——覆盖：
    ///   - 'previous.summary contains "x"' 真 / 假路径
    ///   - 'previous.summary equals "x"' 真 / 假路径
    ///   - 'node_n03.summary contains "y"' 引用 History 真路径
    ///   - History 缺该 node 时抛 NotSupportedException
    ///   - 不识别运算符 / 非引号 rhs / 未知 lhs 一律 NotSupportedException
    ///   - 空白表达式 / null message 抛 ArgumentException / ArgumentNullException
    ///   - 返回字面量 "true"/"false"（与 CircuitMessage.BranchLabel 字面量保持一致）
    /// </summary>
    [TestFixture]
    public sealed class ConditionEvaluatorTests
    {
        // ===== (1) contains 真 / 假 =====

        [Test]
        public void Evaluate_contains_returns_true_when_substring_matches()
        {
            var msg = BuildMessage(lastSummary: "task approved with notes");
            var r = ConditionEvaluator.Evaluate("previous.summary contains \"approved\"", msg);
            Assert.That(r, Is.EqualTo("true"));
        }

        [Test]
        public void Evaluate_contains_returns_false_when_no_substring_match()
        {
            var msg = BuildMessage(lastSummary: "rejected");
            var r = ConditionEvaluator.Evaluate("previous.summary contains \"approved\"", msg);
            Assert.That(r, Is.EqualTo("false"));
        }

        // ===== (2) equals 真 / 假 =====

        [Test]
        public void Evaluate_equals_returns_true_when_exact_match()
        {
            var msg = BuildMessage(lastSummary: "approved");
            var r = ConditionEvaluator.Evaluate("previous.summary equals \"approved\"", msg);
            Assert.That(r, Is.EqualTo("true"));
        }

        [Test]
        public void Evaluate_equals_returns_false_when_substring_not_full_match()
        {
            // contains 真但 equals 假——验证两运算符语义有别。
            var msg = BuildMessage(lastSummary: "approved with notes");
            var r = ConditionEvaluator.Evaluate("previous.summary equals \"approved\"", msg);
            Assert.That(r, Is.EqualTo("false"));
        }

        // ===== (3) node_<id>.summary 引用 History =====

        [Test]
        public void Evaluate_node_summary_references_History_when_node_exists()
        {
            var history = new Dictionary<string, BrainOutcome>
            {
                ["n03"] = new BrainOutcome("approved", null, Array.Empty<SideEffect>(), false, null),
            };
            var msg = BuildMessage(lastSummary: "irrelevant", history: history);
            var r = ConditionEvaluator.Evaluate("node_n03.summary contains \"approved\"", msg);
            Assert.That(r, Is.EqualTo("true"));
        }

        [Test]
        public void Evaluate_throws_when_node_id_not_in_History()
        {
            var msg = BuildMessage(lastSummary: "x");
            Assert.Throws<NotSupportedException>(() =>
                ConditionEvaluator.Evaluate("node_n99.summary equals \"x\"", msg));
        }

        // ===== (4) 不支持的语法 =====

        [Test]
        public void Evaluate_throws_NotSupported_for_unknown_operator()
        {
            var msg = BuildMessage(lastSummary: "x");
            Assert.Throws<NotSupportedException>(() =>
                ConditionEvaluator.Evaluate("previous.summary startsWith \"x\"", msg));
        }

        [Test]
        public void Evaluate_throws_NotSupported_for_unquoted_rhs()
        {
            var msg = BuildMessage(lastSummary: "x");
            Assert.Throws<NotSupportedException>(() =>
                ConditionEvaluator.Evaluate("previous.summary equals x", msg));
        }

        [Test]
        public void Evaluate_throws_NotSupported_for_unknown_lhs()
        {
            var msg = BuildMessage(lastSummary: "x");
            Assert.Throws<NotSupportedException>(() =>
                ConditionEvaluator.Evaluate("nope.summary contains \"x\"", msg));
        }

        // ===== (5) 非法参数 =====

        [Test]
        public void Evaluate_rejects_blank_expression()
        {
            var msg = BuildMessage(lastSummary: "x");
            Assert.Throws<ArgumentException>(() => ConditionEvaluator.Evaluate("", msg));
            Assert.Throws<ArgumentException>(() => ConditionEvaluator.Evaluate("   ", msg));
        }

        [Test]
        public void Evaluate_rejects_null_message()
        {
            Assert.Throws<ArgumentNullException>(() =>
                ConditionEvaluator.Evaluate("previous.summary equals \"x\"", message: null!));
        }

        // ===== helpers =====

        private static CircuitMessage BuildMessage(
            string lastSummary,
            IReadOnlyDictionary<string, BrainOutcome>? history = null)
        {
            return new CircuitMessage(
                circuitId: "cid-1",
                fromNodeId: "@start",
                branchLabel: null,
                lastSummary: lastSummary,
                history: history ?? new Dictionary<string, BrainOutcome>(StringComparer.Ordinal));
        }
    }
}
#endif
