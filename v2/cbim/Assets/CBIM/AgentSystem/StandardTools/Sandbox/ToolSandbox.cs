using System.Collections.Generic;

namespace CBIM.AgentSystem.StandardTools
{
    // 不可变的、按模块隔离的沙箱描述符。承载路径前缀白名单
    // 以及每个工具族都会用到的若干硬性上限。
    //
    // 仅在构造期使用：工具实例绑定到唯一一个 ToolSandbox，
    // 运行时不允许替换（见 module.md "Iron Rule 2"）。
    public sealed class ToolSandbox
    {
        public IReadOnlyList<string> AllowedPathPrefixes { get; }
        public string WorkingDirectory { get; }
        public long MaxFileBytes { get; }
        public long MaxResultBytes { get; }
        public IReadOnlyList<string> BlockedExtensions { get; }
        public IReadOnlyList<string> WebAllowedHosts { get; }

        public ToolSandbox(
            IReadOnlyList<string> allowedPathPrefixes,
            string workingDirectory = "",
            long maxFileBytes = 10L * 1024 * 1024,
            long maxResultBytes = 10L * 1024 * 1024,
            IReadOnlyList<string> blockedExtensions = null,
            IReadOnlyList<string> webAllowedHosts = null)
        {
            AllowedPathPrefixes = allowedPathPrefixes ?? new string[0];
            WorkingDirectory = workingDirectory ?? string.Empty;
            MaxFileBytes = maxFileBytes;
            MaxResultBytes = maxResultBytes;
            BlockedExtensions = blockedExtensions ?? new string[0];
            WebAllowedHosts = webAllowedHosts ?? new string[0];
        }
    }
}
