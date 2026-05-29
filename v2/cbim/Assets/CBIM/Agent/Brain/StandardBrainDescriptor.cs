using System;

namespace CBIM.AgentSystem.Brain
{
    /// <summary>
    /// 标准脑区描述符——覆盖四种 Native 脑区：
    ///   PrefrontalCortex / ParietalLobe / Hippocampus / NativeMotorCortex。
    ///
    /// 内嵌 <see cref="AgentDescription"/> 全字段——这些脑区都走 msai 装配 +
    /// CBIM 完整能力链（Skills / SystemTools / McpList / MemoryFactory）。
    /// 具体 BrainBase 子类由 <see cref="Kind"/> 决定。
    /// </summary>
    public sealed class StandardBrainDescriptor : BrainDescriptor
    {
        /// <summary>能力声明——复用 AgentDescription 全字段。</summary>
        public AgentDescription Capability { get; }

        /// <summary>
        /// 是否为主脑（PrefrontalCortex）。
        /// 仅 <see cref="Kind"/> = <see cref="StandardBrainKind.PrefrontalCortex"/> 时允许 true。
        /// BrainConfig 构造期验证「有且仅有一个 IsPrefrontal=true」。
        /// </summary>
        public bool IsPrefrontal { get; set; }

        /// <summary>标识对应的具体 BrainBase 子类，装配期分派用。</summary>
        public StandardBrainKind Kind { get; }

        public StandardBrainDescriptor(
            string brainId,
            string role,
            string soul,
            StandardBrainKind kind,
            AgentDescription capability)
            : base(brainId, role, soul)
        {
            if (capability == null)
                throw new ArgumentNullException(nameof(capability));

            Kind = kind;
            Capability = capability;
        }

        /// <summary>
        /// 构造后由 BrainConfig.Validate 调用做交叉约束检查——本类对外暴露以便上游强制铁律。
        /// 当前一条铁律：<see cref="IsPrefrontal"/>=true 必须配对 <see cref="StandardBrainKind.PrefrontalCortex"/>。
        /// </summary>
        public void EnsureInvariants()
        {
            if (IsPrefrontal && Kind != StandardBrainKind.PrefrontalCortex)
                throw new InvalidOperationException(
                    "StandardBrainDescriptor.IsPrefrontal 仅允许在 Kind=PrefrontalCortex 上为 true");
        }
    }
}
