using System;
using System.Diagnostics;
using System.Threading.Tasks;

namespace CBIM.AgentSystem.Brain.ClaudeCode
{
    /// <summary>
    /// Claude Code subprocess 作业簿记——一个 Submit 一条。
    /// 仅 <see cref="ClaudeCodeEngineAdapter"/> 内部使用。
    /// </summary>
    internal sealed class ClaudeCodeJob
    {
        /// <summary>Adapter 内部唯一 id（Guid 字符串）。</summary>
        public string JobId { get; }

        /// <summary>已启动的 CLI 进程；DisposeAsync 路径上需 Kill。</summary>
        public Process Process { get; }

        /// <summary>本作业的 transcript 文件绝对路径——stdout 流式落盘的目标。</summary>
        public string TranscriptPath { get; }

        /// <summary>触发本作业的原始 BrainInvocation——供 AwaitResultAsync 路径回看 Intent / Context。</summary>
        public BrainInvocation Invocation { get; }

        /// <summary>提交时刻——便于审计 / 超时诊断。</summary>
        public DateTimeOffset StartedAt { get; }

        /// <summary>
        /// 由 <see cref="Process.Exited"/> 事件 SetResult(ExitCode)；AwaitResultAsync await 它。
        /// 用 <see cref="TaskCreationOptions.RunContinuationsAsynchronously"/> 避免在 Exited 回调
        /// 线程上同步执行后续逻辑导致死锁。
        /// </summary>
        public TaskCompletionSource<int> ExitTcs { get; } =
            new TaskCompletionSource<int>(TaskCreationOptions.RunContinuationsAsynchronously);

        public ClaudeCodeJob(
            string jobId,
            Process process,
            string transcriptPath,
            BrainInvocation invocation,
            DateTimeOffset startedAt)
        {
            if (string.IsNullOrWhiteSpace(jobId))
                throw new ArgumentException("ClaudeCodeJob.JobId 不能为空", nameof(jobId));
            if (string.IsNullOrWhiteSpace(transcriptPath))
                throw new ArgumentException("ClaudeCodeJob.TranscriptPath 不能为空", nameof(transcriptPath));

            JobId = jobId;
            Process = process ?? throw new ArgumentNullException(nameof(process));
            TranscriptPath = transcriptPath;
            Invocation = invocation ?? throw new ArgumentNullException(nameof(invocation));
            StartedAt = startedAt;
        }
    }
}
