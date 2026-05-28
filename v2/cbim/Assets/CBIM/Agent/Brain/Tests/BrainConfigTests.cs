#if UNITY_INCLUDE_TESTS
using System;
using System.Linq;
using NUnit.Framework;
using CBIM.AgentSystem;
using CBIM.AgentSystem.Brain;

namespace CBIM.AgentSystem.Brain.Tests
{
    /// <summary>
    /// <see cref="BrainConfig"/> 与 <see cref="BrainConfigExtensions.WithClaudeCode"/> 单元测试。
    ///
    /// 覆盖：
    ///   - Default 产出 4 脑（Prefrontal / Parietal / Hippocampus / NativeMotor）
    ///   - Custom 拒绝「无 Prefrontal」 / 「两个 Prefrontal」 / 「无 MotorCortex」 / 「BrainId 重复」
    ///   - WithClaudeCode 追加 ExternalMotorCortexDescriptor 后仍满足三铁律（不破坏原有 4 脑）
    /// </summary>
    [TestFixture]
    public sealed class BrainConfigTests
    {
        // ===== (1) Default 4 脑 =====

        [Test]
        public void BrainConfig_Default_returns_4_brains()
        {
            var cfg = BrainConfig.Default("test-agent");

            Assert.That(cfg.Brains.Count, Is.EqualTo(4),
                "默认装配应有 4 个脑区。");

            var kinds = cfg.Brains
                .OfType<StandardBrainDescriptor>()
                .Select(d => d.Kind)
                .ToArray();

            Assert.That(kinds, Is.EquivalentTo(new[]
            {
                StandardBrainKind.PrefrontalCortex,
                StandardBrainKind.ParietalLobe,
                StandardBrainKind.Hippocampus,
                StandardBrainKind.NativeMotorCortex,
            }));

            // 主脑唯一
            Assert.That(cfg.Brains.OfType<StandardBrainDescriptor>().Count(d => d.IsPrefrontal),
                Is.EqualTo(1),
                "默认装配应有且仅有一个 IsPrefrontal=true。");

            // 至少一个 MotorCortex
            Assert.That(cfg.Brains.Any(d => d.BrainId.StartsWith("motor-cortex.", StringComparison.Ordinal)),
                Is.True,
                "默认装配应至少含一个 BrainId 以 'motor-cortex.' 开头的脑区。");
        }

        // ===== (2) Custom 无 Prefrontal → throw =====

        [Test]
        public void BrainConfig_Custom_rejects_no_prefrontal()
        {
            var motorOnly = new StandardBrainDescriptor(
                brainId: "motor-cortex.native",
                role: "motor",
                soul: "soul",
                kind: StandardBrainKind.NativeMotorCortex,
                capability: BuildStubCapability());

            Assert.Throws<InvalidOperationException>(
                () => BrainConfig.Custom(motorOnly),
                "无 IsPrefrontal=true 描述符——「主脑唯一」铁律违反。");
        }

        // ===== (3) Custom 两个 Prefrontal → throw =====

        [Test]
        public void BrainConfig_Custom_rejects_two_prefrontal()
        {
            var pfc1 = new StandardBrainDescriptor(
                brainId: "prefrontal-cortex-1",
                role: "prefrontal",
                soul: "soul",
                kind: StandardBrainKind.PrefrontalCortex,
                capability: BuildStubCapability())
            { IsPrefrontal = true };

            var pfc2 = new StandardBrainDescriptor(
                brainId: "prefrontal-cortex-2",
                role: "prefrontal",
                soul: "soul",
                kind: StandardBrainKind.PrefrontalCortex,
                capability: BuildStubCapability())
            { IsPrefrontal = true };

            var motor = new StandardBrainDescriptor(
                brainId: "motor-cortex.native",
                role: "motor",
                soul: "soul",
                kind: StandardBrainKind.NativeMotorCortex,
                capability: BuildStubCapability());

            Assert.Throws<InvalidOperationException>(
                () => BrainConfig.Custom(pfc1, pfc2, motor),
                "两个 IsPrefrontal=true 描述符——「主脑唯一」铁律违反。");
        }

        // ===== (4) Custom 无 MotorCortex → throw =====

