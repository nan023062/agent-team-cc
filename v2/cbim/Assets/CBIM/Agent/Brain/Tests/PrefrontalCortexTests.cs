#if UNITY_INCLUDE_TESTS
using System;
using System.Collections.Generic;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using NUnit.Framework;
using CBIM.AgentSystem;
using CBIM.AgentSystem.Brain;
using CBIM.AgentSystem.Kernel.Neuron;
using CBIM.AgentSystem.Kernel.Synapse;
using CBIM.AgentSystem.Kernel.Synapse.Compiler;
using CBIM.Memory;

namespace CBIM.AgentSystem.Brain.Tests
{
    /// <summary>
    /// <see cref="PrefrontalCortex"/> 构造期与基础契约单元测试——T14 后契约。
    ///
    /// 覆盖：
    ///   - descriptor.Kind 必须 = PrefrontalCortex，否则 throw
    ///   - descriptor.IsPrefrontal 必须 true，否则 throw
    ///   - 空白 instanceId throw（FlowGraph 路径 JSON 落盘必需）
    ///   - 「主脑回调恒为 null」铁律——构造期内部强制 null
    ///   - 「CallableBrains 不含 PrefrontalCortex 自身」铁律
    ///   - 「CallableBrains 不含 PrefrontalCortex 类型」铁律（外部传入主脑也拒绝）
    ///   - 「CallableBrains 不含 null 项」/ 「BrainId 不重复」
    ///   - CallableBrains 浅复制——构造后外部修改不影响内部状态
    ///   - ActiveBuilder 默认为 null（仅在 InvokeAsync 窗口内非 null）
    ///
    /// 端到端 FlowGraph 路径测试（InvokeAsync 内 builder.Compiled 非 null → JSON 落盘 →
    /// Orchestrator 执行 / builder.Compiled null → 退化路径）在
    /// <see cref="PrefrontalCortexFlowGraphTests"/> 中独立覆盖。
    /// </summary>
    [TestFixture]
    public sealed class PrefrontalCortexTests
    {
        // ===== (1) descriptor.Kind 不对 → throw =====

        [Test]
        public void PrefrontalCortex_rejects_descriptor_with_wrong_kind()
        {
            var memory = new InMemoryFakeMemoryService();
            var neuron = new StubNeuron("prefrontal-cortex", BuildOkOutcome());
            var brainRegistry = new InMemoryBrainRegistry();

            // descriptor.Kind = ParietalLobe 而非 PrefrontalCortex——构造期 throw。
            var wrong = new StandardBrainDescriptor(
                brainId: "prefrontal-cortex",
                role: "prefrontal",
                soul: "soul",
                kind: StandardBrainKind.ParietalLobe,
                capability: BuildStubCapability())
            {
                IsPrefrontal = false,
            };

            Assert.Throws<InvalidOperationException>(
                () => new PrefrontalCortex(
                    wrong, memory, neuron,
                    callback: null,
                    callableBrains: Array.Empty<BrainBase>(),
                    brainRegistry: brainRegistry,
                    instanceId: "inst-1"),
                "PrefrontalCortex 构造期要求 descriptor.Kind=PrefrontalCortex。");
        }

        // ===== (2) descriptor.IsPrefrontal=false → throw =====

        [Test]
        public void PrefrontalCortex_rejects_descriptor_with_IsPrefrontal_false()
        {
            var memory = new InMemoryFakeMemoryService();
            var neuron = new StubNeuron("prefrontal-cortex", BuildOkOutcome());
            var brainRegistry = new InMemoryBrainRegistry();

            // Kind 对但 IsPrefrontal=false——构造期 throw。
            var wrong = new StandardBrainDescriptor(
                brainId: "prefrontal-cortex",
                role: "prefrontal",
                soul: "soul",
                kind: StandardBrainKind.PrefrontalCortex,
                capability: BuildStubCapability())
            {
                IsPrefrontal = false,
            };

            Assert.Throws<InvalidOperationException>(
                () => new PrefrontalCortex(
                    wrong, memory, neuron,
                    callback: null,
                    callableBrains: Array.Empty<BrainBase>(),
                    brainRegistry: brainRegistry,
                    instanceId: "inst-1"),
                "PrefrontalCortex 构造期要求 descriptor.IsPrefrontal=true。");
        }

        // ===== (3) 空白 instanceId → throw =====

        [Test]
        public void PrefrontalCortex_rejects_blank_instanceId()
        {
            var memory = new InMemoryFakeMemoryService();
            var neuron = new StubNeuron("prefrontal-cortex", BuildOkOutcome());
            var brainRegistry = new InMemoryBrainRegistry();
            var pfcDesc = BuildPrefrontalDescriptor();

            Assert.Throws<ArgumentException>(
                () => new PrefrontalCortex(
                    pfcDesc, memory, neuron,
                    callback: null,
                    callableBrains: Array.Empty<BrainBase>(),
                    brainRegistry: brainRegistry,
                    instanceId: "   "),
                "空白 instanceId 必须 throw——FlowGraph 路径 JSON 落盘必需。");
        }

