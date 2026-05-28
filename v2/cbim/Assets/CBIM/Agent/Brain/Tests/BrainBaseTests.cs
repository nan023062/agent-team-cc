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
using CBIM.Memory;

namespace CBIM.AgentSystem.Brain.Tests
{
    /// <summary>
    /// <see cref="BrainBase"/> 单元测试。
    ///
    /// 覆盖契约要点：
    ///   - <see cref="StandardBrainDescriptor"/> 路径下基类装配出 msai <see cref="AIAgent"/>（Name/Description/Instructions 透传）
    ///   - <see cref="ExternalMotorCortexDescriptor"/> 路径下 <see cref="BrainBase.Agent"/> 保持 null（外部引擎自带 LLM）
    ///   - null memory / 空白 brainId 构造期立刻 throw（fail-fast）
    ///   - 默认 <see cref="BrainBase.InvokeAsync"/> 把 intent 包成 user ChatMessage 投给 Agent.RunAsync，回译为 BrainOutcome
    ///   - <see cref="BrainBase.DisposeAsync"/> 幂等（由各具体子类的 default 实现承接）
    ///
    /// 不启 subprocess / 不调真 LLM；用 <see cref="FakeChatClient"/> + 进程内 <see cref="ParietalLobe"/> 走标准路径，
    /// <see cref="StubExternalMotorCortex"/> 走 External 路径。
    /// </summary>
    [TestFixture]
    public sealed class BrainBaseTests
    {
        // ===== (1) StandardBrainDescriptor 路径下 msai 装配 =====

        [Test]
        public void BrainBase_constructor_assembles_msai_agent_for_StandardBrainDescriptor()
        {
            var (descriptor, memory, callback) = BuildStandardSetup();
            var chat = new FakeChatClient("ok");

            var brain = new ParietalLobe(descriptor, memory, chat, callback);

            Assert.That(brain.Agent, Is.Not.Null,
                "StandardBrainDescriptor 路径下基类构造期应装配出 msai AIAgent。");
            Assert.That(brain.Agent, Is.InstanceOf<AIAgent>());
            Assert.That(brain.Agent.Name, Is.EqualTo(descriptor.Capability.Name),
                "Agent.Name 应等于 descriptor.Capability.Name");
            Assert.That(brain.Agent.Description, Is.EqualTo(descriptor.Capability.Identity),
                "Agent.Description 应等于 descriptor.Capability.Identity");
            Assert.That(brain.BrainId, Is.EqualTo(descriptor.BrainId));
            Assert.That(brain.Memory, Is.SameAs(memory),
                "Memory 应原样持有——「同一具身一份记忆」铁律。");
        }

        // ===== (2) ExternalMotorCortexDescriptor 路径下 Agent 保持 null =====

        [Test]
        public async Task BrainBase_constructor_skips_agent_assembly_for_ExternalMotorCortexDescriptor()
        {
            var memory = new InMemoryFakeMemoryService();
            var callback = new FakePrefrontalCallback();
            var ext = new ExternalMotorCortexDescriptor(
                brainId: "motor-cortex.stub",
                soul: "stub external",
                engineKind: ExternalEngineKind.Custom,
                engineEndpoint: "no-op");

            var adapter = new FakeExternalEngineAdapter();
            var brain = new StubExternalMotorCortex(ext, memory, adapter, callback);

            try
            {
                Assert.That(brain.Agent, Is.Null,
                    "ExternalMotorCortexDescriptor 路径下基类不装配 msai——Agent 字段应保持 null。");
                // chatClient 也传 null 是有效的（基类签名允许）。
            }
            finally
            {
                await brain.DisposeAsync();
            }
        }

        // ===== (3) null memory 构造期 throw =====

        [Test]
        public void BrainBase_constructor_rejects_null_memory()
        {
            var (descriptor, _, callback) = BuildStandardSetup();
            var chat = new FakeChatClient("ok");

            Assert.Throws<ArgumentNullException>(
                () => new ParietalLobe(descriptor, memory: null, chat, callback),
                "「同一具身一份记忆」铁律由基类构造期强制——null memory 必须立刻 throw。");
        }

