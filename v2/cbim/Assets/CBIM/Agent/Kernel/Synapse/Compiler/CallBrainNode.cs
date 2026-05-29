using System;

namespace CBIM.AgentSystem.Kernel.Synapse.Compiler
{
    /// <summary>
    /// CallBrain 节点——投递 Intent 到某个脑区（最常见节点；等同于上轮的 <c>__brain_call_*</c>）。
    ///
    /// <para>本切片只做字符串非空校验。<see cref="TargetBrainId"/> 是否对应一个真实存在的
    /// 可调脑区（palette 是否覆盖），由 <c>BrainCallExecutor</c>（T11）在装配期校验——
    /// Compiler 不持 BrainRegistry 引用（K6 铁律：Compiler ⊥ Orchestrator 命名空间 + 不感知执行细节）。</para>
    /// </summary>
    public sealed class CallBrainNode : CircuitNode
    {
        /// <summary>目标脑区 Id——如 <c>motor-cortex.native</c> / <c>parietal-lobe</c>。</summary>
        public string TargetBrainId { get; }

        /// <summary>自然语言意图——透传给 <c>BrainInvocation.Intent</c>。</summary>
        public string Intent { get; }

        /// <summary>可选 JSON 载荷——透传给 <c>BrainInvocation.StructuredInput</c>；不需要时为 null。</summary>
        public string? StructuredInputJson { get; }

        public CallBrainNode(
            string nodeId,
            string label,
            string targetBrainId,
            string intent,
            string? structuredInputJson)
            : base(nodeId, label)
        {
            if (string.IsNullOrWhiteSpace(targetBrainId))
                throw new ArgumentException("CallBrainNode.TargetBrainId 不能为空。", nameof(targetBrainId));
            if (string.IsNullOrWhiteSpace(intent))
                throw new ArgumentException("CallBrainNode.Intent 不能为空。", nameof(intent));

            TargetBrainId = targetBrainId;
            Intent = intent;
            StructuredInputJson = structuredInputJson;
        }
    }
}
