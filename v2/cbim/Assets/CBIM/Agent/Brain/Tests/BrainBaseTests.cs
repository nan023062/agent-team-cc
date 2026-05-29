#if UNITY_INCLUDE_TESTS
using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Agents.AI;
using NUnit.Framework;
using CBIM.AgentSystem;
using CBIM.AgentSystem.Brain;
using CBIM.AgentSystem.Kernel.Neuron;
using CBIM.AgentSystem.Kernel.Synapse;
using CBIM.Memory;

namespace CBIM.AgentSystem.Brain.Tests
{
    /// <summary>
    /// <see cref="BrainBase"/> 单元测试——T4 后契约。
    ///
    /// 覆盖契约要点：
    ///   - 基类构造期不再装配 msai——LLM 出口已下沉到 <see cref="INeuron"/>（K2）
    ///   - <see cref="BrainBase.Agent"/> 透传 <c>Neuron.UnderlyingAgent</c>（msai 路径非 null / external 路径 null）
    ///   - null neuron / null memory / 空白 brainId 构造期立刻 throw（fail-fast）
    ///   - 默认 <see cref="BrainBase.InvokeAsync"/> 透传给 <see cref="INeuron.InvokeAsync"/>
    ///   - <see cref="BrainBase.DisposeAsync"/> 透传给 Neuron + 幂等
    ///   - 「主脑回调恒为 null」铁律由 <see cref="PrefrontalCortex"/> 自身验证（见 PrefrontalCortexTests）
    ///
    /// 用 <see cref="StubNeuron"/> 替代真实 Neuron——本套件不验 LLM 闭环，
    /// 验证 BrainBase 抽象层和 Neuron 的契约对接。
    /// </summary>
    [TestFixture]
    public sealed class BrainBaseTests
    {
        // ===== (1) 默认 InvokeAsync 透传给 Neuron =====

        [Test]
        public async Task BrainBase_InvokeAsync_delegates_to_Neuron()
        {
            var memory = new InMemoryFakeMemoryService();
            var callback = new FakePrefrontalCallback();
            var neuron = new StubNeuron("parietal-lobe", new BrainOutcome(
                Summary: "stub-says-ok",
                StructuredOutput: null,
                SideEffects: Array.Empty<SideEffect>(),
                IsError: false,
                ErrorMessage: null));

            var descriptor = BuildParietalDescriptor();
            var brain = new ParietalLobe(descriptor, memory, neuron, callback);

            var invocation = new BrainInvocation(
                CorrelationId: "corr-1",
                Intent: "设计 Foo 模块",
                StructuredInput: null,
                Context: new Dictionary<string, object>());

            var outcome = await brain.InvokeAsync(invocation, CancellationToken.None);

            Assert.That(neuron.CallCount, Is.EqualTo(1),
                "BrainBase.InvokeAsync 默认实现应透传 1 次到 Neuron。");
            Assert.That(neuron.LastInvocation, Is.SameAs(invocation),
                "BrainBase.InvokeAsync 应把 BrainInvocation 原样投给 Neuron。");
            Assert.That(outcome.Summary, Is.EqualTo("stub-says-ok"),
                "BrainOutcome 应原样从 Neuron 返出。");
        }

        // ===== (2) Agent 透传 Neuron.UnderlyingAgent =====

        [Test]
        public void BrainBase_Agent_property_returns_Neuron_UnderlyingAgent()
        {
            var memory = new InMemoryFakeMemoryService();
            var callback = new FakePrefrontalCallback();

            // ExternalEngine 路径下 UnderlyingAgent 恒 null。
            var neuron = new StubNeuron("motor-cortex.fake", BuildOkOutcome());
            var motorDesc = new ExternalMotorCortexDescriptor(
                brainId: "motor-cortex.fake",
                soul: "fake external",
                engineKind: ExternalEngineKind.Custom,
                engineEndpoint: "no-op");
            var brain = new StubExternalMotorCortex(motorDesc, memory, neuron, callback);

            Assert.That(brain.Agent, Is.Null,
                "ExternalEngine 路径 Neuron.UnderlyingAgent 恒为 null；BrainBase.Agent 应透传 null。");
        }

