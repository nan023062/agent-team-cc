using System.Collections.Generic;

namespace CBIM.AgentSystem.Brain
{
    /// <summary>
    /// 主脑（PrefrontalCortex）向子脑区下发的一次调用请求。
    /// 由 <c>__brain_call_*</c> AIFunction 的 handler 构造，传给目标脑区的
    /// <see cref="BrainBase.InvokeAsync"/>。
    /// </summary>
    /// <param name="CorrelationId">关联主脑 AIFunction call id（追踪用 · 通常是 Guid）。</param>
    /// <param name="Intent">自然语言意图——目标脑区据此推理具体动作。</param>
    /// <param name="StructuredInput">可选结构化输入（任意可序列化对象）。</param>
    /// <param name="Context">主脑当前对话上下文切片（key-value · 不为 null）。</param>
    public sealed class BrainInvocation
    {
        public string CorrelationId { get; }
        public string Intent { get; }
        public object? StructuredInput { get; }
        public IReadOnlyDictionary<string, object> Context { get; }

        public BrainInvocation(
            string CorrelationId,
            string Intent,
            object? StructuredInput,
            IReadOnlyDictionary<string, object> Context)
        {
            this.CorrelationId = CorrelationId;
            this.Intent = Intent;
            this.StructuredInput = StructuredInput;
            this.Context = Context;
        }
    }
}
