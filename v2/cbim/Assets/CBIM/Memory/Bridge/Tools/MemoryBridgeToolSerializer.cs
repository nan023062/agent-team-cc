using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text.Json.Nodes;

namespace CBIM.Memory.Bridge.Tools
{
    /// <summary>
    /// 5 个工具共用的 JSON 输入/输出辅助——把「MCP arguments 节点 ↔ MemoryEntry/Filter/Stats」的
    /// 来回桥接集中到一处，避免每个工具各写一份解析。
    ///
    /// <para><b>时间约定：</b><see cref="DateTime"/> 统一以 ISO 8601 UTC（<c>"yyyy-MM-ddTHH:mm:ss.fffZ"</c>）
    /// 出入；接收方非 Utc 一律转 UTC，避免跨进程时区漂移。</para>
    /// </summary>
    internal static class MemoryBridgeToolSerializer
    {
        // 用「O」格式：roundtrip 精确到 100ns，且本身就是 ISO 8601。
        // 解析侧也只接受这一族格式（Roundtrip），保证 in/out 对称。
        private const string Iso8601UtcFormat = "yyyy-MM-ddTHH:mm:ss.fffZ";

        /// <summary>把 <see cref="DateTime"/> 转 ISO 8601 UTC 字符串。null 输入返回 null（用于可空字段）。</summary>
        public static string FormatIso8601Utc(DateTime? value)
        {
            if (!value.HasValue) return null;
            var utc = ToUtc(value.Value);
            return utc.ToString(Iso8601UtcFormat, CultureInfo.InvariantCulture);
        }

        public static string FormatIso8601Utc(DateTime value)
        {
            return ToUtc(value).ToString(Iso8601UtcFormat, CultureInfo.InvariantCulture);
        }

        /// <summary>
        /// 解析 ISO 8601（含 <c>Z</c> 或时区偏移）为 UTC <see cref="DateTime"/>。
        /// 空白返回 null；非法格式抛 <see cref="FormatException"/>——MCP 层会把它包成 RPC 错误。
        /// </summary>
        public static DateTime? ParseIso8601UtcOrNull(string text)
        {
            if (string.IsNullOrWhiteSpace(text)) return null;
            if (!DateTime.TryParse(
                    text,
                    CultureInfo.InvariantCulture,
                    DateTimeStyles.RoundtripKind | DateTimeStyles.AdjustToUniversal | DateTimeStyles.AssumeUniversal,
                    out var parsed))
            {
                throw new FormatException("时间字段必须是 ISO 8601 格式（例如 '2026-05-28T12:34:56.789Z'）：" + text);
            }
            return DateTime.SpecifyKind(parsed, DateTimeKind.Utc);
        }

        /// <summary>把任意 Kind 的 <see cref="DateTime"/> 折成 UTC（Unspecified 视为 UTC）。</summary>
        public static DateTime ToUtc(DateTime value)
        {
            switch (value.Kind)
            {
                case DateTimeKind.Utc:
                    return value;
                case DateTimeKind.Local:
                    return value.ToUniversalTime();
                default:
                    return DateTime.SpecifyKind(value, DateTimeKind.Utc);
            }
        }

        /// <summary>
        /// 把 <see cref="MemoryEntry"/> 序列化为 MCP 客户端易读的 JSON 对象——
        /// <c>tags</c> 字段保证非 null（null 折成空数组）；<c>createdAt</c> 走 ISO 8601 UTC。
        /// </summary>
        public static JsonObject EntryToJson(MemoryEntry entry)
        {
            if (entry == null) return null;
            var tags = new JsonArray();
            if (entry.Tags != null)
            {
                foreach (var t in entry.Tags) tags.Add(t);
            }
            return new JsonObject
            {
                ["id"] = entry.Id,
                ["source"] = entry.Source,
                ["createdAt"] = FormatIso8601Utc(entry.CreatedAt),
                ["text"] = entry.Text,
                ["tags"] = tags,
            };
        }

        /// <summary>把 <see cref="IReadOnlyList{MemoryEntry}"/> 序列化为 JSON 数组。null/empty 返回空数组。</summary>
        public static JsonArray EntriesToJson(IReadOnlyList<MemoryEntry> entries)
        {
            var arr = new JsonArray();
            if (entries == null) return arr;
            for (int i = 0; i < entries.Count; i++)
            {
                arr.Add(EntryToJson(entries[i]));
            }
            return arr;
        }

        /// <summary>
        /// 取 JSON 字符串字段——缺失 / null 返回 null；类型不对抛 <see cref="ArgumentException"/>
        /// （而非静默返回 null——防 schema 漂移被无声吞掉）。
        /// </summary>
        public static string GetStringOrNull(JsonNode args, string field)
        {
            if (args == null) return null;
            var node = args[field];
            if (node == null) return null;
            if (node is JsonValue v && v.TryGetValue<string>(out var s)) return s;
            throw new ArgumentException("字段 '" + field + "' 必须是字符串");
        }

        /// <summary>
        /// 取 JSON int 字段——缺失 / null 返回 defaultValue；类型不对抛 <see cref="ArgumentException"/>。
        /// </summary>
        public static int GetIntOrDefault(JsonNode args, string field, int defaultValue)
        {
            if (args == null) return defaultValue;
            var node = args[field];
            if (node == null) return defaultValue;
            if (node is JsonValue v)
            {
                if (v.TryGetValue<int>(out var i)) return i;
                // 兼容 LLM 偶发把 int 序列化为 64bit number 的路径
                if (v.TryGetValue<long>(out var l)) return checked((int)l);
            }
            throw new ArgumentException("字段 '" + field + "' 必须是整数");
        }

        /// <summary>
        /// 取 JSON string[] 字段——缺失 / null 返回空列表；非数组或元素非字符串抛
        /// <see cref="ArgumentException"/>。
        /// </summary>
        public static IReadOnlyList<string> GetStringArrayOrEmpty(JsonNode args, string field)
        {
            if (args == null) return Array.Empty<string>();
            var node = args[field];
            if (node == null) return Array.Empty<string>();
            var arr = node as JsonArray;
            if (arr == null)
                throw new ArgumentException("字段 '" + field + "' 必须是字符串数组");

            var result = new List<string>(arr.Count);
            for (int i = 0; i < arr.Count; i++)
            {
                var item = arr[i];
                if (item is JsonValue iv && iv.TryGetValue<string>(out var s))
                {
                    result.Add(s);
                }
                else
                {
                    throw new ArgumentException("字段 '" + field + "[" + i + "]' 必须是字符串");
                }
            }
            return result;
        }
    }
}
