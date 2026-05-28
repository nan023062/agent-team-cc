using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using CBIM.Storage;

namespace CBIM.Skills
{
    /// <summary>
    /// <see cref="ISkillStore"/> 的默认本地文件后端实现。
    ///
    /// 落盘形态：<c>&lt;root&gt;/&lt;subdir&gt;/&lt;id&gt;.json</c>（默认 subdir = "skills"）。
    /// 一条 SkillDescriptor 一个文件，无 index——构造时全量扫描进内存索引，
    /// <see cref="Put"/> / <see cref="Delete"/> 同步更新索引 + 原子落盘。
    ///
    /// 线程安全：所有公共方法在内部锁下访问索引；落盘走 <see cref="FileBackend.WriteAtomic"/>。
    /// 调用方可在任意线程并发调用。
    /// </summary>
    public sealed class FileSkillStore : ISkillStore
    {
        private const string DefaultSubDir = "skills";

        private static readonly JsonSerializerOptions JsonOptions = new JsonSerializerOptions
        {
            WriteIndented = true,
        };

        private readonly FileBackend _storage;
        private readonly string _subdir;
        private readonly object _gate = new object();
        private readonly Dictionary<string, SkillDescriptor> _entries =
            new Dictionary<string, SkillDescriptor>(StringComparer.Ordinal);

        /// <summary>
        /// 构造并从 <c>&lt;root&gt;/&lt;subdir&gt;/</c> 扫描全量条目进内存。
        /// 目录不存在时静默通过——首次 <see cref="Put"/> 会触发创建。
        /// </summary>
        /// <param name="backend">文件后端（共享）。根目录由调用方注入。</param>
        /// <param name="subdir">落盘子目录名，默认 "skills"。</param>
        public FileSkillStore(FileBackend backend, string subdir = DefaultSubDir)
        {
            _storage = backend ?? throw new ArgumentNullException(nameof(backend));
            if (string.IsNullOrWhiteSpace(subdir))
                throw new ArgumentException("subdir 不能为空", nameof(subdir));
            _subdir = subdir;

            LoadFromDisk();
        }

        // ===== ISkillStore =====

        public SkillDescriptor Get(string id)
        {
            if (string.IsNullOrWhiteSpace(id)) return null;
            lock (_gate)
            {
                return _entries.TryGetValue(id, out var d) ? d : null;
            }
        }

        public IReadOnlyList<SkillDescriptor> List()
        {
            lock (_gate)
            {
                return _entries.Values.ToList();
            }
        }

        public IReadOnlyList<SkillDescriptor> Query(string text, int topK)
        {
            if (topK <= 0) return Array.Empty<SkillDescriptor>();
            if (string.IsNullOrWhiteSpace(text)) return Array.Empty<SkillDescriptor>();

            List<SkillDescriptor> snapshot;
            lock (_gate)
            {
                snapshot = _entries.Values.ToList();
            }

            var matches = new List<SkillDescriptor>();
            foreach (var d in snapshot)
            {
                if (Matches(d, text))
                {
                    matches.Add(d);
                    if (matches.Count >= topK) break;
                }
            }
            return matches;
        }

        public void Put(SkillDescriptor descriptor)
        {
            if (descriptor == null) throw new ArgumentNullException(nameof(descriptor));

            lock (_gate)
            {
                _entries[descriptor.Id] = descriptor;
                PersistEntry(descriptor);
            }
        }

        public bool Delete(string id)
        {
            if (string.IsNullOrWhiteSpace(id)) return false;

            lock (_gate)
            {
                if (!_entries.Remove(id)) return false;
                _storage.Delete(EntryPath(id));
                return true;
            }
        }

        // ===== 内部：路径 / 序列化 / 加载 =====

        private string EntryPath(string id) =>
            _storage.ResolveCbimPath(_subdir, id + ".json");

        private void PersistEntry(SkillDescriptor descriptor)
        {
            var dto = SkillDto.From(descriptor);
            string json = JsonSerializer.Serialize(dto, JsonOptions);
            _storage.WriteAtomic(EntryPath(descriptor.Id), json);
        }

        private void LoadFromDisk()
        {
            // 用 ResolveCbimPath 产出一个 dummy 条目路径，从中提取目录。
            // ResolveCbimPath 内部确保父目录存在，但只到 parent；这里我们要的就是 parent。
            string probe = EntryPath("__probe");
            string dir = Path.GetDirectoryName(probe);
            if (string.IsNullOrEmpty(dir) || !Directory.Exists(dir)) return;

            foreach (var file in Directory.EnumerateFiles(dir, "*.json", SearchOption.TopDirectoryOnly))
            {
                var loaded = TryLoadEntry(file);
                if (loaded != null) _entries[loaded.Id] = loaded;
            }
        }

        private SkillDescriptor TryLoadEntry(string path)
        {
            string json = _storage.ReadOrNull(path);
            if (string.IsNullOrEmpty(json)) return null;

            try
            {
                var dto = JsonSerializer.Deserialize<SkillDto>(json, JsonOptions);
                return dto?.ToDescriptor();
            }
            catch (JsonException)
            {
                // 损坏文件静默跳过——避免一个坏文件阻塞整个 store 启动。
                return null;
            }
            catch (ArgumentException)
            {
                // DTO 字段缺失被 SkillDescriptor 构造器拒绝时也走这里。
                return null;
            }
        }

        private static bool Matches(SkillDescriptor d, string text)
        {
            return ContainsIgnoreCase(d.Id, text)
                || ContainsIgnoreCase(d.Name, text)
                || ContainsIgnoreCase(d.Description, text)
                || ContainsIgnoreCase(d.Content, text);
        }

        private static bool ContainsIgnoreCase(string haystack, string needle)
        {
            if (string.IsNullOrEmpty(haystack)) return false;
            return haystack.IndexOf(needle, StringComparison.OrdinalIgnoreCase) >= 0;
        }

        // 落盘 DTO——隔离 SkillDescriptor（构造器有校验，不能直接被反序列化 set）。
        private sealed class SkillDto
        {
            public string Id { get; set; }
            public string Name { get; set; }
            public string Description { get; set; }
            public string Content { get; set; }

            public static SkillDto From(SkillDescriptor d) => new SkillDto
            {
                Id = d.Id,
                Name = d.Name,
                Description = d.Description,
                Content = d.Content,
            };

            public SkillDescriptor ToDescriptor() =>
                new SkillDescriptor(Id, Name, Description, Content);
        }
    }
}
