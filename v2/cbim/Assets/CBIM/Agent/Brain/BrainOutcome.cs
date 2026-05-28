using System.Collections.Generic;

namespace CBIM.AgentSystem.Brain
{
    /// <summary>
    /// 子脑区返回给主脑的执行结果。
    /// <see cref="Summary"/> 作为 ToolMessage 回填到主脑下一轮 LLM 上下文；
    /// <see cref="StructuredOutput"/> 供有需要的主脑路径解析（如 FissionProposal）；
    /// <see cref="SideEffects"/> 是 MotorCortex 家族脑区必填的副作用清单。
    /// </summary>
    /// <param name="Summary">自然语言摘要——回填 LLM。</param>
    /// <param name="StructuredOutput">可选结构化产出。</param>
    /// <param name="SideEffects">副作用清单（MotorCortex 类必填；其他脑区通常为空 · 不为 null）。</param>
    /// <param name="IsError">是否错误结果。</param>
    /// <param name="ErrorMessage"><see cref="IsError"/>=true 时的错误说明。</param>
    public sealed record BrainOutcome(
        string Summary,
        object? StructuredOutput,
        IReadOnlyList<SideEffect> SideEffects,
        bool IsError,
        string? ErrorMessage);
}
