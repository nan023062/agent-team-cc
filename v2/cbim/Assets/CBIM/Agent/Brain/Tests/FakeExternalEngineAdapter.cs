#if UNITY_INCLUDE_TESTS
using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;

namespace CBIM.AgentSystem.Brain.Tests
{
    /// <summary>
    /// 进程内 <see cref="IExternalEngineAdapter"/> 桩——不启 subprocess、不接 CLI。
    /// SubmitAsync 返回新 GUID（jobId）并记录 invocation；AwaitResultAsync 按 jobId 取出预置的 outcome。
    ///
    /// 测试可在 ctor 提供「下一个 outcome」队列，或注册 jobId → outcome 映射；
    /// 未配置 outcome 时返回默认成功 outcome（Summary="ok"）。
    /// </summary>
    internal sealed class FakeExternalEngineAdapter : IExternalEngineAdapter
    {
        private readonly List<string> _disposalLog;
        private readonly string _label;
        private readonly Dictionary<string, BrainOutcome> _outcomesByJob = new Dictionary<string, BrainOutcome>();
        private readonly Queue<BrainOutcome> _outcomeQueue = new Queue<BrainOutcome>();

        public int SubmitCallCount { get; private set; }
        public int AwaitCallCount { get; private set; }
        public int DisposeCallCount { get; private set; }
        public bool ThrowOnSubmit { get; set; }

        public readonly List<BrainInvocation> SubmittedInvocations = new List<BrainInvocation>();
        public readonly List<string> AwaitedJobIds = new List<string>();

        public FakeExternalEngineAdapter()
            : this(disposalLog: null, label: "adapter")
        {
        }

        public FakeExternalEngineAdapter(List<string> disposalLog, string label)
        {
            _disposalLog = disposalLog;
            _label = label ?? "adapter";
        }

        /// <summary>追加一条「下一次 AwaitResultAsync 的产出」（FIFO）。</summary>
        public void EnqueueOutcome(BrainOutcome outcome)
        {
            if (outcome == null) throw new ArgumentNullException(nameof(outcome));
            _outcomeQueue.Enqueue(outcome);
        }

        public Task<string> SubmitAsync(BrainInvocation invocation, CancellationToken ct)
        {
            SubmitCallCount++;
            if (ThrowOnSubmit)
                throw new InvalidOperationException("FakeExternalEngineAdapter: 测试触发的 Submit 异常。");

            SubmittedInvocations.Add(invocation);
            string jobId = Guid.NewGuid().ToString("N");
            return Task.FromResult(jobId);
        }

        public Task<BrainOutcome> AwaitResultAsync(string jobId, CancellationToken ct)
        {
            AwaitCallCount++;
            AwaitedJobIds.Add(jobId);

            if (_outcomesByJob.TryGetValue(jobId, out var byJob))
                return Task.FromResult(byJob);
            if (_outcomeQueue.Count > 0)
                return Task.FromResult(_outcomeQueue.Dequeue());

            return Task.FromResult(new BrainOutcome(
                Summary: "ok",
                StructuredOutput: null,
                SideEffects: Array.Empty<SideEffect>(),
                IsError: false,
                ErrorMessage: null));
        }

        public ValueTask DisposeAsync()
        {
            DisposeCallCount++;
            _disposalLog?.Add(_label);
            return default;
        }
    }
}
#endif
