using System;
using System.Collections.Generic;
using CBIM.AgentSystem.Brain;
using Microsoft.Extensions.AI;

namespace CBIM.AgentSystem.Kernel.Neuron
{
    /// <summary>
    /// 神经元工厂——按 <see cref="BrainDescriptor"/> 子类分派构造 <see cref="INeuron"/> 实例。
    ///
    /// <para>装配方（<c>AgentSystem.OpenInstance</c>）按描述符调本工厂，拿到 INeuron 实例后再
    /// 传给 BrainBase 子类构造器。</para>
    ///
    /// <para>K5 铁律：仅按描述符<b>子类型</b>分派，<b>不</b>解读描述符语义字段
    /// （<see cref="StandardBrainDescriptor.Kind"/> / <see cref="StandardBrainDescriptor.IsPrefrontal"/>
    /// 等仍由 Brain 层验证）。</para>
    /// </summary>
    public static class NeuronFactory
    {
        /// <summary>
        /// 分派规则：
        /// <list type="bullet">
        ///   <item><see cref="StandardBrainDescriptor"/> → <see cref="MsaiNeuron"/></item>
        ///   <item><see cref="ExternalMotorCortexDescriptor"/> → <see cref="ExternalEngineNeuron"/>
        ///         （需 <see cref="NeuronAssemblyContext.ExternalAdapter"/> 非 null）</item>
        /// </list>
        /// 其他子类 → <see cref="InvalidOperationException"/>。
        /// </summary>
        public static INeuron Create(BrainDescriptor descriptor, NeuronAssemblyContext ctx)
        {
            if (descriptor == null)
                throw new ArgumentNullException(nameof(descriptor));
            if (ctx == null)
                throw new ArgumentNullException(nameof(ctx));

            switch (descriptor)
            {
                case StandardBrainDescriptor std:
                {
                    if (ctx.ChatClient == null)
                        throw new InvalidOperationException(
                            "StandardBrainDescriptor 装配需要 NeuronAssemblyContext.ChatClient 非 null。");

                    var merged = MergeTools(ctx.StandardAITools, ctx.SynapseAITools);
                    return new MsaiNeuron(std.BrainId, std, ctx.ChatClient, ctx.Memory, merged);
                }

                case ExternalMotorCortexDescriptor ext:
                {
                    if (ctx.ExternalAdapter == null)
                        throw new InvalidOperationException(
                            "ExternalMotorCortexDescriptor 装配需要 NeuronAssemblyContext.ExternalAdapter 非 null。");

                    return new ExternalEngineNeuron(ext.BrainId, ext, ctx.ExternalAdapter, ctx.Memory);
                }

                default:
                    throw new InvalidOperationException(
                        "unknown BrainDescriptor subclass: " + descriptor.GetType().FullName);
            }
        }

        /// <summary>
        /// 合并两份 AITool 集。null 视为空集；输出为不可变快照
        /// （避免装配方在装配后回改原列表影响神经元）。
        /// </summary>
        private static IReadOnlyList<AITool> MergeTools(
            IReadOnlyList<AITool>? standardTools,
            IReadOnlyList<AITool>? synapseTools)
        {
            int countA = standardTools?.Count ?? 0;
            int countB = synapseTools?.Count ?? 0;
            if (countA == 0 && countB == 0)
                return Array.Empty<AITool>();

            var merged = new List<AITool>(countA + countB);
            if (standardTools != null)
            {
                foreach (var t in standardTools) merged.Add(t);
            }
            if (synapseTools != null)
            {
                foreach (var t in synapseTools) merged.Add(t);
            }
            return merged;
        }
    }
}
