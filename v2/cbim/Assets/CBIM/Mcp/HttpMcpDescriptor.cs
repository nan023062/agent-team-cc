using System;

namespace CBIM.Mcp
{
    /// <summary>
    /// 远端 HTTP/SSE MCP 服务描述符。
    /// 形态：CBIM 直接连远端已运行的 MCP server endpoint，用 HTTP 或 SSE 通信。
    ///
    /// 典型用法：业务自带的 MCP（如 cdn-prod-mcp / erp-finance-mcp）——
    /// 服务方是远端云服务的 MCP 接入端口，CBIM 不启动它、只连它。
    /// 通常配合鉴权 token 使用。
    /// </summary>
    public sealed class HttpMcpDescriptor : McpDescriptor
    {
        public override McpTransportKind Transport => McpTransportKind.Http;

        /// <summary>远端 MCP endpoint URL。例："https://cdn.example.com/mcp"。</summary>
        public string Endpoint { get; }

        /// <summary>可选鉴权 token。空表示无鉴权。</summary>
        public string AuthToken { get; }

        public HttpMcpDescriptor(
            string id,
            string name,
            string description,
            string endpoint,
            string authToken = null)
            : base(id, name, description)
        {
            if (string.IsNullOrWhiteSpace(endpoint))
                throw new ArgumentException("HttpMcpDescriptor.Endpoint 不能为空", nameof(endpoint));

            Endpoint = endpoint;
            AuthToken = authToken ?? string.Empty;
        }
    }
}
