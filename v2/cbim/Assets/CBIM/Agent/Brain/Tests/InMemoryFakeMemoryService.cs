#if UNITY_INCLUDE_TESTS
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using CBIM.Memory;

namespace CBIM.AgentSystem.Brain.Tests
{
    /// <summary>
    /// 进程内 <see cref="IMemoryService"/> 桩——基于 Dictionary 实装全部 5 个数据方法。
    /// 用于脑区 / Agent / Channel 装配链测试：不动文件系统、不接外部存储、
    /// DisposeAsync 调用计数可被外部 disposal log 追踪。
    /// </summary>
    internal sealed class InMemoryFakeMemoryService : IMemoryService
    {
        private readonly Dictionary<string, MemoryEntry> _entries = new Dictionary<string, MemoryEntry>(StringComparer.Ordinal);
        private readonly List<string> _disposalLog;
        private readonly string _label;

        public int DisposeCallCount { get; private set; }

        /// <summary>构造无 disposal log 的实例——只关心数据面。</summary>
        public InMemoryFakeMemoryService()
            : this(disposalLog: null, label: "memory")
        {
        }

        /// <summary>构造带 disposal log 的实例——dispose 时按顺序 append <paramref name="label"/>。</summary>
        public InMemoryFakeMemoryService(List<string> disposalLog, string label)
        {
            _disposalLog = disposalLog;
            _label = label ?? "memory";
        }

        public void Write(MemoryEntry entry)
        {
            if (entry == null) throw new ArgumentNullException(nameof(entry));
            if (string.IsNullOrWhiteSpace(entry.Id))
                throw new ArgumentException("entry.Id 不能为空", nameof(entry));
            _entries[entry.Id] = entry;
        }

        public MemoryEntry Get(string id)
        {
            if (string.IsNullOrWhiteSpace(id)) return null;
            return _entries.TryGetValue(id, out var e) ? e : null;
        }

        public IReadOnlyList<MemoryEntry> Query(string text, int topK)
        {
            if (string.IsNullOrWhiteSpace(text) || topK <= 0) return Array.Empty<MemoryEntry>();
            // 纯子串匹配——测试桩不追求算法保真度。
            return _entries.Values
                .Where(e => (e.Text ?? string.Empty).IndexOf(text, StringComparison.OrdinalIgnoreCase) >= 0)
                .Take(topK)
                .ToList();
        }

        public IReadOnlyList<MemoryEntry> Scan(MemoryScanFilter filter)
        {
            IEnumerable<MemoryEntry> q = _entries.Values;
            if (filter != null)
            {
                if (!string.IsNullOrWhiteSpace(filter.SourceEquals))
                    q = q.Where(e => string.Equals(e.Source, filter.SourceEquals, StringComparison.Ordinal));
                if (filter.Since.HasValue)
                    q = q.Where(e => e.CreatedAt >= filter.Since.Value);
            }
            return q.OrderByDescending(e => e.CreatedAt).ToList();
        }

        public MemoryStats Stats()
        {
            if (_entries.Count == 0) return new MemoryStats(0, null, null);
            DateTime? oldest = null;
            DateTime? newest = null;
            foreach (var e in _entries.Values)
            {
                if (!oldest.HasValue || e.CreatedAt < oldest.Value) oldest = e.CreatedAt;
                if (!newest.HasValue || e.CreatedAt > newest.Value) newest = e.CreatedAt;
            }
            return new MemoryStats(_entries.Count, oldest, newest);
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
