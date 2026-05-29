#if UNITY_INCLUDE_TESTS
using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using NUnit.Framework;
using CBIM.AgentSystem;
using CBIM.AgentSystem.Brain;
using CBIM.AgentSystem.Kernel.Neuron;
using CBIM.AgentSystem.Kernel.Synapse;
using CBIM.Memory;

namespace CBIM.AgentSystem.Brain.Tests
{
    /// <summary>
    /// <see cref="MotorCortex"/> / <see cref="NativeMotorCortex"/> / <see cref="ExternalMotorCortex"/>
    /// 单元测试——T4 后契约（直接喂 <see cref="INeuron"/> 而非 IChatClient）。
    ///
    /// 覆盖：
    ///   - MotorCortex BrainId 必须以 "motor-cortex." 开头（构造期校验）
    ///   - 任意 "motor-cortex.&lt;suffix&gt;" 均被接受（Dream 裂变期产出子型号的物理保证）
    ///   - NativeMotorCortex 透传 InvokeAsync 给底层 Neuron
    ///   - ExternalMotorCortex 也透传 InvokeAsync 给 Neuron（adapter 路径已下沉到 ExternalEngineNeuron 内部）
    ///   - ExternalMotorCortex 构造后 Agent 字段为 null（外部 Neuron 的 UnderlyingAgent 恒 null）
    ///   - ExternalMotorCortex.DisposeAsync 透传到 Neuron.DisposeAsync
    /// </summary>
    [TestFixture]
    public sealed class MotorCortexTests
    {
        // ===== (1) BrainId 必须以 "motor-cortex." 开头 =====

        [Test]
        public void MotorCortex_constructor_rejects_brainId_without_prefix()
        {
            var memory = new InMemoryFakeMemoryService();
            var callback = new FakePrefrontalCallback();
            var neuron = new StubNeuron("not-a-motor", BuildOkOutcome());

            var badDesc = new StandardBrainDescriptor(
                brainId: "not-a-motor",
                role: "motor",
                soul: "soul",
                kind: StandardBrainKind.NativeMotorCortex,
                capability: BuildStubCapability());

            Assert.Throws<InvalidOperationException>(
                () => new NativeMotorCortex(badDesc, memory, neuron, callback),
                "MotorCortex BrainId 必须以 'motor-cortex.' 开头——基类构造校验。");
        }

        // ===== (2) "motor-cortex.<anything>" 接受 =====

        [Test]
        public void MotorCortex_constructor_accepts_motor_cortex_dot_anything()
        {
            var memory = new InMemoryFakeMemoryService();
            var callback = new FakePrefrontalCallback();

            foreach (var brainId in new[] { "motor-cortex.native", "motor-cortex.refactor", "motor-cortex.codegen.x" })
            {
                var desc = new StandardBrainDescriptor(
                    brainId: brainId,
                    role: "motor",
                    soul: "soul",
                    kind: StandardBrainKind.NativeMotorCortex,
                    capability: BuildStubCapability());
                var neuron = new StubNeuron(brainId, BuildOkOutcome());

                BrainBase? brain = null;
                Assert.DoesNotThrow(
                    () => brain = new NativeMotorCortex(desc, memory, neuron, callback),
                    $"BrainId '{brainId}' 应被接受（以 'motor-cortex.' 开头）。");
                Assert.That(brain, Is.Not.Null);
                Assert.That(brain!.BrainId, Is.EqualTo(brainId));
            }
        }

        // ===== (3) NativeMotorCortex 透传 InvokeAsync 给 Neuron =====

        [Test]
        public async Task NativeMotorCortex_InvokeAsync_delegates_to_Neuron()
        {
            var memory = new InMemoryFakeMemoryService();
            var callback = new FakePrefrontalCallback();
            var neuron = new StubNeuron("motor-cortex.native", new BrainOutcome(
                Summary: "native-says-hi",
                StructuredOutput: null,
                SideEffects: Array.Empty<SideEffect>(),
                IsError: false,
                ErrorMessage: null));

            var desc = new StandardBrainDescriptor(
                brainId: "motor-cortex.native",
                role: "motor",
                soul: "soul",
                kind: StandardBrainKind.NativeMotorCortex,
                capability: BuildStubCapability());

            var motor = new NativeMotorCortex(desc, memory, neuron, callback);

            var invocation = new BrainInvocation(
                CorrelationId: "c-1",
                Intent: "请帮我跑工具",
                StructuredInput: null,
                Context: new Dictionary<string, object>());

            var outcome = await motor.InvokeAsync(invocation, CancellationToken.None);

            Assert.That(outcome.IsError, Is.False);
            Assert.That(outcome.Summary, Is.EqualTo("native-says-hi"),
                "Summary 应原样从 Neuron 返出。");
            Assert.That(neuron.CallCount, Is.EqualTo(1),
                "Neuron.InvokeAsync 应被调用 1 次。");
        }

