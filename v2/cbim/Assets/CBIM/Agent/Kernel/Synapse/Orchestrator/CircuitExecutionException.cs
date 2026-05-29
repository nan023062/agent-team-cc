using System;

namespace CBIM.AgentSystem.Kernel.Synapse.Orchestrator
{
    /// <summary>
    /// 回路执行期失败异常——由 Orchestrator 子模块内部 Executor 在执行图节点时抛出。
    ///
    /// <para>触发场景（v1）：</para>
    /// <list type="bullet">
    ///   <item><c>BrainCallExecutor</c> 构造期 brainPalette 不含目标 BrainId。</item>
    ///   <item><c>BrainCallExecutor</c> 节点执行返回 <c>IsError=true</c> 或 <c>BrainBase.InvokeAsync</c> 抛异常，
    ///     由 Executor 包装为本异常上报到 MAF <c>ExecutorFailedEvent</c>。</item>
    ///   <item><c>BranchExecutor</c> 内 <c>ConditionEvaluator</c> 解析 ConditionExpression 失败。</item>
    /// </list>
    ///
    /// <para>本异常由 MAF Workflow 引擎收集为 <c>WorkflowErrorEvent</c>；T13 Orchestrator 门面层
    /// 据此包装出 <c>BrainOutcome(IsError=true)</c> 回主脑。O3 铁律：节点失败 fail-fast 不 fail-creative。</para>
    /// </summary>
    public sealed class CircuitExecutionException : Exception
    {
        /// <summary>失败节点 Id——与 <c>CircuitNode.NodeId</c> 一致。</summary>
        public string NodeId { get; }

        public CircuitExecutionException(string nodeId, string reason)
            : base($"节点 {nodeId} 执行失败: {reason}")
        {
            NodeId = nodeId;
        }

        public CircuitExecutionException(string nodeId, string reason, Exception innerException)
            : base($"节点 {nodeId} 执行失败: {reason}", innerException)
        {
            NodeId = nodeId;
        }
    }
}
