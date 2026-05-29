#if UNITY_INCLUDE_TESTS
using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using NUnit.Framework;
using CBIM.AgentSystem;
using CBIM.AgentSystem.Brain;
using CBIM.AgentSystem.Kernel.Synapse;
using CBIM.Memory;

namespace CBIM.AgentSystem.Brain.Tests
{
    /// <summary>
    /// <see cref="MotorCortex"/> / <see cref="NativeMotorCortex"/> / <see cref="ExternalMotorCortex"/>
    /// 单元测试。
    ///
    /// 覆盖：
    ///   - MotorCortex BrainId 必须以 "motor-cortex." 开头（构造期校验）
    ///   - 任意 "motor-cortex.&lt;suffix&gt;" 均被接受（Dream 裂变期产出子型号的物理保证）
    ///   - NativeMotorCortex 走基类默认 InvokeAsync（msai Agent.RunAsync）
    ///   - ExternalMotorCortex 走 Adapter.SubmitAsync → AwaitResultAsync 路径
    ///   - ExternalMotorCortex 构造后 Agent 字段为 null（外部引擎自带 LLM）
    ///   - ExternalMotorCortex.DisposeAsync 触发 Adapter.DisposeAsync
    /// </summary>
    [TestFixture]
    public sealed class MotorCortexTests
    {
        // ===== (1) BrainId 必须以 "motor-cortex." 开头 =====

        [Test]
        public void MotorCortex_constructor_rejects_brainId_without_prefix()
        {
            // descriptor.BrainId = "not-motor"（不以 "motor-cortex." 开头）——
            // MotorCortex 基类的构造期 throw（即使 NativeMotorCortex 子类 ctor 还会
            // 先检 Kind，但 Kind 校验前基类 ctor 已先跑——这里直接构造一个 Kind 合规
            // 但 BrainId 不合规的描述符以触发基类校验路径）。
            var memory = new InMemoryFakeMemoryService();
            var chat = new FakeChatClient("ok");
            var callback = new FakePrefrontalCallback();

            var badDesc = new StandardBrainDescriptor(
                brainId: "not-a-motor",
                role: "motor",
                soul: "soul",
                kind: StandardBrainKind.NativeMotorCortex,
                capability: BuildStubCapability());

            Assert.Throws<InvalidOperationException>(
                () => new NativeMotorCortex(badDesc, memory, chat, callback),
                "MotorCortex BrainId 必须以 'motor-cortex.' 开头——基类构造校验。");
        }

        // ===== (2) "motor-cortex.<anything>" 接受 =====

        [Test]
        public void MotorCortex_constructor_accepts_motor_cortex_dot_anything()
        {
            var memory = new InMemoryFakeMemoryService();
            var chat = new FakeChatClient("ok");
            var callback = new FakePrefrontalCallback();

            // Dream 裂变期产出 "motor-cortex.refactor" / "motor-cortex.codegen" 等子型号——
            // 基类不应拒绝任意带 "motor-cortex." 前缀的 BrainId。
            foreach (var brainId in new[] { "motor-cortex.native", "motor-cortex.refactor", "motor-cortex.codegen.x" })
            {
                var desc = new StandardBrainDescriptor(
                    brainId: brainId,
                    role: "motor",
                    soul: "soul",
                    kind: StandardBrainKind.NativeMotorCortex,
                    capability: BuildStubCapability());

                BrainBase brain = null;
                Assert.DoesNotThrow(
                    () => brain = new NativeMotorCortex(desc, memory, chat, callback),
                    $"BrainId '{brainId}' 应被接受（以 'motor-cortex.' 开头）。");
                Assert.That(brain, Is.Not.Null);
                Assert.That(brain.BrainId, Is.EqualTo(brainId));
            }
        }

        // ===== (3) NativeMotorCortex 走 msai Agent.RunAsync =====

