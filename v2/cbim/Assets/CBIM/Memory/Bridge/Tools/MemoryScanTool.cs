using System.Text.Json;
using System.Text.Json.Nodes;

namespace CBIM.Memory.Bridge.Tools
{
    /// <summary>
    /// MCP 工具 <c>memory_scan</c>——按结构化过滤枚举条目，按 <see cref="MemoryEntry.CreatedAt"/> 倒序。
    /// 桥接 <see cref="MemoryScanFilter"/>（SourceEquals / TagsAny / Since）；本期接口未提供 <c>until</c>
    /// 字段，故 <c>until</c> 输入参数即便客户端传入也只是被记录在 schema 中作为「未来扩展位」，
    /// server 端忽略——避免谎报「我支持」却悄悄丢字段。
    /// </summary>
    internal sealed class MemoryScanTool : IMemoryBridgeTool
    {
        private readonly IMemoryService _memory;

        public MemoryScanTool(IMemoryService memory)
        {
            _memory = memory ?? throw new System.ArgumentNullException(nameof(memory));
        }

        public string Name => "memory_scan";

        public string Description =>
            "Enumerate memory entries with structured filters (source / tags-any / since). " +
            "Results are ordered by createdAt descending. All filter fields are optional.";

        public JsonNode BuildInputSchema()
        {
            return new JsonObject
            {
                ["type"] = "object",
                ["properties"] = new JsonObject
                {
                    ["source"] = new JsonObject
                    {
                        ["type"] = "string",
                        ["description"] = "Return entries whose source equals this value (exact match)",
                    },
                    ["tags"] = new JsonObject
                    {
                        ["type"] = "array",
                        ["items"] = new JsonObject { ["type"] = "string" },
                        ["description"] = "Return entries whose Tags contain ANY of these (case-insensitive OR)",
                    },
                    ["since"] = new JsonObject
                    {
                        ["type"] = "string",
                        ["format"] = "date-time",
                        ["description"] = "ISO 8601 — return entries with createdAt >= this timestamp",
                    },
                },
            };
        }

        public JsonNode Handle(JsonNode arguments, JsonSerializerOptions jsonOptions)
        {
            string source = MemoryBridgeToolSerializer.GetStringOrNull(arguments, "source");
            var tags = MemoryBridgeToolSerializer.GetStringArrayOrEmpty(arguments, "tags");
            var since = MemoryBridgeToolSerializer.ParseIso8601UtcOrNull(
                MemoryBridgeToolSerializer.GetStringOrNull(arguments, "since"));

            // 空集合 → null（按 MemoryScanFilter 「空列表等价于 null」语义）
            var filter = new MemoryScanFilter(
                SourceEquals: source,
                TagsAny: tags.Count == 0 ? null : tags,
                Since: since);

            var hits = _memory.Scan(filter);
            return new JsonObject
            {
                ["entries"] = MemoryBridgeToolSerializer.EntriesToJson(hits),
            };
        }
    }
}
