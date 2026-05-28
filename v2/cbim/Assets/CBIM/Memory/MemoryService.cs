using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using CBIM.Storage;

namespace CBIM.Memory
{
    /// <summary>
    /// Memory 服务（M 维度门面）——CBIM 中期记忆条目的扁平 JSON CRUD + Query。
    ///
    /// 本轮大幅瘦身后退化为「业务胶水」：
    ///   - 短期记忆 / Compaction / 向量检索 全交给 Microsoft（AgentThread / ChatHistoryProvider / VectorData）
    ///   - 本模块只持「distill 后的 MemoryEntry」一种东西
    ///   - 完全无 Task / Module / Agent 感知——这是它能跨业务跨能力的前提
    ///
    /// 落盘布局：
    ///   &lt;root&gt;/.cbim/memory/medium/&lt;id&gt;.json   ← 一条目一文件
    ///   &lt;root&gt;/.cbim/memory/index.json           ← id → { fileName, source, createdAt, tags }
    ///
    /// 同步方法——异步调用方自己包。
    /// 关键词检索为字符串子串匹配，未来挂 Microsoft VectorStore 时替换 <see cref="Query"/> 实现即可，
    /// 不抽象 IMemoryBackend。
    /// </summary>
    public sealed class MemoryService
    {
        private const string MemoryDir = ".cbim/memory";
        private const string MediumSubDir = "medium";
        private const string IndexFileName = "index.json";

        private static readonly JsonSerializerOptions JsonOptions = new JsonSerializerOptions
        {
            WriteIndented = true,
        };

        private readonly FileBackend _storage;
        private readonly object _gate = new object();
        private readonly Dictionary<string, MemoryEntry> _entries = new Dictionary<string, MemoryEntry>(StringComparer.Ordinal);

        /// <summary>
        /// 构造服务并从磁盘加载已有条目。
        /// </summary>
        /// <param name="storage">文件后端（共享）。根目录由调用方注入。</param>
        public MemoryService(FileBackend storage)
        {
            _storage = storage ?? throw new ArgumentNullException(nameof(storage));
            LoadFromDisk();
        }

        // ===== CRUD 门面 =====

        /// <summary>
        /// 写入或覆盖一条记忆条目。
        /// 落盘：先原子写 &lt;id&gt;.json，再原子写 index.json。
        /// </summary>
        public void Write(MemoryEntry entry)
        {
            if (entry == null) throw new ArgumentNullException(nameof(entry));
            if (string.IsNullOrWhiteSpace(entry.Id))
                throw new ArgumentException("MemoryEntry.Id 不能为空", nameof(entry));

            // 规范化 null 集合 → 空集合，避免反序列化分支。
            var normalized = entry with { Tags = entry.Tags ?? Array.Empty<string>() };

            lock (_gate)
            {
                _entries[normalized.Id] = normalized;
                PersistEntry(normalized);
                PersistIndex();
            }
        }

        /// <summary>按 Id 取条目。找不到返 null。</summary>
        public MemoryEntry Get(string id)
        {
            if (string.IsNullOrWhiteSpace(id)) return null;
            lock (_gate)
            {
                return _entries.TryGetValue(id, out var e) ? e : null;
            }
        }

        /// <summary>
        /// 关键词检索——返回与 <paramref name="text"/> 最匹配的前 K 条。
        ///
        /// 当前实现：忽略大小写的词条匹配，按命中词数排序；命中数相同按 CreatedAt 倒序。
        /// 未来如挂 Microsoft VectorStore，仅此方法体替换，签名不变。
        /// </summary>
        public IReadOnlyList<MemoryEntry> Query(string text, int topK)
        {
            if (topK <= 0) return Array.Empty<MemoryEntry>();
            if (string.IsNullOrWhiteSpace(text)) return Array.Empty<MemoryEntry>();

            var tokens = Tokenize(text);
            if (tokens.Count == 0) return Array.Empty<MemoryEntry>();

            List<MemoryEntry> snapshot;
            lock (_gate)
            {
                snapshot = _entries.Values.ToList();
            }

            var scored = new List<(MemoryEntry Entry, int Score)>(snapshot.Count);
            foreach (var entry in snapshot)
            {
                int score = ScoreEntry(entry, tokens);
                if (score > 0)
                {
                    scored.Add((entry, score));
                }
            }

            scored.Sort((a, b) =>
            {
                int byScore = b.Score.CompareTo(a.Score);
                if (byScore != 0) return byScore;
                return b.Entry.CreatedAt.CompareTo(a.Entry.CreatedAt);
            });

            int take = Math.Min(topK, scored.Count);
            var result = new List<MemoryEntry>(take);
            for (int i = 0; i < take; i++) result.Add(scored[i].Entry);
            return result;
        }

        /// <summary>按结构化过滤条件枚举条目（AND 各字段）。结果按 CreatedAt 倒序。</summary>
        public IReadOnlyList<MemoryEntry> Scan(MemoryScanFilter filter)
        {
            List<MemoryEntry> snapshot;
            lock (_gate)
            {
                snapshot = _entries.Values.ToList();
            }

            IEnumerable<MemoryEntry> q = snapshot;

            if (filter != null)
            {
                if (!string.IsNullOrEmpty(filter.SourceEquals))
                {
                    var src = filter.SourceEquals;
                    q = q.Where(e => string.Equals(e.Source, src, StringComparison.Ordinal));
                }

                if (filter.TagsAny != null && filter.TagsAny.Count > 0)
                {
                    var wanted = new HashSet<string>(filter.TagsAny, StringComparer.OrdinalIgnoreCase);
                    q = q.Where(e =>
                    {
                        if (e.Tags == null) return false;
                        for (int i = 0; i < e.Tags.Count; i++)
                        {
                            if (wanted.Contains(e.Tags[i])) return true;
                        }
                        return false;
                    });
                }

                if (filter.Since.HasValue)
                {
                    var since = filter.Since.Value;
                    q = q.Where(e => e.CreatedAt >= since);
                }
            }

            return q.OrderByDescending(e => e.CreatedAt).ToList();
        }

