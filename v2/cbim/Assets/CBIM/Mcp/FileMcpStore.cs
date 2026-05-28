using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Serialization;
using CBIM.Storage;

namespace CBIM.Mcp
{
    /// <summary>
    /// <see cref="IMcpStore"/> 的默认本地文件后端实现。
    ///
    /// 落盘形态：<c>&lt;root&gt;/&lt;subdir&gt;/&lt;id&gt;.json</c>（默认 subdir = "mcps"）。
    /// 一条 McpDescriptor 一个文件，无 index——构造时全量扫描进内存索引，
    /// <see cref="Put"/> / <see cref="Delete"/> 同步更新索引 + 原子落盘。
    ///
    /// 多态 JSON：McpDescriptor 是抽象基类（StdioMcpDescriptor / HttpMcpDescriptor 两子类），
    /// 使用 <c>"transport"</c> 鉴别字段（值为 <see cref="McpTransportKind"/> 字符串）做
    /// 序列化分派。设计时为后补子类预留——增子类时只需在 <see cref="McpDescriptorConverter"/>
    /// 内加一条 switch 分支即可。
    ///
    /// 线程安全：所有公共方法在内部锁下访问索引；落盘走 <see cref="FileBackend.WriteAtomic"/>。
    /// 调用方可在任意线程并发调用。
    /// </summary>
    public sealed class FileMcpStore : IMcpStore
    {
        private const string DefaultSubDir = "mcps";

        private static readonly JsonSerializerOptions JsonOptions = BuildJsonOptions();

        private readonly FileBackend _storage;
        private readonly string _subdir;
        private readonly object _gate = new object();
        private readonly Dictionary<string, McpDescriptor> _entries =
            new Dictionary<string, McpDescriptor>(StringComparer.Ordinal);

        /// <summary>
        /// 构造并从 <c>&lt;root&gt;/&lt;subdir&gt;/</c> 扫描全量条目进内存。
        /// 目录不存在时静默通过——首次 <see cref="Put"/> 会触发创建。
        /// </summary>
        /// <param name="backend">文件后端（共享）。根目录由调用方注入。</param>
        /// <param name="subdir">落盘子目录名，默认 "mcps"。</param>
        public FileMcpStore(FileBackend backend, string subdir = DefaultSubDir)
        {
            _storage = backend ?? throw new ArgumentNullException(nameof(backend));
            if (string.IsNullOrWhiteSpace(subdir))
                throw new ArgumentException("subdir 不能为空", nameof(subdir));
            _subdir = subdir;

            LoadFromDisk();
        }

        // ===== IMcpStore =====

        public McpDescriptor Get(string id)
        {
            if (string.IsNullOrWhiteSpace(id)) return null;
            lock (_gate)
            {
                return _entries.TryGetValue(id, out var d) ? d : null;
            }
        }

        public IReadOnlyList<McpDescriptor> List()
        {
            lock (_gate)
            {
                return _entries.Values.ToList();
            }
        }

