using System;

namespace CBIM.Mcp
{
    /// <summary>
    /// MCP 服务描述符（McpDescriptor）——能力维度的扩展抽象之一。
    /// 抽象基类。两种具体形态：
    ///   - StdioMcpDescriptor：本地 subprocess + stdin/stdout
    ///   - HttpMcpDescriptor： 远端 endpoint + auth
    ///
    /// 跨维度共享抽象（关键特性）：
    ///   - AgentDescription.McpList    用 IReadOnlyList&lt;McpDescriptor&gt; ← 能力维度：agent 自带 MCP
    ///   - ModuleDescription.McpList   用 IReadOnlyList&lt;McpDescriptor&gt; ← 业务维度：业务接入点 MCP
    ///   同抽象，归属语义不同：
    ///     agent 自带 → 跟人走，例如 git-mcp（agent 会用 git）
    ///     业务自带 → 跟业务走，例如 cdn-prod-mcp（这个具体 CDN 实例的接入点）
    ///
    /// 在 CBIM 能力维度三大扩展抽象中的位置（平级）：
    ///   Skill        ← Skills/
    ///   ToolDescriptor   ← Tools/Standard/
    ///   McpDescriptor ← 这里
    ///
    /// 装配机制（任务期生命周期）：
    ///   AgentSystem.OpenInstance
    ///     → 按 desc 启动 MCP server（subprocess 或 HTTP 连接）
    ///     → MCP 握手 + tools/list 拿工具清单
    ///     → 每个工具包成 AIFunction，挂到 ChatOptions.Tools
    ///   任务结束 CloseInstance → MCP 关闭，AIFunction 失效
    ///
    /// 与 ToolDescriptor 的区别：ToolDescriptor 是声明即用（0 启动开销），
    /// MCP 是要启进程 + 协议握手 + 工具发现（数百 ms 起步）。
    /// </summary>
    public abstract class McpDescriptor
    {
        /// <summary>MCP 服务唯一 ID。kebab-case。例："unity-mcp" / "cdn-prod-mcp"。</summary>
        public string Id { get; }

        /// <summary>MCP 服务名（人类可读）。</summary>
        public string Name { get; }

        /// <summary>一句话描述：这个 MCP 提供什么能力。</summary>
        public string Description { get; }

        protected McpDescriptor(string id, string name, string description)
        {
            if (string.IsNullOrWhiteSpace(id))
                throw new ArgumentException("McpDescriptor.Id 不能为空", nameof(id));
            if (string.IsNullOrWhiteSpace(name))
                throw new ArgumentException("McpDescriptor.Name 不能为空", nameof(name));
            if (string.IsNullOrWhiteSpace(description))
                throw new ArgumentException("McpDescriptor.Description 不能为空", nameof(description));

            Id = id;
            Name = name;
            Description = description;
        }

        /// <summary>形态标识，用于装配时分派到对应启动器。</summary>
        public abstract McpTransportKind Transport { get; }

        public override string ToString() => $"{GetType().Name}({Id})";
    }

    /// <summary>MCP 传输形态。</summary>
    public enum McpTransportKind
    {
        /// <summary>本地 subprocess 启动，通过 stdin/stdout 通信。</summary>
        Stdio,

        /// <summary>HTTP/SSE 连远端 endpoint。</summary>
        Http,
    }
}
