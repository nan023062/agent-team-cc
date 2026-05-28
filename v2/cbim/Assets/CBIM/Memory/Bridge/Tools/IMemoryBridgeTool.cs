using System.Text.Json;
using System.Text.Json.Nodes;

namespace CBIM.Memory.Bridge.Tools
{
    /// <summary>
    /// <see cref="MemoryBridgeMcpServer"/> 内部「工具描述符」契约——把一个 MCP tool 拆成
    /// 「元信息（name / description / input schema）」+「执行体（Handle）」两半。
    ///
    /// <para>仅 5 个内置实现：<c>memory_write / memory_query / memory_get / memory_scan / memory_stats</c>。
    /// 不对外暴露——bridge 不打算成为 tool 注册中心，避免变成另一个 ToolDescriptor 抽象。</para>
    /// </summary>
    internal interface IMemoryBridgeTool
    {
        /// <summary>MCP 工具名——CBIM 现有 memory_* skill 同名。</summary>
        string Name { get; }

        /// <summary>给 LLM 看的工具说明（英文，与 MCP 生态惯例一致）。</summary>
        string Description { get; }

        /// <summary>MCP <c>inputSchema</c> JSON Schema 节点——已构造好可直接嵌入响应。</summary>
        JsonNode BuildInputSchema();

        /// <summary>
        /// 执行工具——接收 MCP 客户端发来的 <c>arguments</c> 节点（可能为 null），
        /// 返回符合 MCP <c>tools/call</c> 结果格式的内容节点（通常是一个对象，由调用方包装到
        /// <c>{ content: [ { type: "text", text: JSON.stringify(...) } ] }</c>）。
        /// </summary>
        /// <param name="arguments">客户端 <c>arguments</c> 对象；null 视为空对象。</param>
        /// <param name="jsonOptions">序列化选项（与 server 共用）。</param>
        /// <returns>执行结果——序列化后作为 text content 回传。不为 null。</returns>
        JsonNode Handle(JsonNode arguments, JsonSerializerOptions jsonOptions);
    }
}
