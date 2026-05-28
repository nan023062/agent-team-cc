using System;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace CBIM.Memory.Bridge.Tools
{
    /// <summary>
    /// MCP 工具 <c>memory_write</c>——写入或覆盖一条 <see cref="MemoryEntry"/>。
    /// 直接转发到 <see cref="IMemoryService.Write"/>；<c>createdAt</c> 由 server 端取 <see cref="DateTime.UtcNow"/>
    /// 填入（让客户端只关心「内容是什么」，时间戳归 server 权威）。
    /// </summary>
    internal sealed class MemoryWriteTool : IMemoryBridgeTool
    {
        private readonly IMemoryService _memory;

        public MemoryWriteTool(IMemoryService memory)
        {
            _memory = memory ?? throw new ArgumentNullException(nameof(memory));
        }

        public string Name => "memory_write";

        public string Description =>
            "Write or overwrite a memory entry. Tags are free-form keywords/topics. " +
            "The createdAt timestamp is assigned by the server (UTC).";

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
                        ["description"] = "Entry id (unique within the memory store; non-blank)",
                    },
                    ["source"] = new JsonObject
                    {
                        ["type"] = "string",
                        ["description"] = "Origin tag, e.g. 'distill' / 'manual'",
                    },
                    ["text"] = new JsonObject
                    {
                        ["type"] = "string",
                        ["description"] = "Entry body (free-form text)",
                    },
                    ["tags"] = new JsonObject
                    {
                        ["type"] = "array",
                        ["items"] = new JsonObject { ["type"] = "string" },
                        ["description"] = "Free-form keywords/topics (optional; defaults to empty)",
                    },
                },
                ["required"] = new JsonArray { "id", "source", "text" },
            };
        }

        public JsonNode Handle(JsonNode arguments, JsonSerializerOptions jsonOptions)
        {
            string id = MemoryBridgeToolSerializer.GetStringOrNull(arguments, "id");
            string source = MemoryBridgeToolSerializer.GetStringOrNull(arguments, "source");
            string text = MemoryBridgeToolSerializer.GetStringOrNull(arguments, "text");
            var tags = MemoryBridgeToolSerializer.GetStringArrayOrEmpty(arguments, "tags");

            // 入口校验（fail-fast）——把「空白 id」从默认实现的 ArgumentException
            // 上提为更明确的 MCP 输入错误。
            if (string.IsNullOrWhiteSpace(id))
                throw new ArgumentException("memory_write: 'id' 必填且不为空白");
            if (source == null)
                throw new ArgumentException("memory_write: 'source' 必填");
            if (text == null)
                throw new ArgumentException("memory_write: 'text' 必填");

            var entry = new MemoryEntry(
                Id: id,
                Source: source,
                CreatedAt: DateTime.UtcNow,
                Text: text,
                Tags: tags);

            _memory.Write(entry);

            return new JsonObject { ["ok"] = true };
        }
    }
}
