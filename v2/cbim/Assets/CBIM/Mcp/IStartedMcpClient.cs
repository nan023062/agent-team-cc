using System;
using System.Collections.Generic;

namespace CBIM.Mcp
{
    /// <summary>
    /// 一个已完成握手 + 工具发现的 MCP client 启动产物。
    ///
    /// 由 <see cref="IMcpClientStarter.Start(McpDescriptor)"/> 创建；
    /// 由 <see cref="McpManager"/> 在 ref-count 归零时 Dispose。
    ///
    /// 字段类型注释：
    ///   AiFunctions 当前用 <c>IReadOnlyList&lt;object&gt;</c> 占位——后续接
    ///   Microsoft.Agents.AI.Mcp 时收紧为 <c>IReadOnlyList&lt;Microsoft.Extensions.AI.AIFunction&gt;</c>。
    ///   占位 object 是为了保持本模块零外部依赖（铁律：不引入 Microsoft.Agents.AI.Mcp NuGet）。
    ///
    /// Dispose 语义：断 IPC + Kill server 进程（Stdio） / 断 HTTP session（Http）。
    /// </summary>
    public interface IStartedMcpClient : IDisposable
    {
        /// <summary>
        /// 该 MCP server 通过 <c>tools/list</c> 暴露的工具集，已被 Microsoft client
        /// 包成 AIFunction 实例（占位类型 object）。装配侧把这里的元素挂到
        /// ChatOptions.Tools 即可使用。
        /// </summary>
        IReadOnlyList<object> AiFunctions { get; }
    }
}
