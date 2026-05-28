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
using CBIM.Channel;
using CBIM.Memory;

// Alias 消歧——CBIM.AgentSystem 既是 namespace 又是 sealed class，无法继承；
// 测试代码用别名直接引用 AgentSystem 类型，避免「AgentSystem.AgentSystem」重名段。
using AgentSystemService = CBIM.AgentSystem.AgentSystem;

namespace CBIM.Channel.Tests
{
    /// <summary>
    /// <see cref="ChannelService"/> + <see cref="Channel"/> SendAsync 单元测试。
    ///
    /// 覆盖：
    ///   - OpenChannelAsync 返回的 Channel.Agent 引用 = Prefrontal.Agent
    ///   - SendAsync 返回的 outcome.ResultText 来自 AIAgent.RunAsync
    ///   - SendAsync 完成时 OnOutput 事件被发射
    ///   - SendAsync 路径上的异常被吞并转译为 IsError outcome（不向上传播）
    ///   - CloseChannelAsync 触发底层 Agent.DisposeAsync
    ///   - OpenChannelAsync 拒绝空白 WorkspaceRoot
    ///
    /// 不启 subprocess、不调真 LLM；用 <see cref="FakeChatClient"/> 走 msai 装配。
    /// </summary>
    [TestFixture]
    public sealed class ChannelSendAsyncTests
    {
        private FakeChatClient _chat;
        private AgentSystemService _system;
        private ChannelService _channels;
        private AgentDescription _desc;

        [SetUp]
        public void SetUp()
        {
            _chat = new FakeChatClient("agent-reply");
            _desc = new AgentDescription(
                id: "channel-test",
                name: "Channel Test",
                soul: "soul",
                identity: "identity",
                memoryFactory: _ => new InMemoryFakeMemoryService());
            _system = new AgentSystemService(new[] { _desc }, _chat);
            _channels = new ChannelService(_system);
        }

        // ===== (1) Channel.Agent == Prefrontal.Agent =====

        [Test]
        public async Task ChannelService_OpenChannelAsync_returns_channel_with_Agent_equal_to_Prefrontal_Agent()
        {
            var channel = await _channels.OpenChannelAsync(_desc.Id, new ChannelOptions
            {
                WorkspaceRoot = System.IO.Path.GetTempPath(),
            });

            try
            {
                Assert.That(channel, Is.Not.Null);
                Assert.That(channel.ChannelId, Is.Not.Null.And.Not.Empty);
                Assert.That(channel.Agent, Is.Not.Null);
                Assert.That(channel.Session, Is.Not.Null);

                // Channel.Instance 是 internal——通过反射读出来验证「Channel.Agent = instance.Prefrontal.Agent」。
                var instance = GetInternalInstance(channel);
                Assert.That(instance, Is.Not.Null,
                    "Channel.Instance 属性反射读取失败——可能字段重命名，需同步更新本测试。");
                Assert.That(channel.Agent, Is.SameAs(instance.Prefrontal.Agent),
                    "Channel.Agent 必须 = instance.Prefrontal.Agent——「Channel 实际投递目标即主脑」铁律。");
                Assert.That(channel.Session, Is.SameAs(instance.Session),
                    "Channel.Session 必须 = 底层 instance.Session（不重建）。");
            }
            finally
            {
                await _channels.CloseChannelAsync(channel.ChannelId);
            }
        }

        private static Agent GetInternalInstance(Channel channel)
        {
            var prop = typeof(Channel).GetProperty(
                "Instance",
                System.Reflection.BindingFlags.Instance |
                System.Reflection.BindingFlags.NonPublic |
                System.Reflection.BindingFlags.Public);
            return prop?.GetValue(channel) as Agent;
        }

        // ===== (2) SendAsync.ResultText 来自 AIAgent.RunAsync =====

