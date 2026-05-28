using System;
using System.Collections.Generic;
using System.Linq;

namespace CBIM.AgentSystem.Brain
{
    /// <summary>
    /// <see cref="BrainConfig"/> 的链式扩展——为常见「追加 ExternalMotorCortex 桥接」
    /// 场景提供命名良好的工厂方法，避免调用方手写一长串 <see cref="ExternalMotorCortexDescriptor"/>
    /// 字段。
    ///
    /// <para>本类只产「新的 <see cref="BrainConfig"/> 实例」——<see cref="BrainConfig"/> 不可变，
    /// 扩展方法必须返回新对象（铁律：链式调用不得改写源对象）。</para>
    ///
    /// <para>当前 v1 仅 <see cref="WithClaudeCode"/> 一种桥接落地；未来按需追加
    /// <c>.WithCursor / .WithCodex / .WithAider</c> 等。</para>
    /// </summary>
    public static class BrainConfigExtensions
    {
        /// <summary>
        /// 在现有 <see cref="BrainConfig"/> 后追加一个 <see cref="ExternalMotorCortexDescriptor"/>，
        /// 指向 Claude Code CLI——返回新 <see cref="BrainConfig"/> 实例。
        ///
        /// <para>装配后由 <c>AgentSystem.OpenInstanceAsync</c> 内的 <c>BuildExternalBrain</c>
        /// 路径解析为 <c>ClaudeCodeMotorCortex</c>，自带 memory-bridge MCP server
        /// （视 <paramref name="shareMode"/> 而定）。</para>
        ///
        /// <para>BrainId 固定为 <c>"motor-cortex.claude-code"</c>（与
        /// <c>ClaudeCodeMotorCortex.DefaultBrainId</c> 对齐——Dream 裂变产出变体时才会出现
        /// <c>"motor-cortex.claude-code.&lt;variant&gt;"</c>）。</para>
        /// </summary>
        /// <param name="config">源配置——本方法不会被修改，返回的新实例 Brains 列表 =
        /// 源 Brains + 1 个 ExternalMotorCortexDescriptor。</param>
        /// <param name="cliPath">Claude Code CLI 可执行路径。默认 <c>"claude-code"</c>
        /// （需在 PATH 中可找到）。</param>
        /// <param name="extraArgs">额外 CLI 参数（可空）；为 null 时按 <see cref="Array.Empty{T}"/> 处理。</param>
        /// <param name="shareMode">Memory 共享桥模式——默认 <see cref="MemoryShareMode.McpServer"/>
        /// （CBIM 起 in-proc memory-bridge MCP server 暴露 5 个 memory_* 工具）。</param>
        public static BrainConfig WithClaudeCode(
            this BrainConfig config,
            string cliPath = "claude-code",
            IReadOnlyList<string> extraArgs = null,
            MemoryShareMode shareMode = MemoryShareMode.McpServer)
        {
            if (config == null)
                throw new ArgumentNullException(nameof(config));
            if (string.IsNullOrWhiteSpace(cliPath))
                throw new ArgumentException("cliPath 不能为空", nameof(cliPath));

            var adapterConfig = new Dictionary<string, object>(StringComparer.Ordinal)
            {
                ["cli-path"] = cliPath,
                ["extra-args"] = extraArgs ?? Array.Empty<string>(),
            };

            var ext = new ExternalMotorCortexDescriptor(
                brainId: "motor-cortex.claude-code",
                soul:
                    "你是外部 Claude Code 引擎驱动的运动皮层。" +
                    "主脑下发的意图将作为 prompt 投给 Claude Code subprocess，" +
                    "由该子进程完成实际的文件编辑 / 工具调用 / 副作用执行；" +
                    "你只负责把意图翻译给子进程，并把子进程产出（transcript + git diff）" +
                    "如实回填为 BrainOutcome。",
                engineKind: ExternalEngineKind.ClaudeCode,
                engineEndpoint: cliPath,
                adapterConfig: adapterConfig)
            {
                MemoryShareMode = shareMode,
            };

            // BrainConfig 不可变——通过 Custom 重建新实例，源 config 与新 config 共享
            // 已有 BrainDescriptor 引用（描述符本身也是不可变值对象）。
            var merged = config.Brains.Concat(new BrainDescriptor[] { ext }).ToArray();
            return BrainConfig.Custom(merged);
        }
    }
}
