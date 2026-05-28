using System;
using System.Collections.Generic;

namespace CBIM.AgentSystem.Brain
{
    /// <summary>
    /// 进程内 <see cref="IBrainRegistry"/> 默认实现——一把粗锁保护字典。
    ///
    /// <para>选粗锁不选 <see cref="System.Collections.Concurrent.ConcurrentDictionary{TKey,TValue}"/>
    /// 的原因：注册 / 撤销远低频（仅装配期 + Dream 裂变期），但 <see cref="All"/> 调用方期望
    /// 一个稳定快照而非弱一致视图——粗锁路径下生成快照副本最简单。</para>
    /// </summary>
    public sealed class InMemoryBrainRegistry : IBrainRegistry
    {
        private readonly Dictionary<string, BrainBase> _brains = new Dictionary<string, BrainBase>(StringComparer.Ordinal);
        private readonly object _lock = new object();

        /// <inheritdoc/>
        public void RegisterBrain(BrainBase brain)
        {
            if (brain == null)
                throw new ArgumentNullException(nameof(brain));

            lock (_lock)
            {
                if (_brains.ContainsKey(brain.BrainId))
                    throw new InvalidOperationException(
                        $"BrainId '{brain.BrainId}' 已注册——「BrainId 唯一」铁律违反。");

                _brains.Add(brain.BrainId, brain);
            }
        }

        /// <inheritdoc/>
        public bool UnregisterBrain(string brainId)
        {
            if (string.IsNullOrWhiteSpace(brainId))
                return false;

            lock (_lock)
            {
                return _brains.Remove(brainId);
            }
        }

        /// <inheritdoc/>
        public BrainBase? Find(string brainId)
        {
            if (string.IsNullOrWhiteSpace(brainId))
                return null;

            lock (_lock)
            {
                return _brains.TryGetValue(brainId, out var b) ? b : null;
            }
        }

        /// <inheritdoc/>
        public IReadOnlyList<BrainBase> All()
        {
            lock (_lock)
            {
                // 返回快照副本——调用方拿到的列表不会随后续 Register / Unregister 改变。
                var snapshot = new BrainBase[_brains.Count];
                _brains.Values.CopyTo(snapshot, 0);
                return snapshot;
            }
        }
    }
}
