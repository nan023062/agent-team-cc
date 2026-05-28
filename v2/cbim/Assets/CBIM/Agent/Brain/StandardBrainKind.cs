namespace CBIM.AgentSystem.Brain
{
    /// <summary>
    /// 标识 <see cref="StandardBrainDescriptor"/> 所对应的具体 BrainBase 子类。
    /// 装配期（AgentSystem.OpenInstanceAsync）按该枚举分派构造哪个标准脑区类。
    /// External 类脑区不用本枚举——用独立的 <see cref="ExternalMotorCortexDescriptor"/>。
    /// </summary>
    public enum StandardBrainKind
    {
        /// <summary>前额叶皮层（主脑 · 调度中枢）。仅本 Kind 允许 <see cref="StandardBrainDescriptor.IsPrefrontal"/>=true。</summary>
        PrefrontalCortex,

        /// <summary>顶叶（架构脑 · 模块设计 / 架构合规）。</summary>
        ParietalLobe,

        /// <summary>海马体（记忆学习 · Dream 裂变）。</summary>
        Hippocampus,

        /// <summary>原生运动皮层（msai 装配 · 默认 1 个）。</summary>
        NativeMotorCortex
    }
}
