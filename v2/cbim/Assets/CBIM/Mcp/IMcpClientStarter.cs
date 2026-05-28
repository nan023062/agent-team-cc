namespace CBIM.Mcp
{
    /// <summary>
    /// MCP 客户端启动器 SPI——装配侧（AgentSystem / 业务 Workflow）注入的「怎么启」插口。
    ///
    /// 为什么设 SPI（而非直接依赖 Microsoft.Agents.AI.Mcp）：
    ///   - 本模块仍是基建抽象层，**不引入** Microsoft.Agents.AI.Mcp NuGet 依赖。
    ///   - ref-count / 生命周期 / 并发保护是本模块职责；具体协议接入由装配侧提供实现。
    ///   - 单测可注入 fake starter，不依赖外部进程 / 网络。
    ///
    /// 形态约定：
    ///   - 同步签名——与本模块其他接口对齐（CBIM.Storage / IMcpStore 均同步）。
    ///     具体实现可在内部 block 等待异步握手 / tools/list；调用方（DefaultMcpInstanceManager）
    ///     已在锁内串行化同 Id 启动，不存在重入风险。
    ///   - 抛异常代表启动失败——上游 IMcpInstanceManager.Request 不吞、原样上抛。
    ///     装配侧接住后做优雅降级。
    ///
    /// 这是「依赖隔离 SPI」而非「多实现插件点」——现阶段只有一个 Microsoft client 实现，
    /// SPI 的目的是不让 NuGet 包污染基建层，不是支持多套竞争实现。
    /// </summary>
    public interface IMcpClientStarter
    {
        /// <summary>
        /// 按 descriptor 启动 MCP client（stdio: 拉起子进程；http: 建连），
        /// 完成握手 + tools/list，返回一个可释放的启动产物（AIFunction 列表 + Dispose）。
        ///
        /// 失败时抛异常——不返回 null。
        /// </summary>
        IStartedMcpClient Start(McpDescriptor descriptor);
    }
}
