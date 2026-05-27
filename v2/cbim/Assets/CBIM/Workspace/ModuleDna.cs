using System;

namespace CBIM.Workspace
{
    /// <summary>
    /// 模块 DNA 来源类型。
    /// </summary>
    public enum ModuleDnaKind
    {
        /// <summary>本地文档（CBIM 工作区内的 .dna/module.md 文件）。</summary>
        Local,

        /// <summary>远端文档 / spec endpoint（云工作区的知识载体）。</summary>
        Remote,
    }

    /// <summary>
    /// 模块 DNA（ModuleDna）——业务维度的**纯知识载体**抽象。
    /// 一个 Module 通过 Dna 暴露它的业务知识、约定、约束文档（"是什么"）。
    ///
    /// 重要边界：
    ///   Dna 只承载**知识 / 文档 / spec**，不承载**操作能力**。
    ///   业务的操作能力归 ModuleDescription.McpList，类型是 AgentSystem.Mcp.McpDescriptor。
    ///   这与 AgentDescription（能力维度）的分工一致：
    ///     - Skills + SystemTools + McpList = "能做什么"
    ///     - Dna + Workflows + McpList     = "是什么 + 能做什么 + 怎么做"
    ///
    /// 两种实现：
    ///   - LocalModuleDna  ：本地 .dna/module.md 文档（当前默认）
    ///   - RemoteModuleDna ：远端 endpoint（云工作区的文档 / spec 服务）
    ///
    /// 「云工作区」设计意图：
    ///   一个 Module 在 CBIM 系统里可以只是一些"声明"（基本元信息 + 远端文档指针）。
    ///   真实业务知识在远端服务上托管（如内部 wiki / OpenAPI 文档服务 / spec registry）。
    ///   CBIM 启动时不必本地保存所有 module 文档，按需远端拉取。
    ///   注意：业务**操作**走 ModuleDescription.McpList，不走 Dna。
    ///
    /// CDN 业务示例（完整三段式）：
    ///   new ModuleDescription(
    ///     id: "cdn-storage-prod",
    ///     name: "生产 CDN 存储",
    ///     dna: new LocalModuleDna(".dna/module.md"),  // 这个 CDN 业务是什么、规则、SLA
    ///     workflows: [upload, download, query],        // 业务流程语义
    ///     mcpList: [
    ///       new HttpMcpDescriptor("cdn-mcp", ..., "https://cdn.example.com/mcp", auth)
    ///     ]);                                          // 实际操作接入点
    ///
    /// 读取语义不在此类——由 WorkspaceService 按 Kind 分派到对应 reader。
    /// ModuleDna 保持为纯数据描述符，无 IO 依赖。
    /// </summary>
    public abstract class ModuleDna
    {
        /// <summary>来源类型（Local / Remote）。</summary>
        public abstract ModuleDnaKind Kind { get; }

        /// <summary>定位字符串。Local 时是文件路径，Remote 时是 endpoint URL。</summary>
        public abstract string Location { get; }
    }

    /// <summary>
    /// 本地 .dna/module.md 文档。
    /// </summary>
    public sealed class LocalModuleDna : ModuleDna
    {
        public override ModuleDnaKind Kind => ModuleDnaKind.Local;

        /// <summary>本地文档绝对路径，如：项目根/Assets/Modules/MyGame/.dna/module.md</summary>
        public string FilePath { get; }

        public override string Location => FilePath;

        public LocalModuleDna(string filePath)
        {
            if (string.IsNullOrWhiteSpace(filePath))
                throw new ArgumentException("LocalModuleDna.FilePath 不能为空", nameof(filePath));
            FilePath = filePath;
        }

        public override string ToString() => $"LocalDna({FilePath})";
    }

    /// <summary>
    /// 远端文档 / spec endpoint（云工作区的知识载体）。
    /// 注意：仅持知识获取的远端入口，不承载业务**操作**——操作归 ModuleDescription.McpList。
    /// </summary>
    public sealed class RemoteModuleDna : ModuleDna
    {
        public override ModuleDnaKind Kind => ModuleDnaKind.Remote;

        /// <summary>远端 endpoint URL。例："https://wiki.example.com/api/docs/finance-module"。</summary>
        public string Endpoint { get; }

        /// <summary>可选鉴权令牌 / API key。空值表示无鉴权。</summary>
        public string AuthToken { get; }

        public override string Location => Endpoint;

        public RemoteModuleDna(string endpoint, string authToken = null)
        {
            if (string.IsNullOrWhiteSpace(endpoint))
                throw new ArgumentException("RemoteModuleDna.Endpoint 不能为空", nameof(endpoint));

            Endpoint = endpoint;
            AuthToken = authToken ?? string.Empty;
        }

        public override string ToString() => $"RemoteDna({Endpoint})";
    }
}