        // ===== (3) null neuron 构造期 throw =====

        [Test]
        public void BrainBase_constructor_rejects_null_neuron()
        {
            var memory = new InMemoryFakeMemoryService();
            var callback = new FakePrefrontalCallback();
            var descriptor = BuildParietalDescriptor();

            Assert.Throws<ArgumentNullException>(
                () => new ParietalLobe(descriptor, memory, neuron: null, callback),
                "K2 铁律：null neuron 构造期必须立刻 throw。");
        }

        // ===== (4) null memory 构造期 throw =====

        [Test]
        public void BrainBase_constructor_rejects_null_memory()
        {
            var callback = new FakePrefrontalCallback();
            var neuron = new StubNeuron("parietal-lobe", BuildOkOutcome());
            var descriptor = BuildParietalDescriptor();

            Assert.Throws<ArgumentNullException>(
                () => new ParietalLobe(descriptor, memory: null, neuron, callback),
                "「同一具身一份记忆」铁律由基类构造期强制——null memory 必须立刻 throw。");
        }

        // ===== (5) 空白 brainId 描述符层就拦截 =====

        [Test]
        public void BrainBase_constructor_rejects_blank_brainId_via_descriptor()
        {
            // descriptor.BrainId 空白时 BrainDescriptor 基类先 throw ArgumentException——
            // 物理保证 BrainBase 拿不到空白 brainId。
            Assert.Throws<ArgumentException>(() => new StandardBrainDescriptor(
                brainId: "   ",
                role: "parietal",
                soul: "ok",
                kind: StandardBrainKind.ParietalLobe,
                capability: BuildStubCapability()));
        }

        // ===== (6) DisposeAsync 透传给 Neuron + 幂等 =====

        [Test]
        public async Task BrainBase_DisposeAsync_propagates_to_Neuron_and_is_idempotent()
        {
            var memory = new InMemoryFakeMemoryService();
            var callback = new FakePrefrontalCallback();
            var neuron = new StubNeuron("parietal-lobe", BuildOkOutcome());
            var descriptor = BuildParietalDescriptor();
            var brain = new ParietalLobe(descriptor, memory, neuron, callback);

            await brain.DisposeAsync();
            await brain.DisposeAsync();
            await brain.DisposeAsync();

            Assert.That(neuron.DisposeCallCount, Is.GreaterThanOrEqualTo(1),
                "BrainBase.DisposeAsync 必须透传到 Neuron.DisposeAsync。");
            Assert.Pass("多次 DisposeAsync 不抛即视为幂等（具体次数由 Neuron 实现决定）。");
        }

        // ===== helpers =====

        private static StandardBrainDescriptor BuildParietalDescriptor()
        {
            return new StandardBrainDescriptor(
                brainId: "parietal-lobe",
                role: "parietal",
                soul: "顶叶魂",
                kind: StandardBrainKind.ParietalLobe,
                capability: BuildStubCapability());
        }

        private static AgentDescription BuildStubCapability()
        {
            return new AgentDescription(
                id: "brain-stub.test.parietal",
                name: "Test · Parietal",
                soul: "stub-soul",
                identity: "stub identity for tests");
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

        /// <summary>
        /// <see cref="ExternalMotorCortex"/> 极小 stub——避免 ClaudeCodeMotorCortex 触发真实 CLI 探测。
        /// </summary>
        private sealed class StubExternalMotorCortex : ExternalMotorCortex
        {
            public StubExternalMotorCortex(
                ExternalMotorCortexDescriptor descriptor,
                IMemoryService memory,
                INeuron neuron,
                IPrefrontalCallback callback)
                : base(descriptor, memory, neuron, callback)
            {
            }
        }
    }
}
#endif
