#if UNITY_INCLUDE_TESTS
using System.Collections.Generic;

namespace CBIM.AgentSystem.Brain.Tests
{
    /// <summary>
    /// <see cref="IPrefrontalCallback"/> 桩——记录每次回报（brainId + payload）。
    /// 用于断言「callback 被调用过/未被调用」与回报顺序。
    /// v1 PrefrontalCallbackAdapter 是 no-op，所以这个 fake 在「装配链测试」里
    /// 主要用作 ctor 强制 non-null 的占位（CallableBrains 子脑区禁止 null callback）。
    /// </summary>
    internal sealed class FakePrefrontalCallback : IPrefrontalCallback
    {
        public readonly List<(string BrainId, string Message)> Progresses = new List<(string, string)>();
        public readonly List<(string BrainId, BrainOutcome Outcome)> Outcomes = new List<(string, BrainOutcome)>();

        public void ReportProgress(string brainId, string message)
        {
            Progresses.Add((brainId, message));
        }

        public void ReportOutcome(string brainId, BrainOutcome outcome)
        {
            Outcomes.Add((brainId, outcome));
        }
    }
}
#endif