        // ===== (4) ExternalMotorCortex 透传 InvokeAsync 给 Neuron =====

        [Test]
        public async Task ExternalMotorCortex_InvokeAsync_delegates_to_Neuron()
        {
            var memory = new InMemoryFakeMemoryService();
            var callback = new FakePrefrontalCallback();
            var neuron = new StubNeuron("motor-cortex.fake", new BrainOutcome(
                Summary: "external-done",
                StructuredOutput: null,
                SideEffects: new[] { new SideEffect("file-write", "/tmp/x.txt", null, DateTimeOffset.UtcNow) },
                IsError: false,
                ErrorMessage: null));

            var ext = new ExternalMotorCortexDescriptor(
                brainId: "motor-cortex.fake",
                soul: "fake external",
                engineKind: ExternalEngineKind.Custom,
                engineEndpoint: "no-op");

            var brain = new StubExternalMotorCortex(ext, memory, neuron, callback);

            try
            {
                var invocation = new BrainInvocation(
                    CorrelationId: "c-ext",
                    Intent: "请编辑文件",
                    StructuredInput: null,
                    Context: new Dictionary<string, object>());

                var outcome = await brain.InvokeAsync(invocation, CancellationToken.None);

                Assert.That(neuron.CallCount, Is.EqualTo(1),
                    "Neuron.InvokeAsync 应被调用 1 次（adapter 路径已下沉到 Neuron 内部）。");
                Assert.That(outcome.IsError, Is.False);
                Assert.That(outcome.Summary, Is.EqualTo("external-done"));
                Assert.That(outcome.SideEffects.Count, Is.EqualTo(1));
            }
            finally
            {
                await brain.DisposeAsync();
            }
        }

        // ===== (5) ExternalMotorCortex.Agent 为 null =====

        [Test]
        public async Task ExternalMotorCortex_Agent_is_null_after_construction()
        {
            var memory = new InMemoryFakeMemoryService();
            var callback = new FakePrefrontalCallback();
            var neuron = new StubNeuron("motor-cortex.fake", BuildOkOutcome());

            var ext = new ExternalMotorCortexDescriptor(
                brainId: "motor-cortex.fake",
                soul: "fake external",
                engineKind: ExternalEngineKind.Custom,
                engineEndpoint: "no-op");

            var brain = new StubExternalMotorCortex(ext, memory, neuron, callback);

            try
            {
                Assert.That(brain.Agent, Is.Null,
                    "External Neuron 的 UnderlyingAgent 恒 null——BrainBase.Agent 透传 null。");
                Assert.That(brain.ShareMode, Is.EqualTo(MemoryShareMode.McpServer),
                    "默认 MemoryShareMode 应等于描述符默认值 McpServer。");
            }
            finally
            {
                await brain.DisposeAsync();
            }
        }

        // ===== (6) Dispose 透传 Neuron =====

        [Test]
        public async Task ExternalMotorCortex_DisposeAsync_disposes_neuron()
        {
            var memory = new InMemoryFakeMemoryService();
            var callback = new FakePrefrontalCallback();
            var neuron = new StubNeuron("motor-cortex.fake", BuildOkOutcome());

            var ext = new ExternalMotorCortexDescriptor(
                brainId: "motor-cortex.fake",
                soul: "fake external",
                engineKind: ExternalEngineKind.Custom,
                engineEndpoint: "no-op");

            var brain = new StubExternalMotorCortex(ext, memory, neuron, callback);

            Assert.That(neuron.DisposeCallCount, Is.EqualTo(0),
                "构造期不应触发 neuron.Dispose。");

            await brain.DisposeAsync();

            Assert.That(neuron.DisposeCallCount, Is.GreaterThanOrEqualTo(1),
                "ExternalMotorCortex.DisposeAsync 必须传递 dispose 到底层 Neuron（adapter 由 Neuron 进一步释放）。");
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
