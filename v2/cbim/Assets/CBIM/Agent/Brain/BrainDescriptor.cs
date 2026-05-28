using System;

namespace CBIM.AgentSystem.Brain
{
    /// <summary>
    /// 脑区描述符公共基类——声明「这是什么脑区」的静态信息（不含运行态资源）。
    ///
    /// 两个具体子类分别覆盖标准脑区与外部桥接脑区：
    ///   - <see cref="StandardBrainDescriptor"/>：主脑 / 海马体 / 架构脑 / NativeMotorCortex
    ///   - <see cref="ExternalMotorCortexDescriptor"/>：外部引擎桥接的运动皮层
    ///
    /// 装配期（AgentSystem.OpenInstanceAsync）按子类类型 + 内部枚举分派构造哪个具体 BrainBase 子类。
    /// </summary>
    public abstract class BrainDescriptor
    {
        /// <summary>脑区在 AgentInstance 内的唯一标识。如 "prefrontal-cortex" / "motor-cortex.claude-code"。</summary>
        public string BrainId { get; }

        /// <summary>角色分类——"prefrontal" / "parietal" / "hippocampus" / "motor"。</summary>
        public string Role { get; }

        /// <summary>脑区灵魂（系统提示词 · 装入 ChatClientAgentOptions.Instructions）。</summary>
        public string Soul { get; }

        /// <summary>本脑区是否必须存在（默认 true · 当前 v1 不消费该字段，预留供 BrainConfig 校验扩展）。</summary>
        public bool IsRequired { get; init; } = true;

        protected BrainDescriptor(string brainId, string role, string soul)
        {
            if (string.IsNullOrWhiteSpace(brainId))
                throw new ArgumentException("BrainDescriptor.BrainId 不能为空", nameof(brainId));
            if (string.IsNullOrWhiteSpace(role))
                throw new ArgumentException("BrainDescriptor.Role 不能为空", nameof(role));
            if (string.IsNullOrWhiteSpace(soul))
                throw new ArgumentException("BrainDescriptor.Soul 不能为空——脑区必须有人设", nameof(soul));

            BrainId = brainId;
            Role = role;
            Soul = soul;
        }
    }
}
