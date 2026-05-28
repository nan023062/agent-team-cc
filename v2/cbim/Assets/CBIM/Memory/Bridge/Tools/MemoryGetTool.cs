using System;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace CBIM.Memory.Bridge.Tools
{
    /// <summary>
    /// MCP 工具 <c>memory_get</c>——按 id 精确取一条 <see cref="MemoryEntry"/>；
    /// 不存在或 id 空白时返回 <c>{ entry: null }</c>。
    /// </summary>
    internal sealed class MemoryGetTool : IMemoryBridgeTool
    {
        private readonly IMemoryService _memory;

        public MemoryGetTool(IMemoryService memory)
        {
            _memory = memory ?? throw new ArgumentNullException(nameof(memory));
        }

        public string Name => "memory_get";

        public string Description =>
            "Fetch a memory entry by id. Returns { entry: null } when the id is missing or blank.";

        public JsonNode BuildInputSchema()
        {
            return new JsonObject
            {
                ["type"] = "object",
                ["properties"] = new JsonObject
                {
                    ["id"] = new JsonObject
                    {
                        ["type"] = "string",
                        ["description"] = "Entry id",
                    },
                },
                ["required"] = new JsonArray { "id" },
            };
        }

        public JsonNode Handle(JsonNode arguments, JsonSerializerOptions jsonOptions)
        {
            string id = MemoryBridgeToolSerializer.GetStringOrNull(arguments, "id");
            var entry = _memory.Get(id);

            return new JsonObject
            {
                // null 节点显式置 null（而非省略），让客户端 schema 稳定。
                ["entry"] = entry == null ? null : MemoryBridgeToolSerializer.EntryToJson(entry),
            };
        }
    }
}
