using System;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace CBIM.Memory.Bridge.Tools
{
    /// <summary>
    /// MCP 工具 <c>memory_query</c>——按文本检索 top-K 相关条目。
    /// 算法由 <see cref="IMemoryService"/> 实现决定（默认 <c>FileMemoryBackend</c> = 关键词；
    /// 第三方实现可能是向量相似度）；本桥只透传。
    /// </summary>
    internal sealed class MemoryQueryTool : IMemoryBridgeTool
    {
        private const int DefaultTopK = 5;

        private readonly IMemoryService _memory;

        public MemoryQueryTool(IMemoryService memory)
        {
            _memory = memory ?? throw new ArgumentNullException(nameof(memory));
        }

        public string Name => "memory_query";

        public string Description =>
            "Search memory by text; returns the top-K most relevant entries. " +
            "Algorithm depends on the backend (keyword for FileMemoryBackend, vector similarity for VectorStore backends).";

        public JsonNode BuildInputSchema()
        {
            return new JsonObject
            {
                ["type"] = "object",
                ["properties"] = new JsonObject
                {
                    ["text"] = new JsonObject
                    {
                        ["type"] = "string",
                        ["description"] = "Query text",
                    },
                    ["topK"] = new JsonObject
                    {
                        ["type"] = "integer",
                        ["description"] = "Max entries to return (default 5; non-positive returns empty)",
                        ["default"] = DefaultTopK,
                    },
                },
                ["required"] = new JsonArray { "text" },
            };
        }

        public JsonNode Handle(JsonNode arguments, JsonSerializerOptions jsonOptions)
        {
            string text = MemoryBridgeToolSerializer.GetStringOrNull(arguments, "text");
            int topK = MemoryBridgeToolSerializer.GetIntOrDefault(arguments, "topK", DefaultTopK);

            // text 为 null 时下游会返回空集合，但 MCP 输入语义里 text 是必填——给出明确错误。
            if (text == null)
                throw new ArgumentException("memory_query: 'text' 必填（空字符串允许，但要显式传）");

            var hits = _memory.Query(text, topK);
            return new JsonObject
            {
                ["entries"] = MemoryBridgeToolSerializer.EntriesToJson(hits),
            };
        }
    }
}