        [Test]
        public async Task Channel_SendAsync_returns_outcome_text_from_AIAgent_RunAsync()
        {
            var channel = await _channels.OpenChannelAsync(_desc.Id, new ChannelOptions
            {
                WorkspaceRoot = System.IO.Path.GetTempPath(),
            });

            try
            {
                var outcome = await channel.SendAsync("你好");

                Assert.That(outcome, Is.Not.Null);
                Assert.That(outcome.IsError, Is.False);
                Assert.That(outcome.ErrorMessage, Is.Null);
                Assert.That(outcome.ResultText, Is.EqualTo("agent-reply"),
                    "ResultText 应取自底层 FakeChatClient 的固定回复（msai 装配后透传）。");
            }
            finally
            {
                await _channels.CloseChannelAsync(channel.ChannelId);
            }
        }

        // ===== (3) OnOutput 事件被发射 =====

        [Test]
        public async Task Channel_SendAsync_emits_OnOutput_event()
        {
            var channel = await _channels.OpenChannelAsync(_desc.Id, new ChannelOptions
            {
                WorkspaceRoot = System.IO.Path.GetTempPath(),
            });

            try
            {
                var events = new List<ChannelOutputEvent>();
                channel.OnOutput += ev => events.Add(ev);

                await channel.SendAsync("foo");
                await channel.SendAsync("bar");

                Assert.That(events.Count, Is.EqualTo(2),
                    "每次 SendAsync 应发射一次 OnOutput。");
                Assert.That(events[0].ChannelId, Is.EqualTo(channel.ChannelId));
                Assert.That(events[0].Text, Is.EqualTo("agent-reply"));
                Assert.That(events[1].Text, Is.EqualTo("agent-reply"));
            }
            finally
            {
                await _channels.CloseChannelAsync(channel.ChannelId);
            }
        }

        // ===== (4) 异常转译为 IsError outcome =====

        [Test]
        public async Task Channel_SendAsync_returns_IsError_outcome_on_exception()
        {
            // 用一个「下次调用必抛」的 chat client 重建装配。
            var throwingChat = new ThrowingChatClient("boom");
            var desc = new AgentDescription(
                id: "channel-throw",
                name: "Channel Throw",
                soul: "soul",
                identity: "identity",
                memoryFactory: _ => new InMemoryFakeMemoryService());
            var system = new AgentSystemService(new[] { desc }, throwingChat);
            var channels = new ChannelService(system);

            var channel = await channels.OpenChannelAsync(desc.Id, new ChannelOptions
            {
                WorkspaceRoot = System.IO.Path.GetTempPath(),
            });

            try
            {
                ChannelOutputEvent lastEvent = null;
                channel.OnOutput += ev => lastEvent = ev;

                ChannelOutcome outcome = null;
                Assert.DoesNotThrowAsync(async () => outcome = await channel.SendAsync("ping"),
                    "SendAsync 应吞掉底层异常，不向上抛——契约约定。");

                Assert.That(outcome, Is.Not.Null);
                Assert.That(outcome.IsError, Is.True);
                Assert.That(outcome.ResultText, Is.Empty);
                Assert.That(outcome.ErrorMessage, Does.Contain("boom"),
                    "ErrorMessage 应携带底层异常摘要。");

                Assert.That(lastEvent, Is.Not.Null, "失败路径也应发射 OnOutput。");
                Assert.That(lastEvent.Text, Does.StartWith("[ERROR]"),
                    "失败 OnOutput 文本应以 '[ERROR]' 前缀开头。");
            }
            finally
            {
                await channels.CloseChannelAsync(channel.ChannelId);
            }
        }

        // ===== (5) CloseChannelAsync 触发 Agent.DisposeAsync =====

        [Test]
        public async Task ChannelService_CloseChannelAsync_disposes_underlying_AgentInstance()
        {
            // 用「带计数的 Memory」反推 Agent.DisposeAsync 是否被调到——
            // Agent.DisposeAsync 会传递到 Memory.DisposeAsync。
            var spy = new InMemoryFakeMemoryService();
            var desc = new AgentDescription(
                id: "channel-dispose",
                name: "Channel Dispose",
                soul: "soul",
                identity: "identity",
                memoryFactory: _ => spy);
            var system = new AgentSystemService(new[] { desc }, _chat);
            var channels = new ChannelService(system);

            var channel = await channels.OpenChannelAsync(desc.Id, new ChannelOptions
            {
                WorkspaceRoot = System.IO.Path.GetTempPath(),
            });

            Assert.That(spy.DisposeCallCount, Is.EqualTo(0),
                "OpenChannelAsync 不应提前 dispose memory。");

            await channels.CloseChannelAsync(channel.ChannelId);

            Assert.That(spy.DisposeCallCount, Is.GreaterThanOrEqualTo(1),
                "CloseChannelAsync 必须传递 dispose 到底层 Agent.Memory。");

            // 注册表已清空
            Assert.That(channels.GetChannel(channel.ChannelId), Is.Null,
                "CloseChannelAsync 后 GetChannel 应返回 null。");
            Assert.That(channels.ListChannels(), Is.Empty);
        }

