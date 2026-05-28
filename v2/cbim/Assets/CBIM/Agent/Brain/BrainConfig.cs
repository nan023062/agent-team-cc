using System;
using System.Collections.Generic;

namespace CBIM.AgentSystem.Brain
{
    /// <summary>
    /// 脑区编织蓝图——声明一个 Agent 由哪些脑区组装。
    ///
    /// <para>三铁律由构造期 <see cref="Validate"/> 强制：</para>
    /// <list type="number">
    ///   <item>有且仅有一个 <see cref="StandardBrainDescriptor.IsPrefrontal"/>=true（主脑唯一）。</item>
    ///   <item>至少一个脑区 BrainId 以 <c>"motor-cortex."</c> 开头（至少一个 MotorCortex）。</item>
    ///   <item>BrainId 全部唯一。</item>
    /// </list>
    ///
    /// <para><see cref="Default"/> 产出 4 脑装载（PrefrontalCortex / ParietalLobe /
    /// Hippocampus / NativeMotorCortex）；<see cref="Custom"/> 允许自定义编织
    /// （如追加 ClaudeCodeMotorCortex 走 BrainConfigExtensions 扩展方法）。</para>
    /// </summary>
    public sealed class BrainConfig
    {
        /// <summary>编织清单——构造期已做完三铁律校验。</summary>
        public IReadOnlyList<BrainDescriptor> Brains { get; }

        private BrainConfig(IReadOnlyList<BrainDescriptor> brains)
        {
            Validate(brains);
            Brains = brains;
        }

        /// <summary>
        /// 构造期三铁律校验——不变量违反即抛 <see cref="InvalidOperationException"/>。
        /// </summary>
        private static void Validate(IReadOnlyList<BrainDescriptor> brains)
        {
            if (brains == null)
                throw new ArgumentNullException(nameof(brains));
            if (brains.Count == 0)
                throw new InvalidOperationException(
                    "BrainConfig 至少要声明一个脑区。");

            int prefrontalCount = 0;
            bool hasMotor = false;
            var seenIds = new HashSet<string>(StringComparer.Ordinal);

            for (int i = 0; i < brains.Count; i++)
            {
                var d = brains[i];
                if (d == null)
                    throw new InvalidOperationException(
                        $"BrainConfig.Brains[{i}] 不允许为 null。");

                // RULE 1：主脑唯一——StandardBrainDescriptor.IsPrefrontal 计数 1
                if (d is StandardBrainDescriptor std)
                {
                    std.EnsureInvariants();
                    if (std.IsPrefrontal)
                        prefrontalCount++;
                }

                // RULE 2：至少一个 MotorCortex（BrainId 以 "motor-cortex." 开头）
                if (d.BrainId.StartsWith(MotorCortex.BrainIdPrefix, StringComparison.Ordinal))
                    hasMotor = true;

                // RULE 3：BrainId 唯一
                if (!seenIds.Add(d.BrainId))
                    throw new InvalidOperationException(
                        $"BrainId 重复: '{d.BrainId}'");
            }

            if (prefrontalCount != 1)
                throw new InvalidOperationException(
                    "BrainConfig 必须有且仅有一个 Prefrontal" +
                    $"（StandardBrainDescriptor.IsPrefrontal=true）；当前 {prefrontalCount} 个。");

            if (!hasMotor)
                throw new InvalidOperationException(
                    "BrainConfig 必须至少含一个 MotorCortex" +
                    $"（BrainId 以 '{MotorCortex.BrainIdPrefix}' 开头）。");
        }

        /// <summary>
        /// 默认 4 脑装配：PrefrontalCortex + ParietalLobe + Hippocampus + NativeMotorCortex。
        /// 各脑区 Soul 走 <see cref="DefaultSouls"/> 模板（占位符 <c>{agentName}</c> 替换）。
        /// 各脑区的 Capability 用一份「空能力」AgentDescription 占位——v1 各脑区不下发 Skills /
        /// SystemTools / McpList，本字段仅用于走 msai 装配（Name / Identity 写入 ChatClientAgentOptions）。
        /// </summary>
        public static BrainConfig Default(string agentName)
        {
            if (string.IsNullOrWhiteSpace(agentName))
                throw new ArgumentException("agentName 不能为空", nameof(agentName));

            var brains = new BrainDescriptor[]
            {
                new StandardBrainDescriptor(
                    brainId: PrefrontalCortex.DefaultBrainId,
                    role: "prefrontal",
                    soul: DefaultSouls.Prefrontal(agentName),
                    kind: StandardBrainKind.PrefrontalCortex,
                    capability: BuildStubCapability(agentName, "Prefrontal", "前额叶皮层 · 主脑 · 调度中枢"))
                {
                    IsPrefrontal = true,
                },
                new StandardBrainDescriptor(
                    brainId: ParietalLobe.DefaultBrainId,
                    role: "parietal",
                    soul: DefaultSouls.Parietal(agentName),
                    kind: StandardBrainKind.ParietalLobe,
                    capability: BuildStubCapability(agentName, "Parietal", "顶叶 · 架构脑 · 模块设计 / 结构推理")),
                new StandardBrainDescriptor(
                    brainId: Hippocampus.DefaultBrainId,
                    role: "hippocampus",
                    soul: DefaultSouls.Hippocampus(agentName),
                    kind: StandardBrainKind.Hippocampus,
                    capability: BuildStubCapability(agentName, "Hippocampus", "海马体 · 记忆学习 + Dream 裂变")),
                new StandardBrainDescriptor(
                    brainId: NativeMotorCortex.DefaultBrainId,
                    role: "motor",
                    soul: DefaultSouls.Motor(agentName),
                    kind: StandardBrainKind.NativeMotorCortex,
                    capability: BuildStubCapability(agentName, "Motor", "运动皮层 · 一切对外副作用唯一出口")),
            };

            return new BrainConfig(brains);
        }

