using System;
using System.Threading;
using System.Threading.Tasks;
using CBIM.Memory;

namespace CBIM.AgentSystem.Brain
{
    /// <summary>
    /// ExternalMotorCortex —— 桥接外部 agent 引擎（Claude Code / Cursor / Cline 等）的运动皮层抽象。
    ///
    /// <para>「外部 AI 工具 = 会干活的肌肉」哲学的物理落地——本抽象类是 OO 层面整个
    /// CBIM 唯一允许的 External 分支点（其他脑区无 External 变体）。</para>
    ///
    /// <para>结构差异：</para>
    /// <list type="bullet">
    ///   <item><see cref="BrainBase.Agent"/> 在本路径下为 <c>null</c>（外部引擎自带 LLM，
    ///         不通过 msai 装配）——基类已为此分支预留。</item>
    ///   <item>因 Agent 为 null，<see cref="BrainBase.InvokeAsync"/> 默认实现会抛出
    ///         InvalidOperationException——本类<b>必须</b>重写为 Adapter 路径。</item>
    /// </list>
    /// </summary>
    public abstract class ExternalMotorCortex : MotorCortex
    {
        /// <summary>把对外部引擎的调用收敛到一处——子类通过它发起 Submit / Await。</summary>
        protected IExternalEngineAdapter Adapter { get; }

        /// <summary>Memory 与外部引擎的共享桥模式——从描述符透传。</summary>
        public MemoryShareMode ShareMode { get; }

        protected ExternalMotorCortex(
            ExternalMotorCortexDescriptor descriptor,
            IMemoryService memory,
            IExternalEngineAdapter adapter,
            IPrefrontalCallback callback)
            : base(descriptor?.BrainId ?? throw new ArgumentNullException(nameof(descriptor)),
                   descriptor,
                   memory,
                   chatClient: null,
                   callback)
        {
            Adapter = adapter ?? throw new ArgumentNullException(nameof(adapter),
                "ExternalMotorCortex.Adapter 不允许 null——外部路径的 InvokeAsync 全靠它。");
            ShareMode = descriptor.MemoryShareMode;
        }

        /// <summary>
        /// 重写默认 InvokeAsync——走 Adapter 二阶段路径。
        /// Adapter 任一阶段异常都被收敛为 <c>IsError=true</c> 的 <see cref="BrainOutcome"/>，
        /// 不向上抛出（主脑只关心结果，不应被外部引擎的异常打断调度循环）。
        /// </summary>
        public override async Task<BrainOutcome> InvokeAsync(BrainInvocation invocation, CancellationToken ct)
        {
            if (invocation == null)
                throw new ArgumentNullException(nameof(invocation));

            try
            {
                var jobId = await Adapter.SubmitAsync(invocation, ct).ConfigureAwait(false);
                return await Adapter.AwaitResultAsync(jobId, ct).ConfigureAwait(false);
            }
            catch (OperationCanceledException)
            {
                // 取消语义直传——上游可能在等同一个 token 触发。
                throw;
            }
            catch (Exception ex)
            {
                return new BrainOutcome(
                    Summary: string.Empty,
                    StructuredOutput: null,
                    SideEffects: Array.Empty<SideEffect>(),
                    IsError: true,
                    ErrorMessage: $"ExternalMotorCortex({BrainId}) 桥接失败: {ex.Message}");
            }
        }

        /// <inheritdoc/>
        public override async ValueTask DisposeAsync()
        {
            await Adapter.DisposeAsync().ConfigureAwait(false);
        }
    }
}
