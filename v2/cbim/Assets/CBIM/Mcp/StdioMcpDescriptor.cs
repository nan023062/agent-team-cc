using System;
using System.Collections.Generic;

namespace CBIM.Mcp
{
    /// <summary>
    /// 本地 subprocess MCP 服务描述符。
    /// 形态：CBIM 本地启动一个 server 进程，通过 stdin/stdout 用 MCP 协议通信。
    ///
    /// 典型用法：agent 自带的 MCP（如 unity-mcp / git-mcp）——
    /// 服务方是命令行可执行程序，CBIM 进程内拉起来用，任务结束就关。
    /// </summary>
    public sealed class StdioMcpDescriptor : McpDescriptor
    {
        public override McpTransportKind Transport => McpTransportKind.Stdio;

        /// <summary>启动命令（可执行文件路径或命令名）。例："python" / "node" / "/usr/local/bin/unity-mcp"。</summary>
        public string Command { get; }

        /// <summary>启动参数列表。例：["-m", "unity_mcp", "--port", "0"]。</summary>
        public IReadOnlyList<string> Args { get; }

        /// <summary>额外环境变量。可为空。</summary>
        public IReadOnlyDictionary<string, string> Env { get; }

        public StdioMcpDescriptor(
            string id,
            string name,
            string description,
            string command,
            IReadOnlyList<string> args = null,
            IReadOnlyDictionary<string, string> env = null)
            : base(id, name, description)
        {
            if (string.IsNullOrWhiteSpace(command))
                throw new ArgumentException("StdioMcpDescriptor.Command 不能为空", nameof(command));

            Command = command;
            Args = args ?? Array.Empty<string>();
            Env = env ?? new Dictionary<string, string>();
        }
    }
}
