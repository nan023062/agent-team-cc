using System;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace CBIM.Memory.Bridge.Tools
{
    /// <summary>
    /// MCP 工具 <c>memory_stats</c>——返回 <see cref="MemoryStats"/> 快照。
    /// 字段名沿用 arch 约定的 <c>entryCount / oldestCreatedAt / newestCreatedAt</c>
    /// （注：实现内部记录名是 <c>TotalEntries</c>，但暴露给 LLM 时按规约名输出）。
    /// </summary>
    internal sealed class MemoryStatsTool : IMemoryBridgeTool
    {
        private readonly IMemoryService _memory;

        public MemoryStatsTool(IMemoryService memory)
        {
            _memory = memory ?? throw new ArgumentNullException(nameof(memory));
        }

        public string Name => "memory_stats";

        public string Description =>
            "Return memory store statistics: total entry count and oldest/newest createdAt (UTC, ISO 8601). " +
            "Returns null for oldest/newest when the store is empty.";

        public JsonNode BuildInputSchema()
        {
            // 无输入；提供空 object schema 以满足 MCP 客户端约定。
            return new JsonObject
            {
                ["type"] = "object",
                ["properties"] = new JsonObject(),
            };
        }

        public JsonNode Handle(JsonNode arguments, JsonSerializerOptions jsonOptions)
        {
            var stats = _memory.Stats();
            return new JsonObject
            {
                ["entryCount"] = stats.TotalEntries,
                ["oldestCreatedAt"] = MemoryBridgeToolSerializer.FormatIso8601Utc(stats.OldestCreatedAt),
                ["newestCreatedAt"] = MemoryBridgeToolSerializer.FormatIso8601Utc(stats.NewestCreatedAt),
            };
        }
    }
}
