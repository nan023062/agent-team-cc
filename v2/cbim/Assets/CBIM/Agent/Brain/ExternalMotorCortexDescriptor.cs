using System;
using System.Collections.Generic;

namespace CBIM.AgentSystem.Brain
{
    /// <summary>
    /// External 运动皮层描述符——仅持桥接字段，<b>不</b>继承 AgentDescription
    /// （外部引擎自带工具栈，硬拗继承会产生字段污染：SystemTools / Skills / McpList
    /// 在 External 上无意义）。
    ///
    /// Role 固定为 <c>"motor"</c>；BrainId 必须以 <c>"motor-cortex."</c> 开头
    /// （与 MotorCortex 抽象基类的构造校验对齐，提前在描述符层就锁死）。
    /// </summary>
    public sealed class ExternalMotorCortexDescriptor : BrainDescriptor
    {
        /// <summary>外部引擎种类（v1 仅 ClaudeCode）。</summary>
        public ExternalEngineKind EngineKind { get; }

        /// <summary>引擎接入点——CLI 路径 / HTTP URL 等。</summary>
        public string EngineEndpoint { get; }

        /// <summary>引擎自有配置（key-value · 由具体 Adapter 解析）。</summary>
        public IReadOnlyDictionary<string, object> AdapterConfig { get; }

        /// <summary>Memory 共享桥模式（默认 <see cref="MemoryShareMode.McpServer"/>）。</summary>
        public MemoryShareMode MemoryShareMode { get; init; } = MemoryShareMode.McpServer;

        public ExternalMotorCortexDescriptor(
            string brainId,
            string soul,
            ExternalEngineKind engineKind,
            string engineEndpoint,
            IReadOnlyDictionary<string, object>? adapterConfig = null)
            : base(brainId, role: "motor", soul: soul)
        {
            if (!brainId.StartsWith("motor-cortex.", StringComparison.Ordinal))
                throw new InvalidOperationException(
                    $"ExternalMotorCortexDescriptor.BrainId 必须以 'motor-cortex.' 开头（实际: '{brainId}'）");
            if (string.IsNullOrWhiteSpace(engineEndpoint))
                throw new ArgumentException(
                    "ExternalMotorCortexDescriptor.EngineEndpoint 不能为空", nameof(engineEndpoint));

            EngineKind = engineKind;
            EngineEndpoint = engineEndpoint;
            AdapterConfig = adapterConfig ?? new Dictionary<string, object>();
        }
    }
}
