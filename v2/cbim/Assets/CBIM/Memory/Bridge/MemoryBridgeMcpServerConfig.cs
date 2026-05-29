using System;

namespace CBIM.Memory.Bridge
{
    /// <summary>
    /// <see cref="MemoryBridgeMcpServer"/> 的启动参数——MCP <c>initialize</c> 握手回传的服务信息。
    ///
    /// <para>本配置仅承载「告诉对端我是谁」所需的最小字段;不包含端点、超时等运行参数——
    /// 这些由调用方在 <see cref="MemoryBridgeMcpServer.RunAsync"/> 处直接控制(stdin/stdout + ct)。</para>
    /// </summary>
    /// <param name="ServerName">
    /// MCP server 名称(暴露给客户端的 <c>serverInfo.name</c>)。
    /// 默认 <c>"cbim-memory-bridge-mcp"</c>——与 CBIM 文档 / 调用方 endpoint 名一致。
    /// 不允许 null / 空白。
    /// </param>
    /// <param name="ServerVersion">
    /// MCP server 版本(<c>serverInfo.version</c>)。默认 <c>"1.0.0"</c>。不允许 null / 空白。
    /// </param>
    public sealed class MemoryBridgeMcpServerConfig
    {
        public string ServerName { get; }
        public string ServerVersion { get; }

        public MemoryBridgeMcpServerConfig(
            string ServerName = "cbim-memory-bridge-mcp",
            string ServerVersion = "1.0.0")
        {
            this.ServerName = ServerName;
            this.ServerVersion = ServerVersion;
        }

        /// <summary>
        /// 校验字段——构造时即触发,让非法配置在启动而非首次 RPC 时暴露(fail-fast)。
        /// </summary>
        public MemoryBridgeMcpServerConfig Validate()
        {
            if (string.IsNullOrWhiteSpace(ServerName))
                throw new ArgumentException("ServerName 不能为空", nameof(ServerName));
            if (string.IsNullOrWhiteSpace(ServerVersion))
                throw new ArgumentException("ServerVersion 不能为空", nameof(ServerVersion));
            return this;
        }
    }
}
