namespace CBIM.AgentSystem.Brain
{
    /// <summary>
    /// ExternalMotorCortex 与 CBIM Memory 之间的共享桥模式。
    /// 「同一具身一份记忆」铁律的物理桥接选项。
    ///
    /// 当前 v1 实施仅 <see cref="McpServer"/> 走通；其他模式预留枚举位置。
    /// </summary>
    public enum MemoryShareMode
    {
        /// <summary>默认：CBIM 起 <c>cbim-memory-bridge-mcp</c> server 暴露 IMemoryService，外部以 MCP client 接入。</summary>
        McpServer,

        /// <summary>文件桥：CBIM 写记忆快照到约定目录，外部读（v1 不实施）。</summary>
        FileBridge,

        /// <summary>HTTP 桥：CBIM 起 HTTP 服务，外部主动调（v1 不实施）。</summary>
        HttpEndpoint,

        /// <summary>不共享（破坏「同一具身」铁律，不推荐 · v1 不实施）。</summary>
        None
    }
}