        [Test]
        public async Task NativeMotorCortex_uses_msai_agent_for_InvokeAsync()
        {
            var memory = new InMemoryFakeMemoryService();
            var chat = new FakeChatClient("native-says-hi");
            var callback = new FakePrefrontalCallback();

            var desc = new StandardBrainDescriptor(
                brainId: "motor-cortex.native",
                role: "motor",
                soul: "soul",
                kind: StandardBrainKind.NativeMotorCortex,
                capability: BuildStubCapability());

            var motor = new NativeMotorCortex(desc, memory, chat, callback);
            Assert.That(motor.Agent, Is.Not.Null,
                "NativeMotorCortex 路径下 Agent 应由基类装配出 msai AIAgent。");

            var invocation = new BrainInvocation(
                CorrelationId: "c-1",
                Intent: "请帮我跑工具",
                StructuredInput: null,
                Context: new Dictionary<string, object>());

            var outcome = await motor.InvokeAsync(invocation, CancellationToken.None);

            Assert.That(outcome.IsError, Is.False);
            Assert.That(outcome.Summary, Is.EqualTo("native-says-hi"),
                "Summary 应取 msai AIAgent 的 RunAsync 文本（即 FakeChatClient 固定回复）。");
            Assert.That(chat.CallCount, Is.GreaterThanOrEqualTo(1),
                "底层 FakeChatClient.GetResponseAsync 应被驱动至少一次。");
        }

        // ===== (4) ExternalMotorCortex 走 Adapter Submit→Await 路径 =====

        [Test]
        public async Task ExternalMotorCortex_InvokeAsync_routes_through_adapter_Submit_then_Await()
        {
            var memory = new InMemoryFakeMemoryService();
            var callback = new FakePrefrontalCallback();
            var adapter = new FakeExternalEngineAdapter();
            adapter.EnqueueOutcome(new BrainOutcome(
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

            var brain = new StubExternalMotorCortex(ext, memory, adapter, callback);

            try
            {
                var invocation = new BrainInvocation(
                    CorrelationId: "c-ext",
                    Intent: "请编辑文件",
                    StructuredInput: null,
                    Context: new Dictionary<string, object>());

                var outcome = await brain.InvokeAsync(invocation, CancellationToken.None);

                Assert.That(adapter.SubmitCallCount, Is.EqualTo(1),
                    "Adapter.SubmitAsync 应被调用 1 次。");
                Assert.That(adapter.AwaitCallCount, Is.EqualTo(1),
                    "Adapter.AwaitResultAsync 应被调用 1 次。");
                Assert.That(adapter.SubmittedInvocations[0].Intent, Is.EqualTo("请编辑文件"),
                    "Submit 应原样收到 invocation.Intent。");
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
            var adapter = new FakeExternalEngineAdapter();

            var ext = new ExternalMotorCortexDescriptor(
                brainId: "motor-cortex.fake",
                soul: "fake external",
                engineKind: ExternalEngineKind.Custom,
                engineEndpoint: "no-op");

            var brain = new StubExternalMotorCortex(ext, memory, adapter, callback);

            try
            {
                Assert.That(brain.Agent, Is.Null,
                    "ExternalMotorCortex 路径下基类不装配 msai—Agent 应保持 null（外部引擎自带 LLM）。");
                Assert.That(brain.ShareMode, Is.EqualTo(MemoryShareMode.McpServer),
                    "默认 MemoryShareMode 应等于描述符默认值 McpServer。");
            }
            finally
            {
                await brain.DisposeAsync();
            }
        }

        // ===== (6) Dispose 触发 Adapter.Dispose =====

        [Test]
        public async Task ExternalMotorCortex_DisposeAsync_disposes_adapter()
        {
            var memory = new InMemoryFakeMemoryService();
            var callback = new FakePrefrontalCallback();
            var adapter = new FakeExternalEngineAdapter();

            var ext = new ExternalMotorCortexDescriptor(
                brainId: "motor-cortex.fake",
                soul: "fake external",
                engineKind: ExternalEngineKind.Custom,
                engineEndpoint: "no-op");

            var brain = new StubExternalMotorCortex(ext, memory, adapter, callback);

            Assert.That(adapter.DisposeCallCount, Is.EqualTo(0),
                "构造期不应触发 adapter.Dispose。");

            await brain.DisposeAsync();

            Assert.That(adapter.DisposeCallCount, Is.EqualTo(1),
                "ExternalMotorCortex.DisposeAsync 必须传递 dispose 到底层 Adapter。");
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

        /// <summary>
        /// 用于走 ExternalMotorCortexDescriptor 路径——避免 ClaudeCodeMotorCortex
        /// 触发真实 CLI 探测（EnsureCliInPath 会在 PATH 不含 claude-code 时 throw）。
        /// </summary>
        private sealed class StubExternalMotorCortex : ExternalMotorCortex
        {
            public StubExternalMotorCortex(
                ExternalMotorCortexDescriptor descriptor,
                IMemoryService memory,
                IExternalEngineAdapter adapter,
                IPrefrontalCallback callback)
                : base(descriptor, memory, adapter, callback)
            {
            }
        }
    }
}
#endif
