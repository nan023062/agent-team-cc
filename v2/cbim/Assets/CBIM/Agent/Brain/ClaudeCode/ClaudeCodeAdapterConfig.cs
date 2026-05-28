using System;
using System.Collections.Generic;

namespace CBIM.AgentSystem.Brain.ClaudeCode
{
    /// <summary>
    /// <see cref="ClaudeCodeEngineAdapter"/> 的运行配置。
    ///
    /// <para>「记忆桥不在本切片起」铁律：本类<b>不</b>启动 cbim-memory-bridge-mcp；
    /// 仅消费 <see cref="MemoryMcpEndpoint"/> 字段——由上游（task-5 AgentSystem.OpenInstanceAsync）
    /// 在装配期把已起好的 stdio command 字符串透传进来。</para>
    ///
    /// <para><see cref="WorkspaceRoot"/> 等于 AgentInstance.TaskWhere；不允许 null/空白。
    /// subprocess 的工作目录与 <see cref="TranscriptDir"/> 的解析锚点都来自它。</para>
    ///
    /// <para><see cref="TranscriptDir"/> 默认相对路径，最终落在
    /// <c>{WorkspaceRoot}/{TranscriptDir}</c>；每个 job 一行 JSONL 转录文件。</para>
    /// </summary>
    public sealed record ClaudeCodeAdapterConfig
    {
        /// <summary>Claude Code CLI 可执行名/绝对路径——默认假设在 PATH 中。</summary>
        public string CliPath { get; init; } = "claude-code";

        /// <summary>追加到 CLI 命令尾部的额外参数（在内置参数之前传入）。</summary>
        public IReadOnlyList<string> ExtraArgs { get; init; } = Array.Empty<string>();

        /// <summary>subprocess 整体超时——超时后 Kill 整棵进程树并返回 IsError BrainOutcome。</summary>
        public TimeSpan Timeout { get; init; } = TimeSpan.FromMinutes(30);

        /// <summary>转录文件目录（相对 <see cref="WorkspaceRoot"/>）；每个 jobId 一个 .jsonl。</summary>
        public string TranscriptDir { get; init; } = ".cbim/external/claude-code";

        /// <summary>
        /// CBIM-memory-bridge-mcp 的 stdio 启动命令——task-5 装配胶水期注入；
        /// 本切片只把它写进 --mcp-config 临时文件。null/空 = 不启用 MCP 记忆桥。
        /// </summary>
        public string? MemoryMcpEndpoint { get; init; }

        /// <summary>
        /// subprocess 的 WorkingDirectory——必须 = AgentInstance.TaskWhere；不允许 null/空白。
        /// </summary>
        public string WorkspaceRoot { get; init; } = string.Empty;

        /// <summary>
        /// 构造期校验——发现非法值即抛 <see cref="ArgumentException"/>/<see cref="ArgumentOutOfRangeException"/>。
        /// 调用方应在装配期立即触发此校验（典型做法：构造后立刻 Validate）。
        /// </summary>
        public void Validate()
        {
            if (string.IsNullOrWhiteSpace(CliPath))
                throw new ArgumentException(
                    "ClaudeCodeAdapterConfig.CliPath 不能为空。", nameof(CliPath));
            if (string.IsNullOrWhiteSpace(WorkspaceRoot))
                throw new ArgumentException(
                    "ClaudeCodeAdapterConfig.WorkspaceRoot 不能为空——必须 = AgentInstance.TaskWhere。",
                    nameof(WorkspaceRoot));
            if (Timeout <= TimeSpan.Zero)
                throw new ArgumentOutOfRangeException(
                    nameof(Timeout),
                    Timeout,
                    "ClaudeCodeAdapterConfig.Timeout 必须 > 0（默认 30 分钟）。");
            if (string.IsNullOrWhiteSpace(TranscriptDir))
                throw new ArgumentException(
                    "ClaudeCodeAdapterConfig.TranscriptDir 不能为空。", nameof(TranscriptDir));
            if (ExtraArgs == null)
                throw new ArgumentNullException(
                    nameof(ExtraArgs),
                    "ClaudeCodeAdapterConfig.ExtraArgs 不允许 null（用 Array.Empty<string>() 代替）。");
        }
    }
}