        public IReadOnlyList<McpDescriptor> Query(string text, int topK)
        {
            if (topK <= 0) return Array.Empty<McpDescriptor>();
            if (string.IsNullOrWhiteSpace(text)) return Array.Empty<McpDescriptor>();

            List<McpDescriptor> snapshot;
            lock (_gate)
            {
                snapshot = _entries.Values.ToList();
            }

            var matches = new List<McpDescriptor>();
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

        public void Put(McpDescriptor descriptor)
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

        private void PersistEntry(McpDescriptor descriptor)
        {
            string json = JsonSerializer.Serialize(descriptor, JsonOptions);
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

        private McpDescriptor TryLoadEntry(string path)
        {
            string json = _storage.ReadOrNull(path);
            if (string.IsNullOrEmpty(json)) return null;

            try
            {
                return JsonSerializer.Deserialize<McpDescriptor>(json, JsonOptions);
            }
            catch (JsonException)
            {
                // 损坏文件 / 未知 transport 静默跳过——避免一个坏文件阻塞整个 store 启动。
                return null;
            }
            catch (ArgumentException)
            {
                // DTO 字段缺失被 McpDescriptor 构造器拒绝时也走这里。
                return null;
            }
        }

        private static bool Matches(McpDescriptor d, string text)
        {
            return ContainsIgnoreCase(d.Id, text)
                || ContainsIgnoreCase(d.Name, text)
                || ContainsIgnoreCase(d.Description, text);
        }

        private static bool ContainsIgnoreCase(string haystack, string needle)
        {
            if (string.IsNullOrEmpty(haystack)) return false;
            return haystack.IndexOf(needle, StringComparison.OrdinalIgnoreCase) >= 0;
        }

        private static JsonSerializerOptions BuildJsonOptions()
        {
            var options = new JsonSerializerOptions
            {
                WriteIndented = true,
            };
            options.Converters.Add(new McpDescriptorConverter());
            return options;
        }

        // ===== 多态 JSON 转换器 =====

        /// <summary>
        /// McpDescriptor 多态 JSON 转换器。
        ///
        /// 落盘形态（示例）：
        /// <code>
        /// {
        ///   "transport": "Stdio",
        ///   "id": "unity-mcp",
        ///   "name": "Unity MCP",
        ///   "description": "Unity 桥",
        ///   "command": "python",
        ///   "args": ["-m", "unity_mcp"],
        ///   "env": { "LOG_LEVEL": "debug" }
        /// }
        /// </code>
        ///
        /// 读：先读 "transport" 鉴别字段 → 分派到对应 DTO → 调子类构造器（构造器内会校验）。
        /// 写：先写 "transport" 鉴别字段 → 写基类字段 → 写子类专有字段。
        ///
        /// 不直接用 System.Text.Json 的 JsonDerivedType（需 .NET 7+），手写以兼容 Unity 的
        /// System.Text.Json 版本，且对未来补抽象子类的演进路径更显式。
        /// </summary>
        private sealed class McpDescriptorConverter : JsonConverter<McpDescriptor>
        {
            private const string TransportProperty = "transport";

            public override McpDescriptor Read(
                ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
            {
                using var document = JsonDocument.ParseValue(ref reader);
                var root = document.RootElement;

                if (root.ValueKind != JsonValueKind.Object)
                    throw new JsonException("McpDescriptor JSON 必须是对象");

                if (!TryGetTransport(root, out McpTransportKind transport))
                    throw new JsonException(
                        $"McpDescriptor JSON 缺少或无法识别 \"{TransportProperty}\" 鉴别字段");

                switch (transport)
                {
                    case McpTransportKind.Stdio:
                        return ReadStdio(root);
                    case McpTransportKind.Http:
                        return ReadHttp(root);
                    default:
                        throw new JsonException(
                            $"McpDescriptor JSON \"{TransportProperty}\" 值未支持：{transport}");
                }
            }

            public override void Write(
                Utf8JsonWriter writer, McpDescriptor value, JsonSerializerOptions options)
            {
                writer.WriteStartObject();
                writer.WriteString(TransportProperty, value.Transport.ToString());
                writer.WriteString("id", value.Id);
                writer.WriteString("name", value.Name);
                writer.WriteString("description", value.Description);

                switch (value)
                {
                    case StdioMcpDescriptor stdio:
                        WriteStdio(writer, stdio);
                        break;
                    case HttpMcpDescriptor http:
                        WriteHttp(writer, http);
                        break;
                    default:
                        throw new JsonException(
                            $"未知 McpDescriptor 子类：{value.GetType().FullName}");
                }

                writer.WriteEndObject();
            }

            // ----- transport 鉴别字段读取 -----

            private static bool TryGetTransport(JsonElement root, out McpTransportKind transport)
            {
                transport = default;
                if (!root.TryGetProperty(TransportProperty, out var prop)) return false;
                if (prop.ValueKind != JsonValueKind.String) return false;
                return Enum.TryParse(prop.GetString(), ignoreCase: true, out transport);
            }

            // ----- Stdio 子类 -----

            private static StdioMcpDescriptor ReadStdio(JsonElement root)
            {
                string id = GetRequiredString(root, "id");
                string name = GetRequiredString(root, "name");
                string description = GetRequiredString(root, "description");
                string command = GetRequiredString(root, "command");
                var args = ReadStringArray(root, "args");
                var env = ReadStringMap(root, "env");

                return new StdioMcpDescriptor(id, name, description, command, args, env);
            }

            private static void WriteStdio(Utf8JsonWriter writer, StdioMcpDescriptor stdio)
            {
                writer.WriteString("command", stdio.Command);

                writer.WriteStartArray("args");
                foreach (var arg in stdio.Args)
                    writer.WriteStringValue(arg);
                writer.WriteEndArray();

                writer.WriteStartObject("env");
                foreach (var kv in stdio.Env)
                    writer.WriteString(kv.Key, kv.Value);
                writer.WriteEndObject();
            }

            // ----- Http 子类 -----

            private static HttpMcpDescriptor ReadHttp(JsonElement root)
            {
                string id = GetRequiredString(root, "id");
                string name = GetRequiredString(root, "name");
                string description = GetRequiredString(root, "description");
                string endpoint = GetRequiredString(root, "endpoint");
                string authToken = GetOptionalString(root, "authToken");
                var headers = ReadStringMap(root, "headers");

                return new HttpMcpDescriptor(id, name, description, endpoint, authToken, headers);
            }

            private static void WriteHttp(Utf8JsonWriter writer, HttpMcpDescriptor http)
            {
                writer.WriteString("endpoint", http.Endpoint);
                writer.WriteString("authToken", http.AuthToken ?? string.Empty);

                writer.WriteStartObject("headers");
                foreach (var kv in http.Headers)
                    writer.WriteString(kv.Key, kv.Value);
                writer.WriteEndObject();
            }

            // ----- 字段读取原语 -----

            private static string GetRequiredString(JsonElement root, string name)
            {
                if (!root.TryGetProperty(name, out var prop) || prop.ValueKind != JsonValueKind.String)
                    throw new JsonException($"McpDescriptor JSON 缺少必填字段 \"{name}\"");
                return prop.GetString();
            }

            private static string GetOptionalString(JsonElement root, string name)
            {
                if (!root.TryGetProperty(name, out var prop)) return null;
                if (prop.ValueKind == JsonValueKind.Null) return null;
                if (prop.ValueKind != JsonValueKind.String)
                    throw new JsonException($"McpDescriptor JSON 字段 \"{name}\" 必须为字符串");
                return prop.GetString();
            }

            private static List<string> ReadStringArray(JsonElement root, string name)
            {
                var list = new List<string>();
                if (!root.TryGetProperty(name, out var prop)) return list;
                if (prop.ValueKind == JsonValueKind.Null) return list;
                if (prop.ValueKind != JsonValueKind.Array)
                    throw new JsonException($"McpDescriptor JSON 字段 \"{name}\" 必须为数组");

                foreach (var item in prop.EnumerateArray())
                {
                    if (item.ValueKind != JsonValueKind.String)
                        throw new JsonException($"McpDescriptor JSON \"{name}\" 元素必须为字符串");
                    list.Add(item.GetString());
                }
                return list;
            }

            private static Dictionary<string, string> ReadStringMap(JsonElement root, string name)
            {
                var map = new Dictionary<string, string>(StringComparer.Ordinal);
                if (!root.TryGetProperty(name, out var prop)) return map;
                if (prop.ValueKind == JsonValueKind.Null) return map;
                if (prop.ValueKind != JsonValueKind.Object)
                    throw new JsonException($"McpDescriptor JSON 字段 \"{name}\" 必须为对象");

                foreach (var kv in prop.EnumerateObject())
                {
                    if (kv.Value.ValueKind != JsonValueKind.String)
                        throw new JsonException($"McpDescriptor JSON \"{name}\".{kv.Name} 必须为字符串");
                    map[kv.Name] = kv.Value.GetString();
                }
                return map;
            }
        }
    }
}
