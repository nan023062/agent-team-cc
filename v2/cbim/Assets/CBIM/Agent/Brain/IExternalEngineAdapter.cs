using System;
using System.Threading;
using System.Threading.Tasks;

namespace CBIM.AgentSystem.Brain
{
    /// <summary>
    /// 把对外部 agent 引擎（Claude Code / Cursor / Cline 等）的调用收敛到一处。
    /// <see cref="ExternalMotorCortex"/> 在 InvokeAsync 路径上仅与本接口对话——
    /// 具体 Adapter（如 ClaudeCodeEngineAdapter）由后续切片实装。
    ///
    /// <para>提交 / 等待二阶段拆分的原因：外部引擎多为 subprocess 或异步作业，
    /// 同步 await 会长时间持有 CancellationToken；二阶段可让上游灵活控制超时 /
    /// 取消 / 进度上报。</para>
    ///
    /// <para>实现期约定：</para>
    /// <list type="bullet">
    ///   <item>SubmitAsync 必须返回一个对实现内部唯一的 jobId（用于 AwaitResultAsync 配对）。</item>
    ///   <item>AwaitResultAsync 失败时返回 <c>IsError=true</c> 的 <see cref="BrainOutcome"/>，<b>不</b>抛出。</item>
    ///   <item>DisposeAsync 必须强制收尾——杀掉所有未退出的外部进程、关闭桥接 server。</item>
    /// </list>
    /// </summary>
    public interface IExternalEngineAdapter : IAsyncDisposable
    {
        /// <summary>
        /// 提交一次外部引擎调用。返回引擎内部唯一的 jobId。
        /// </summary>
        Task<string> SubmitAsync(BrainInvocation invocation, CancellationToken ct);

        /// <summary>
        /// 等待指定 jobId 的最终结果。
        /// 失败时返回 <c>IsError=true</c> 的 <see cref="BrainOutcome"/>，不抛。
        /// </summary>
        Task<BrainOutcome> AwaitResultAsync(string jobId, CancellationToken ct);
    }
}