        /// <summary>
        /// 自定义编织——把传入的描述符按顺序装入。<see cref="BrainConfigExtensions.WithClaudeCode"/>
        /// （task-6 落地）等扩展方法会基于 <see cref="Custom"/> 产物追加 ExternalMotorCortex。
        /// </summary>
        public static BrainConfig Custom(params BrainDescriptor[] brains)
        {
            if (brains == null)
                throw new ArgumentNullException(nameof(brains));

            // 拷贝防御——外部传入数组可被外部继续修改，BrainConfig 必须持只读快照。
            var copy = new BrainDescriptor[brains.Length];
            Array.Copy(brains, copy, brains.Length);
            return new BrainConfig(copy);
        }

        /// <summary>
        /// 为标准脑区构造一份「空能力」AgentDescription 占位——v1 不通过该 stub 派发 Skills /
        /// SystemTools / McpList（默认能力下发铁律由装配胶水侧 NativeMotorCortex 单独处理）。
        /// 仅承担 Name / Identity 进入 msai ChatClientAgentOptions 的最小职责。
        /// </summary>
        private static AgentDescription BuildStubCapability(string agentName, string region, string identity)
        {
            return new AgentDescription(
                id: $"brain-stub.{agentName}.{region}".ToLowerInvariant(),
                name: $"{agentName} · {region}",
                soul: $"{agentName} 的 {region} 脑区能力占位。",
                identity: identity);
        }

        /// <summary>
        /// 默认 Soul 模板——直接照搬 <c>Agent/Brain/.dna/module.md</c> 中各脑区的「默认 Soul 模板」段。
        /// 占位符 <c>{agentName}</c> 由 string interpolation 在工厂调用期替换。
        /// </summary>
        internal static class DefaultSouls
        {
            public static string Prefrontal(string agentName) =>
                "## 角色\n" +
                $"你是 {agentName} 的前额叶皮层（PrefrontalCortex）—— 执行调度中枢。\n" +
                "你本身不执行具体业务，也不直接调外部工具。你的职责只有三件：\n" +
                "  1. 听懂用户（或上游子任务）意图。\n" +
                "  2. 判断该调哪个脑区，通过 __brain_call_* 函数下发。\n" +
                "  3. 汇总子脑区返回的结果，以主脑口吻返回。\n" +
                "\n" +
                "## 调度原则\n" +
                "- 设计 / 架构 / 模块裂变 → __brain_call_parietal_lobe（顶叶）\n" +
                "- 记忆读写 / 学习 / Dream 裂变决策 → __brain_call_hippocampus（海马体）\n" +
                "- 代码 / 文件 / MCP / 任何副作用 → __brain_call_motor_cortex_*\n" +
                "  优先选 native；需要「仓库里多文件精修」时选 claude_code（如装了）。\n" +
                "- 不确定时优先问用户，不要乱分发。\n" +
                "\n" +
                "## 不允许的事\n" +
                "- 不直接调外部工具。所有动作走 motor 脑区。\n" +
                "- 不透露子脑区的存在给用户。\n" +
                "- 不重复下发同一动作。";

            public static string Parietal(string agentName) =>
                "## 角色\n" +
                $"你是 {agentName} 的顶叶（ParietalLobe）—— 架构设计与结构推理脑区。\n" +
                "\n" +
                "## 职责\n" +
                "  1. 为新模块产出 .dna 骨架（路径 + kind + name + owner + description + positioning + dependencies + 铁律）。\n" +
                "  2. 评价架构改动是否违反三层模型、依赖方向、能力 vs 业务维度铁律。\n" +
                "  3. 与 Hippocampus 协作裂变新模块（它判定什么该裂，你实际落下 .dna 设计）。\n" +
                "\n" +
                "## 不允许的事\n" +
                "  - 不直接编辑代码或写 .dna 文件——你产出设计意图，MotorCortex 调 dna_* MCP 实际写入。\n" +
                "  - 不跳过依赖图检查。产出新 .dna 前必读现有模块列表。\n" +
                "  - 不裁决该裂还是不该裂——裂变决策是 Hippocampus 职责。";

            public static string Hippocampus(string agentName) =>
                "## 角色\n" +
                $"你是 {agentName} 的海马体（Hippocampus）—— 记忆学习与 Dream 裂变脑区。\n" +
                "\n" +
                "## 日间职责\n" +
                "  1. 通过 IMemoryService.Write 落入新条目（manual / distill）。\n" +
                "  2. 通过 IMemoryService.Query / Scan 检索历史经验回填上下文。\n" +
                "  3. 维护标签 / source 等元数据，让 Scan 过滤可工作。\n" +
                "\n" +
                "## 夜间职责（Dream tick · v1 不完整实施）\n" +
                "  - 从最近 N 轮记忆中提炼「能力缺口 / 知识聚集」信号。\n" +
                "  - 产出 FissionProposal[]——能力裂变（新 MotorCortex）或知识裂变（新 Workspace Module）。\n" +
                "\n" +
                "## 不允许的事\n" +
                "  - 不直接改代码 / 写 .dna——裂变设计由 ParietalLobe 产出，落地由 MotorCortex 执行。\n" +
                "  - 不裁决「该不该执行」——你只产出提议，主脑决定。";

            public static string Motor(string agentName) =>
                $"你是 {agentName} 的运动皮层。你的职责是把主脑下发的意图翻译为实际工具调用，并如实记录副作用。";
        }
    }
}