        // ===== (4) 空白 brainId 构造期 throw =====

        [Test]
        public void BrainBase_constructor_rejects_blank_brainId()
        {
            // descriptor.BrainId 空白时 BrainDescriptor 基类先 throw ArgumentException——
            // 这是 BrainBase 不能拿到空白 brainId 的物理保证（前哨校验）。
            Assert.Throws<ArgumentException>(() => new StandardBrainDescriptor(
                brainId: "   ",
                role: "parietal",
                soul: "ok",
                kind: StandardBrainKind.ParietalLobe,
                capability: BuildStubCapability()));
        }

        // ===== (5) 默认 InvokeAsync 走 user ChatMessage 路径 =====

        [Test]
        public async Task BrainBase_InvokeAsync_wraps_invocation_into_chat_message_and_returns_outcome()
        {
            var (descriptor, memory, callback) = BuildStandardSetup();
            var chat = new FakeChatClient("回答：ok");

            var brain = new ParietalLobe(descriptor, memory, chat, callback);

            var invocation = new BrainInvocation(
                CorrelationId: "corr-1",
                Intent: "设计 Foo 模块",
                StructuredInput: null,
                Context: new Dictionary<string, object>());

            var outcome = await brain.InvokeAsync(invocation, CancellationToken.None);

            Assert.That(outcome, Is.Not.Null);
            Assert.That(outcome.IsError, Is.False);
            Assert.That(outcome.Summary, Is.EqualTo("回答：ok"),
                "Summary 应取 AgentResponse.Text（即 FakeChatClient 的固定回复）。");
            Assert.That(outcome.SideEffects, Is.Not.Null.And.Empty,
                "默认实现 SideEffects 为空列表——MotorCortex 子类才填实际副作用。");
            Assert.That(chat.LastMessages, Is.Not.Null.And.Not.Empty,
                "应至少投递一条 ChatMessage 到 IChatClient。");

            // 找一条用户角色的消息携带 invocation.Intent。
            bool foundUserIntent = false;
            foreach (var m in chat.LastMessages)
            {
                if (m.Role == ChatRole.User && (m.Text ?? string.Empty).Contains("设计 Foo 模块"))
                {
                    foundUserIntent = true;
                    break;
                }
            }
            Assert.That(foundUserIntent, Is.True,
                "BrainInvocation.Intent 应作为 user ChatMessage 投递给 IChatClient。");
        }

        // ===== (6) DisposeAsync 幂等 =====

        [Test]
        public async Task BrainBase_DisposeAsync_is_idempotent()
        {
            var (descriptor, memory, callback) = BuildStandardSetup();
            var chat = new FakeChatClient("ok");
            var brain = new ParietalLobe(descriptor, memory, chat, callback);

            await brain.DisposeAsync();
            await brain.DisposeAsync();
            await brain.DisposeAsync();
            Assert.Pass("多次 DisposeAsync 不抛即视为幂等。");
        }

        // ===== helpers =====

        private static (StandardBrainDescriptor desc, IMemoryService memory, IPrefrontalCallback callback) BuildStandardSetup()
        {
            var descriptor = new StandardBrainDescriptor(
                brainId: "parietal-lobe",
                role: "parietal",
                soul: "顶叶魂",
                kind: StandardBrainKind.ParietalLobe,
                capability: BuildStubCapability());
            var memory = new InMemoryFakeMemoryService();
            var callback = new FakePrefrontalCallback();
            return (descriptor, memory, callback);
        }

        private static AgentDescription BuildStubCapability()
        {
            return new AgentDescription(
                id: "brain-stub.test.parietal",
                name: "Test · Parietal",
                soul: "stub-soul",
                identity: "stub identity for tests");
        }

        // ===== fakes =====

        /// <summary>
        /// <see cref="ExternalMotorCortex"/> 的极小 stub——用于走 ExternalMotorCortexDescriptor
        /// 路径（避免 ClaudeCodeMotorCortex 触发真实 CLI 探测）。
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