        // ===== (6) 空白 WorkspaceRoot → throw =====

        [Test]
        public void ChannelService_OpenChannelAsync_rejects_blank_WorkspaceRoot()
        {
            Assert.ThrowsAsync<ArgumentException>(async () =>
                await _channels.OpenChannelAsync(_desc.Id, new ChannelOptions
                {
                    WorkspaceRoot = "   ",
                }));

            Assert.ThrowsAsync<ArgumentException>(async () =>
                await _channels.OpenChannelAsync(_desc.Id, new ChannelOptions
                {
                    WorkspaceRoot = null,
                }));
        }

        // ===== Local fakes =====

        private sealed class FakeChatClient : IChatClient
        {
            private readonly string _replyText;
            public int CallCount { get; private set; }
            public FakeChatClient(string replyText) { _replyText = replyText; }
            public Task<ChatResponse> GetResponseAsync(
                IEnumerable<ChatMessage> messages, ChatOptions options = null,
                CancellationToken cancellationToken = default)
            {
                CallCount++;
                return Task.FromResult(new ChatResponse(new ChatMessage(ChatRole.Assistant, _replyText)));
            }
            public IAsyncEnumerable<ChatResponseUpdate> GetStreamingResponseAsync(
                IEnumerable<ChatMessage> messages, ChatOptions options = null,
                CancellationToken cancellationToken = default)
                => throw new NotSupportedException();
            public object GetService(Type serviceType, object serviceKey = null) => null;
            public void Dispose() { }
        }

        /// <summary>每次 GetResponseAsync 都抛——用于验证 SendAsync 错误路径转译。</summary>
        private sealed class ThrowingChatClient : IChatClient
        {
            private readonly string _message;
            public ThrowingChatClient(string message) { _message = message; }
            public Task<ChatResponse> GetResponseAsync(
                IEnumerable<ChatMessage> messages, ChatOptions options = null,
                CancellationToken cancellationToken = default)
                => throw new InvalidOperationException(_message);
            public IAsyncEnumerable<ChatResponseUpdate> GetStreamingResponseAsync(
                IEnumerable<ChatMessage> messages, ChatOptions options = null,
                CancellationToken cancellationToken = default)
                => throw new NotSupportedException();
            public object GetService(Type serviceType, object serviceKey = null) => null;
            public void Dispose() { }
        }

        /// <summary>In-memory IMemoryService 桩——脑区装配链需要，数据面方法返回最小实装。</summary>
        private sealed class InMemoryFakeMemoryService : IMemoryService
        {
            private readonly Dictionary<string, MemoryEntry> _entries =
                new Dictionary<string, MemoryEntry>(StringComparer.Ordinal);
            public int DisposeCallCount { get; private set; }

            public void Write(MemoryEntry entry) { _entries[entry.Id] = entry; }
            public MemoryEntry Get(string id)
                => string.IsNullOrWhiteSpace(id) ? null : _entries.TryGetValue(id, out var e) ? e : null;
            public IReadOnlyList<MemoryEntry> Query(string text, int topK) => Array.Empty<MemoryEntry>();
            public IReadOnlyList<MemoryEntry> Scan(MemoryScanFilter filter) => Array.Empty<MemoryEntry>();
            public MemoryStats Stats() => new MemoryStats(_entries.Count, null, null);
            public ValueTask DisposeAsync()
            {
                DisposeCallCount++;
                return default;
            }
        }
    }
}
#endif
