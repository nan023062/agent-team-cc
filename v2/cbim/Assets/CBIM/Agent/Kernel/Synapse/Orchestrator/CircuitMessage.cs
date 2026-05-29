using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using CBIM.AgentSystem.Brain;

namespace CBIM.AgentSystem.Kernel.Synapse.Orchestrator
{
    /// <summary>
    /// 节点间消息 envelope——MAF Executor 之间通过 <see cref="CircuitMessage"/> 串接，
    /// 沿 <c>NeuralCircuit</c> 中的边逐节点流动。
    ///
    /// <para>不可变值对象：每次节点完成后由 <see cref="WithNext"/> 派生新实例传给下游，
    /// 旧实例可作为审计快照保留（O2 铁律：图与消息均不在执行期就地修改）。</para>
    ///
    /// <para><see cref="History"/> 由 <c>BranchNode.ConditionExpression</c> 通过
    /// <c>ConditionEvaluator</c> 引用——形如 <c>node_n03.summary contains "approved"</c>。
    /// <see cref="LastSummary"/> 始终等于「上一个 <c>CallBrainNode</c> 的 outcome.Summary」
    /// （<c>BranchNode</c> 不产生新 summary，<see cref="WithNext"/> 直接透传）。</para>
    /// </summary>
    public sealed class CircuitMessage
    {
        /// <summary>所属回路 Id——便于交叉调试时识别 envelope 出处。</summary>
        public string CircuitId { get; }

        /// <summary>上一个执行节点 Id——下游节点用以引用 History。</summary>
        public string FromNodeId { get; }

        /// <summary>BranchNode 评估出的分支标签——用于 MAF AddEdge 的 condition lambda 匹配；
        /// 非 BranchNode 产生的消息恒为 <c>null</c>。</summary>
        public string? BranchLabel { get; }

        /// <summary>上一节点 outcome.Summary——回填进下一节点 BrainInvocation.Context["previous"]。</summary>
        public string LastSummary { get; }

        /// <summary>路径现场：nodeId → 该节点 BrainOutcome；只读视图（构造期一次性包装）。</summary>
        public IReadOnlyDictionary<string, BrainOutcome> History { get; }

        public CircuitMessage(
            string circuitId,
            string fromNodeId,
            string? branchLabel,
            string lastSummary,
            IReadOnlyDictionary<string, BrainOutcome> history)
        {
            if (string.IsNullOrWhiteSpace(circuitId))
                throw new ArgumentException("CircuitMessage.CircuitId 不能为空。", nameof(circuitId));
            if (string.IsNullOrWhiteSpace(fromNodeId))
                throw new ArgumentException("CircuitMessage.FromNodeId 不能为空。", nameof(fromNodeId));
            if (lastSummary == null)
                throw new ArgumentNullException(nameof(lastSummary));
            if (history == null)
                throw new ArgumentNullException(nameof(history));

            CircuitId = circuitId;
            FromNodeId = fromNodeId;
            BranchLabel = branchLabel;
            LastSummary = lastSummary;
            History = new ReadOnlyDictionary<string, BrainOutcome>(
                new Dictionary<string, BrainOutcome>(history));
        }

        /// <summary>
        /// 派生下一节点的 envelope——不可变更新：复制 History、按需 append、构造新实例返回。
        /// </summary>
        /// <param name="newFromNodeId">本次产生消息的节点 Id（即将成为下游的 FromNodeId）。</param>
        /// <param name="newLastSummary">本节点 outcome.Summary（BranchNode 透传上游的 LastSummary）。</param>
        /// <param name="appendOutcome">本节点 BrainOutcome——非 null 时以 <paramref name="newFromNodeId"/> 为 key 追加进 History。</param>
        /// <param name="newBranchLabel">本节点选定的分支标签——BranchNode 设为 <c>"true"</c>/<c>"false"</c>/标签字符串；其他节点传 <c>null</c>。</param>
        public CircuitMessage WithNext(
            string newFromNodeId,
            string newLastSummary,
            BrainOutcome? appendOutcome,
            string? newBranchLabel)
        {
            if (string.IsNullOrWhiteSpace(newFromNodeId))
                throw new ArgumentException("CircuitMessage.WithNext.newFromNodeId 不能为空。", nameof(newFromNodeId));
            if (newLastSummary == null)
                throw new ArgumentNullException(nameof(newLastSummary));

            var nextHistory = new Dictionary<string, BrainOutcome>(History);
            if (appendOutcome != null)
            {
                nextHistory[newFromNodeId] = appendOutcome;
            }

            return new CircuitMessage(
                CircuitId,
                newFromNodeId,
                newBranchLabel,
                newLastSummary,
                nextHistory);
        }
    }
}