        [Test]
        public void BrainConfig_Custom_rejects_no_motor_cortex()
        {
            var pfc = new StandardBrainDescriptor(
                brainId: "prefrontal-cortex",
                role: "prefrontal",
                soul: "soul",
                kind: StandardBrainKind.PrefrontalCortex,
                capability: BuildStubCapability())
            { IsPrefrontal = true };

            var parietal = new StandardBrainDescriptor(
                brainId: "parietal-lobe",
                role: "parietal",
                soul: "soul",
                kind: StandardBrainKind.ParietalLobe,
                capability: BuildStubCapability());

            // 没有任何 BrainId 以 "motor-cortex." 开头——铁律违反。
            Assert.Throws<InvalidOperationException>(
                () => BrainConfig.Custom(pfc, parietal),
                "无 MotorCortex 脑区——「至少一个 MotorCortex」铁律违反。");
        }

        // ===== (5) Custom 重复 BrainId → throw =====

        [Test]
        public void BrainConfig_Custom_rejects_duplicate_brainId()
        {
            var pfc = new StandardBrainDescriptor(
                brainId: "prefrontal-cortex",
                role: "prefrontal",
                soul: "soul",
                kind: StandardBrainKind.PrefrontalCortex,
                capability: BuildStubCapability())
            { IsPrefrontal = true };

            // 重复 BrainId "motor-cortex.native"
            var motor1 = new StandardBrainDescriptor(
                brainId: "motor-cortex.native",
                role: "motor",
                soul: "soul",
                kind: StandardBrainKind.NativeMotorCortex,
                capability: BuildStubCapability());
            var motor2 = new StandardBrainDescriptor(
                brainId: "motor-cortex.native",
                role: "motor",
                soul: "soul",
                kind: StandardBrainKind.NativeMotorCortex,
                capability: BuildStubCapability());

            Assert.Throws<InvalidOperationException>(
                () => BrainConfig.Custom(pfc, motor1, motor2),
                "「BrainId 唯一」铁律违反。");
        }

        // ===== (6) WithClaudeCode 追加 + 铁律保持 =====

        [Test]
        public void BrainConfig_WithClaudeCode_adds_ClaudeCode_descriptor_keeping_invariants()
        {
            var baseCfg = BrainConfig.Default("test-agent");
            var withCc = baseCfg.WithClaudeCode();

            Assert.That(withCc.Brains.Count, Is.EqualTo(baseCfg.Brains.Count + 1),
                "WithClaudeCode 应追加恰好 1 个描述符。");

            // 追加的是 ExternalMotorCortexDescriptor 且 BrainId = "motor-cortex.claude-code"
            var extras = withCc.Brains.OfType<ExternalMotorCortexDescriptor>().ToList();
            Assert.That(extras.Count, Is.EqualTo(1));
            Assert.That(extras[0].BrainId, Is.EqualTo("motor-cortex.claude-code"));
            Assert.That(extras[0].EngineKind, Is.EqualTo(ExternalEngineKind.ClaudeCode));

            // 主脑仍唯一
            Assert.That(withCc.Brains.OfType<StandardBrainDescriptor>().Count(d => d.IsPrefrontal),
                Is.EqualTo(1),
                "WithClaudeCode 后仍只能有 1 个主脑。");

            // MotorCortex 现在有 2 个（NativeMotorCortex + ClaudeCodeMotorCortex）
            int motorCount = withCc.Brains
                .Count(d => d.BrainId.StartsWith("motor-cortex.", StringComparison.Ordinal));
            Assert.That(motorCount, Is.EqualTo(2),
                "WithClaudeCode 后应有 2 个 MotorCortex 描述符。");

            // 不可变契约：源 baseCfg 未被修改
            Assert.That(baseCfg.Brains.Count, Is.EqualTo(4),
                "BrainConfig 不可变——WithClaudeCode 应返回新实例而非改写源对象。");
        }

        // ===== helpers =====

        private static AgentDescription BuildStubCapability()
        {
            return new AgentDescription(
                id: "brain-stub.test",
                name: "Test",
                soul: "stub-soul",
                identity: "stub identity");
        }
    }
}
#endif
