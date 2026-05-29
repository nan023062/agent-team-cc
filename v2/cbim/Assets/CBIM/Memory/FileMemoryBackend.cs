using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;
using CBIM.Storage;

namespace CBIM.Memory
{
    /// <summary>
    /// <see cref="IMemoryService"/> 的本地文件后端实现——CBIM 中期记忆条目的扁平 JSON CRUD + Query。
    ///
    /// 本轮大幅瘦身后退化为「业务胶水」：
    ///   - 短期记忆 / Compaction / 向量检索 全交给 Microsoft（AgentThread / ChatHistoryProvider / VectorData）
    ///   - 本模块只持「distill 后的 MemoryEntry」一种东西
    ///   - 完全无 Task / Module / Agent 感知——这是它能跨业务跨能力的前提
    ///
    /// 落盘布局（subDir 默认 <c>"memory/medium"</c>）：
    ///   &lt;root&gt;/.cbim/&lt;subDir&gt;/&lt;id&gt;.json   ← 一条目一文件
    ///   &lt;root&gt;/.cbim/&lt;subDirParent&gt;/index.json ← id → { fileName, source, createdAt, tags }
    ///
    /// 同步方法——异步调用方自己包。<see cref="DisposeAsync"/> 仅为 <see cref="IAsyncDisposable"/>
    /// 契约提供，本实现无异步资源可释（返回完成的 <see cref="ValueTask"/>），多次调用幂等。
    /// 关键词检索为字符串子串匹配，未来挂 Microsoft VectorStore 时换一个 <see cref="IMemoryService"/> 实现即可。
    /// </summary>
    public sealed class FileMemoryBackend : IMemoryService
    {
        private const string CbimDir = ".cbim";
        private const string IndexFileName = "index.json";
        private const string DefaultSubDir = "memory/medium";

        private static readonly JsonSerializerOptions JsonOptions = new JsonSerializerOptions
        {
            WriteIndented = true,
        };

        private readonly FileBackend _storage;
        private readonly string _subDir;
        private readonly string _indexParentSubDir;
        private readonly object _gate = new object();
        private readonly Dictionary<string, MemoryEntry> _entries = new Dictionary<string, MemoryEntry>(StringComparer.Ordinal);
        private bool _disposed;

        /// <summary>
        /// 构造服务并从磁盘加载已有条目。
        /// </summary>
        /// <param name="storage">文件后端（共享）。根目录由调用方注入。</param>
        /// <param name="subDir">
        /// 条目落盘相对 <c>.cbim/</c> 的子目录，默认 <c>"memory/medium"</c>——
        /// 保持与历史落盘布局一致。<c>index.json</c> 放在该子目录的父目录下。
        /// 允许 <c>/</c> 或 <c>\</c> 分隔多级。
        /// </param>
        public FileMemoryBackend(FileBackend storage, string subDir = DefaultSubDir)
        {
            _storage = storage ?? throw new ArgumentNullException(nameof(storage));
            if (string.IsNullOrWhiteSpace(subDir))
                throw new ArgumentException("subDir 不能为空", nameof(subDir));

            _subDir = subDir.Replace('\\', '/').Trim('/');
            if (_subDir.Length == 0)
                throw new ArgumentException("subDir 不能为空", nameof(subDir));

            int lastSlash = _subDir.LastIndexOf('/');
            _indexParentSubDir = lastSlash > 0 ? _subDir.Substring(0, lastSlash) : string.Empty;

            LoadFromDisk();
        }

        // ===== CRUD 门面 =====

        /// <inheritdoc />
        public void Write(MemoryEntry entry)
        {
            if (entry == null) throw new ArgumentNullException(nameof(entry));
            if (string.IsNullOrWhiteSpace(entry.Id))
                throw new ArgumentException("MemoryEntry.Id 不能为空", nameof(entry));

            // 规范化 null 集合 → 空集合，避免反序列化分支。
            var normalized = new MemoryEntry(
                entry.Id,
                entry.Source,
                entry.CreatedAt,
                entry.Text,
                entry.Tags ?? Array.Empty<string>());

            lock (_gate)
            {
                _entries[normalized.Id] = normalized;
                PersistEntry(normalized);
                PersistIndex();
            }
        }

        /// <inheritdoc />
        public MemoryEntry Get(string id)
        {
            if (string.IsNullOrWhiteSpace(id)) return null;
            lock (_gate)
            {
                return _entries.TryGetValue(id, out var e) ? e : null;
            }
        }

        /// <inheritdoc />
        /// <remarks>
        /// 当前实现：忽略大小写的词条匹配，按命中词数排序；命中数相同按 <see cref="MemoryEntry.CreatedAt"/> 倒序。
        /// </remarks>
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

        /// <inheritdoc />
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

        /// <inheritdoc />
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

        /// <summary>
        /// 释放资源——本实现无异步资源可释。仅清空内存缓存以释引用，幂等：多次调用不抛。
        /// </summary>
        public ValueTask DisposeAsync()
        {
            lock (_gate)
            {
                if (_disposed) return default;
                _entries.Clear();
                _disposed = true;
            }
            return default;
        }

        // ===== 内部：加载 / 持久化 =====

        private string EntryPath(string id)
        {
            // 把 subDir 拆段后交给 ResolveCbimPath，复用其分隔符 / 根目录处理。
            var segments = _subDir.Split(new[] { '/' }, StringSplitOptions.RemoveEmptyEntries);
            var all = new string[segments.Length + 2];
            all[0] = CbimDir;
            Array.Copy(segments, 0, all, 1, segments.Length);
            all[all.Length - 1] = id + ".json";
            return _storage.ResolveCbimPath(all);
        }

        private string IndexPath()
        {
            if (_indexParentSubDir.Length == 0)
            {
                return _storage.ResolveCbimPath(CbimDir, IndexFileName);
            }
            var segments = _indexParentSubDir.Split(new[] { '/' }, StringSplitOptions.RemoveEmptyEntries);
            var all = new string[segments.Length + 2];
            all[0] = CbimDir;
            Array.Copy(segments, 0, all, 1, segments.Length);
            all[all.Length - 1] = IndexFileName;
            return _storage.ResolveCbimPath(all);
        }

        private void LoadFromDisk()
        {
            // 优先按 index.json 加载；index 缺失或损坏时退回扫描条目目录重建。
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
            string entryDir = Path.GetDirectoryName(EntryPath("__probe"));
            if (string.IsNullOrEmpty(entryDir) || !Directory.Exists(entryDir)) return;

            foreach (var file in Directory.EnumerateFiles(entryDir, "*.json", SearchOption.TopDirectoryOnly))
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