        /// <summary>仓库聚合快照——总数 + 最早 / 最新 CreatedAt。</summary>
        public MemoryStats Stats()
        {
            lock (_gate)
            {
                if (_entries.Count == 0)
                {
                    return new MemoryStats(0, null, null);
                }

                DateTime oldest = DateTime.MaxValue;
                DateTime newest = DateTime.MinValue;
                foreach (var e in _entries.Values)
                {
                    if (e.CreatedAt < oldest) oldest = e.CreatedAt;
                    if (e.CreatedAt > newest) newest = e.CreatedAt;
                }
                return new MemoryStats(_entries.Count, oldest, newest);
            }
        }

        // ===== 内部：加载 / 持久化 =====

        private string EntryPath(string id) =>
            _storage.ResolveCbimPath(MemoryDir, MediumSubDir, id + ".json");

        private string IndexPath() =>
            _storage.ResolveCbimPath(MemoryDir, IndexFileName);

        private void LoadFromDisk()
        {
            // 优先按 index.json 加载；index 缺失或损坏时退回扫描 medium/ 目录重建。
            string indexPath = IndexPath();
            string indexJson = _storage.ReadOrNull(indexPath);
            bool indexUsable = false;

            if (!string.IsNullOrEmpty(indexJson))
            {
                try
                {
                    var index = JsonSerializer.Deserialize<Dictionary<string, IndexRecord>>(indexJson, JsonOptions);
                    if (index != null)
                    {
                        foreach (var kv in index)
                        {
                            var loaded = TryLoadEntry(kv.Key);
                            if (loaded != null) _entries[loaded.Id] = loaded;
                        }
                        indexUsable = true;
                    }
                }
                catch (JsonException)
                {
                    indexUsable = false;
                }
            }

            if (!indexUsable)
            {
                RebuildFromDirectory();
                if (_entries.Count > 0) PersistIndex();
            }
        }

        private void RebuildFromDirectory()
        {
            string mediumDir = Path.GetDirectoryName(EntryPath("__probe"));
            if (string.IsNullOrEmpty(mediumDir) || !Directory.Exists(mediumDir)) return;

            foreach (var file in Directory.EnumerateFiles(mediumDir, "*.json", SearchOption.TopDirectoryOnly))
            {
                string id = Path.GetFileNameWithoutExtension(file);
                var loaded = TryLoadEntry(id);
                if (loaded != null) _entries[loaded.Id] = loaded;
            }
        }

        private MemoryEntry TryLoadEntry(string id)
        {
            string path = EntryPath(id);
            string json = _storage.ReadOrNull(path);
            if (string.IsNullOrEmpty(json)) return null;
            try
            {
                return JsonSerializer.Deserialize<MemoryEntry>(json, JsonOptions);
            }
            catch (JsonException)
            {
                return null;
            }
        }

        private void PersistEntry(MemoryEntry entry)
        {
            string json = JsonSerializer.Serialize(entry, JsonOptions);
            _storage.WriteAtomic(EntryPath(entry.Id), json);
        }

        private void PersistIndex()
        {
            var snapshot = new Dictionary<string, IndexRecord>(_entries.Count, StringComparer.Ordinal);
            foreach (var e in _entries.Values)
            {
                snapshot[e.Id] = new IndexRecord
                {
                    FileName = e.Id + ".json",
                    Source = e.Source,
                    CreatedAt = e.CreatedAt,
                    Tags = e.Tags,
                };
            }
            string json = JsonSerializer.Serialize(snapshot, JsonOptions);
            _storage.WriteAtomic(IndexPath(), json);
        }

        // ===== 检索辅助 =====

        private static int ScoreEntry(MemoryEntry entry, IReadOnlyList<string> tokens)
        {
            int score = 0;
            string text = entry.Text ?? string.Empty;
            for (int i = 0; i < tokens.Count; i++)
            {
                string tok = tokens[i];
                if (text.IndexOf(tok, StringComparison.OrdinalIgnoreCase) >= 0) score++;
                if (entry.Tags != null)
                {
                    for (int j = 0; j < entry.Tags.Count; j++)
                    {
                        if (string.Equals(entry.Tags[j], tok, StringComparison.OrdinalIgnoreCase))
                        {
                            score++;
                            break;
                        }
                    }
                }
            }
            return score;
        }

        private static readonly char[] TokenSeparators = new[]
        {
            ' ', '\t', '\n', '\r', ',', '.', ';', ':', '!', '?', '/', '\\', '|',
            '(', ')', '[', ']', '{', '}', '<', '>', '"', '\'', '`',
        };

        private static IReadOnlyList<string> Tokenize(string text)
        {
            var parts = text.Split(TokenSeparators, StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length == 0) return Array.Empty<string>();

            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            var result = new List<string>(parts.Length);
            for (int i = 0; i < parts.Length; i++)
            {
                var p = parts[i];
                if (p.Length == 0) continue;
                if (seen.Add(p)) result.Add(p);
            }
            return result;
        }

        // ===== index.json 记录形 =====

        private sealed class IndexRecord
        {
            public string FileName { get; set; }
            public string Source { get; set; }
            public DateTime CreatedAt { get; set; }
            public IReadOnlyList<string> Tags { get; set; }
        }
    }
}