        // ===== (4) PrefrontalCallback 恒为 null（即使调用方传非 null 也覆盖为 null） =====

        [Test]
        public void PrefrontalCortex_PrefrontalCallback_is_always_null_by_design()
        {
            var memory = new InMemoryFakeMemoryService();
            var neuron = new StubNeuron("prefrontal-cortex", BuildOkOutcome());
            var brainRegistry = new InMemoryBrainRegistry();
            var pfcDesc = BuildPrefrontalDescriptor();

            // 故意传一个非 null callback——构造器内部应强制为 null。
            var pfc = new PrefrontalCortex(
                pfcDesc, memory, neuron,
                callback: new FakePrefrontalCallback(),
                callableBrains: Array.Empty<BrainBase>(),
                brainRegistry: brainRegistry,
                instanceId: "inst-1");

            // PrefrontalCallback 是 protected——反射验证「主脑自己不回报自己」。
            var prop = typeof(BrainBase).GetProperty("PrefrontalCallback",
                System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
            Assert.That(prop, Is.Not.Null, "未找到 BrainBase.PrefrontalCallback——内部不变量违反。");

            var value = prop!.GetValue(pfc);
            Assert.That(value, Is.Null,
                "PrefrontalCortex.PrefrontalCallback 必须为 null——「主脑不回报自己」铁律。");
        }

        // ===== (5) CallableBrains 不含 PrefrontalCortex 自身 =====

        [Test]
        public void PrefrontalCortex_does_not_allow_PrefrontalCortex_type_in_CallableBrains()
        {
            var memory = new InMemoryFakeMemoryService();
            var neuron = new StubNeuron("prefrontal-cortex-other", BuildOkOutcome());
            var brainRegistry = new InMemoryBrainRegistry();

            // 准备一个外部「假主脑」以模拟「错误地把 Prefrontal 类型脑区放进 CallableBrains」。
            var otherPfcDesc = BuildPrefrontalDescriptor("prefrontal-cortex-other");
            var otherPfc = new PrefrontalCortex(
                otherPfcDesc, memory, neuron,
                callback: null,
                callableBrains: Array.Empty<BrainBase>(),
                brainRegistry: new InMemoryBrainRegistry(),
                instanceId: "inst-other");

            var pfcDesc = BuildPrefrontalDescriptor();
            var mainNeuron = new StubNeuron("prefrontal-cortex", BuildOkOutcome());

            Assert.Throws<InvalidOperationException>(() =>
                new PrefrontalCortex(
                    pfcDesc, memory, mainNeuron,
                    callback: null,
                    callableBrains: new BrainBase[] { otherPfc },
                    brainRegistry: brainRegistry,
                    instanceId: "inst-1"),
                "CallableBrains 不允许包含 PrefrontalCortex 类型脑区——「主脑唯一」铁律。");
        }

        // ===== (6) CallableBrains null 项 → throw =====

        [Test]
        public void PrefrontalCortex_rejects_null_item_in_CallableBrains()
        {
            var memory = new InMemoryFakeMemoryService();
            var neuron = new StubNeuron("prefrontal-cortex", BuildOkOutcome());
            var brainRegistry = new InMemoryBrainRegistry();
            var pfcDesc = BuildPrefrontalDescriptor();

            Assert.Throws<ArgumentException>(() =>
                new PrefrontalCortex(
                    pfcDesc, memory, neuron,
                    callback: null,
                    callableBrains: new BrainBase?[] { null }!,
                    brainRegistry: brainRegistry,
                    instanceId: "inst-1"),
                "CallableBrains 含 null 项必须 throw。");
        }

        // ===== (7) CallableBrains 重复 BrainId → throw =====

        [Test]
        public void PrefrontalCortex_rejects_duplicate_BrainId_in_CallableBrains()
        {
            var memory = new InMemoryFakeMemoryService();
            var callback = new FakePrefrontalCallback();
            var pfcDesc = BuildPrefrontalDescriptor();
            var brainRegistry = new InMemoryBrainRegistry();

            var parietalDesc = BuildStandardDescriptor(
                "parietal-lobe", "parietal", StandardBrainKind.ParietalLobe);
            var pNeuron1 = new StubNeuron("parietal-lobe", BuildOkOutcome());
            var pNeuron2 = new StubNeuron("parietal-lobe", BuildOkOutcome());

            var p1 = new ParietalLobe(parietalDesc, memory, pNeuron1, callback);
            var p2 = new ParietalLobe(parietalDesc, memory, pNeuron2, callback);

            var mainNeuron = new StubNeuron("prefrontal-cortex", BuildOkOutcome());

            Assert.Throws<InvalidOperationException>(() =>
                new PrefrontalCortex(
                    pfcDesc, memory, mainNeuron,
                    callback: null,
                    callableBrains: new BrainBase[] { p1, p2 },
                    brainRegistry: brainRegistry,
                    instanceId: "inst-1"),
                "CallableBrains 中 BrainId 重复必须 throw——「BrainId 唯一」铁律。");
        }

        // ===== (8) CallableBrains 浅复制——构造后外部 list 修改不影响内部 =====

        [Test]
        public void PrefrontalCortex_copies_CallableBrains_defensively()
        {
            var memory = new InMemoryFakeMemoryService();
            var callback = new FakePrefrontalCallback();
            var brainRegistry = new InMemoryBrainRegistry();
            var pfcDesc = BuildPrefrontalDescriptor();
            var mainNeuron = new StubNeuron("prefrontal-cortex", BuildOkOutcome());

            var parietalDesc = BuildStandardDescriptor(
                "parietal-lobe", "parietal", StandardBrainKind.ParietalLobe);
            var pNeuron = new StubNeuron("parietal-lobe", BuildOkOutcome());
            var p1 = new ParietalLobe(parietalDesc, memory, pNeuron, callback);

            var external = new List<BrainBase> { p1 };
            var pfc = new PrefrontalCortex(
                pfcDesc, memory, mainNeuron,
                callback: null,
                callableBrains: external,
                brainRegistry: brainRegistry,
                instanceId: "inst-1");

            external.Clear();  // 修改外部 list

            Assert.That(pfc.CallableBrains.Count, Is.EqualTo(1),
                "PrefrontalCortex 必须对 CallableBrains 做浅复制——构造后外部修改不影响内部状态。");
        }

        // ===== (9) ActiveBuilder 默认为 null =====

        [Test]
        public void PrefrontalCortex_ActiveBuilder_is_null_outside_InvokeAsync()
        {
            var memory = new InMemoryFakeMemoryService();
            var neuron = new StubNeuron("prefrontal-cortex", BuildOkOutcome());
            var brainRegistry = new InMemoryBrainRegistry();
            var pfcDesc = BuildPrefrontalDescriptor();

            var pfc = new PrefrontalCortex(
                pfcDesc, memory, neuron,
                callback: null,
                callableBrains: Array.Empty<BrainBase>(),
                brainRegistry: brainRegistry,
                instanceId: "inst-1");

            Assert.That(pfc.ActiveBuilder, Is.Null,
                "ActiveBuilder 在 InvokeAsync 窗口外应为 null——CompilerToolFactory 闭包必须读到 null 时抛错。");
        }

        // ===== (10) Aggregation 默认值 =====

        [Test]
        public void PrefrontalCortex_Aggregation_defaults_to_SummarizeBeforeReturn()
        {
            var memory = new InMemoryFakeMemoryService();
            var neuron = new StubNeuron("prefrontal-cortex", BuildOkOutcome());
            var brainRegistry = new InMemoryBrainRegistry();
            var pfcDesc = BuildPrefrontalDescriptor();

            var pfc = new PrefrontalCortex(
                pfcDesc, memory, neuron,
                callback: null,
                callableBrains: Array.Empty<BrainBase>(),
                brainRegistry: brainRegistry,
                instanceId: "inst-1");

            Assert.That(pfc.Aggregation, Is.EqualTo(PrefrontalAggregationStrategy.SummarizeBeforeReturn),
                "Aggregation 默认值应为 SummarizeBeforeReturn（v1 仅留枚举与字段）。");
        }

        // ===== helpers =====

        private static StandardBrainDescriptor BuildPrefrontalDescriptor(string brainId = "prefrontal-cortex")
        {
            return new StandardBrainDescriptor(
                brainId: brainId,
                role: "prefrontal",
                soul: "主脑魂",
                kind: StandardBrainKind.PrefrontalCortex,
                capability: BuildStubCapability())
            {
                IsPrefrontal = true,
            };
        }

        private static StandardBrainDescriptor BuildStandardDescriptor(
            string brainId, string role, StandardBrainKind kind)
        {
            return new StandardBrainDescriptor(
                brainId: brainId,
                role: role,
                soul: $"{role}-魂",
                kind: kind,
                capability: BuildStubCapability());
        }

        private static AgentDescription BuildStubCapability()
        {
            return new AgentDescription(
                id: "brain-stub.test",
                name: "Test",
                soul: "stub-soul",
                identity: "stub identity");
        }

        private static BrainOutcome BuildOkOutcome()
        {
            return new BrainOutcome(
                Summary: "ok",
                StructuredOutput: null,
                SideEffects: Array.Empty<SideEffect>(),
                IsError: false,
                ErrorMessage: null);
        }
    }
}
#endif
