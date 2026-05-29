using System;
using System.Threading.Tasks;
using CBIM.AgentSystem.Brain;

namespace CBIM.AgentSystem.Kernel.Synapse
{
    /// <summary>
    /// 默认 <see cref="IPrefrontalCallback"/> 连接器——把子脑区上报路由到主脑实例
    /// 或主脑 Neuron 提供的处理委托。
    ///
    /// <para>设计意图：把「主脑如何接收上报」解耦为两个函数指针，避免本适配器与
    /// 具体的 <c>PrefrontalCortex</c> 类型直接耦合（K1 铁律：Synapse 不感知具体脑区类型）。</para>
    ///
    /// <para>本适配器是「fire-and-forget」语义：构造方提供的 <see cref="_onOutcome"/> /
    /// <see cref="_onProgress"/> 返回 <see cref="Task"/>，但本类的回报方法 (<see cref="ReportOutcome"/> /
    /// <see cref="ReportProgress"/>) 是同步签名——内部不 await。子脑区上报后立即返回，
    /// 主脑端的实际处理是异步进行的。这一选择匹配 <see cref="IPrefrontalCallback"/> 接口
    /// 「极小化、非阻塞」的设计目标——避免子脑区因等待主脑端处理而阻塞自身的执行流。</para>
    /// </summary>
    public sealed class PrefrontalCallbackAdapter : IPrefrontalCallback
    {
        private readonly Func<string, BrainOutcome, Task> _onOutcome;
        private readonly Func<string, string, Task>? _onProgress;

        /// <summary>
        /// 构造一个回调适配器。
        /// </summary>
        /// <param name="onOutcome">最终产出处理委托——子脑区调 <see cref="ReportOutcome"/> 时被触发。不为 null。</param>
        /// <param name="onProgress">可选的进度处理委托——为 null 时进度上报被静默丢弃（接口允许丢弃语义）。</param>
        public PrefrontalCallbackAdapter(
            Func<string, BrainOutcome, Task> onOutcome,
            Func<string, string, Task>? onProgress = null)
        {
            _onOutcome = onOutcome ?? throw new ArgumentNullException(nameof(onOutcome));
            _onProgress = onProgress;
        }

        /// <inheritdoc/>
        public void ReportProgress(string brainId, string message)
        {
            if (_onProgress == null)
                return;
            if (string.IsNullOrWhiteSpace(brainId))
                throw new ArgumentException("brainId 不能为空", nameof(brainId));

            // fire-and-forget：不 await，由主脑端自决处理时机；忽略返回 Task。
            _ = _onProgress(brainId, message ?? string.Empty);
        }

        /// <inheritdoc/>
        public void ReportOutcome(string brainId, BrainOutcome outcome)
        {
            if (string.IsNullOrWhiteSpace(brainId))
                throw new ArgumentException("brainId 不能为空", nameof(brainId));
            if (outcome == null)
                throw new ArgumentNullException(nameof(outcome));

            // fire-and-forget：见类注释。
            _ = _onOutcome(brainId, outcome);
        }
    }
}
