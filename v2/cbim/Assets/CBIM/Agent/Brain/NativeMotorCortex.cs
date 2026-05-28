using System;
using System.Threading.Tasks;
using CBIM.Memory;
using Microsoft.Extensions.AI;

namespace CBIM.AgentSystem.Brain
{
    /// <summary>
    /// NativeMotorCortex —— msai 装配的运动皮层。BrainConfig.Default 默认装 1 个。
    ///
    /// <para>BrainId 约定：默认 <c>"motor-cortex.native"</c>；允许 Dream 裂变期产出
    /// <c>"motor-cortex.&lt;specialty&gt;"</c> 子型号（如 <c>"motor-cortex.refactor"</c>）——
    /// 由 <see cref="StandardBrainDescriptor.BrainId"/> 携带，本类只验前缀。</para>
    ///
    /// <para>能力下发：<see cref="StandardBrainDescriptor.Capability"/> 上声明的
    /// SystemTools / McpList 默认全部下发到本脑区——由 AgentSystem.OpenInstanceAsync
    /// 在装配期挂到 <c>base.Agent.ChatOptions.Tools</c>（属 task-5 范畴；本切片不直
    /// 接消费 StandardToolsService）。</para>
    /// </summary>
    public sealed class NativeMotorCortex : MotorCortex
    {
        public const string DefaultBrainId = "motor-cortex.native";

        public NativeMotorCortex(
            StandardBrainDescriptor descriptor,
            IMemoryService memory,
            IChatClient chatClient,
            IPrefrontalCallback callback)
            : base(descriptor?.BrainId ?? throw new ArgumentNullException(nameof(descriptor)),
                   descriptor,
                   memory,
                   chatClient,
                   callback)
        {
            if (descriptor.Kind != StandardBrainKind.NativeMotorCortex)
                throw new InvalidOperationException(
                    $"NativeMotorCortex 要求 descriptor.Kind=NativeMotorCortex（实际: {descriptor.Kind}）。");
        }

        /// <inheritdoc/>
        public override ValueTask DisposeAsync() => default;
    }
}
