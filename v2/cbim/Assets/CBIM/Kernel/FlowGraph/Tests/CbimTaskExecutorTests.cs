#if UNITY_INCLUDE_TESTS
using System;
using System.Collections.Generic;
using System.Runtime.CompilerServices;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Agents.AI;
using Microsoft.Agents.AI.Workflows;
using Microsoft.Extensions.AI;
using NUnit.Framework;
using CBIM.AgentSystem;
using CBIM.Kernel.TaskScheduler;

namespace CBIM.Kernel.FlowGraph.Tests
{
    /// <summary>
    /// CbimTaskExecutor 单元测试。
    ///
    /// 核心检验点（设计裁决）：写 Session 的 instanceId 必须取
    /// CBIM Agent.InstanceId（自生成 GUID），不能取 Microsoft AIAgent.Id
    /// （每次 AsAIAgent 重生）。
    ///
    /// 依赖隔离：
    ///   - IChatClient → FakeChatClient（固定返回一行文本）
    ///   - IAgentSystemSessionWriter → FakeSessionWriter（记录每次 Append 调用）
    ///   - IWorkflowContext → StubWorkflowContext（任何成员被调到都抛，验证 Executor 未触碰）
    /// </summary>
    [TestFixture]
    public sealed class CbimTaskExecutorTests
    {
        [Test]
        public async Task HandleAsync_WritesUserInputAndOutput_UsingCbimInstanceId()
        {
            // === arrange ===
            var fakeChat = new FakeChatClient(replyText: "ok-from-fake");
            var description = new AgentDescription(
                id: "test-desc",
                name: "Test",
                soul: "you are a test agent",
                identity: "test agent for unit tests");

            var system = new CBIM.AgentSystem.AgentSystem(
                descriptions: new[] { description },
                chatClient: fakeChat);

            Agent agent = await system.OpenInstanceAsync(description.Id);

            // sanity: 两个 GUID 来源确实不同——这是本次验证的前提
            Assert.That(agent.InstanceId, Is.Not.Null.And.Not.Empty);
            Assert.That(agent.AIAgent.Id, Is.Not.EqualTo(agent.InstanceId),
                "前提失败：AIAgent.Id 与 Agent.InstanceId 相同，本测试失去意义。");

            var writer = new FakeSessionWriter();
            var executor = new CbimTaskExecutor("test", writer);

            CbimTask task = CbimTask.Create(
                who: agent,
                where: Array.Empty<string>(),
                what: "hello executor");

            var context = new StubWorkflowContext();

            // === act ===
            AgentResponse response = await executor.HandleAsync(task, context, CancellationToken.None);

            // === assert (a) ===
            Assert.That(response, Is.Not.Null, "AgentResponse 不应为 null");
            Assert.That(response.Text, Is.Not.Null.And.Not.Empty, "AgentResponse.Text 不应为空");

            // === assert (b) ===
            Assert.That(writer.Calls.Count, Is.EqualTo(2),
                "应写入 2 条事件（UserInput + Output），实际：" + writer.Calls.Count);

            var first = writer.Calls[0];
            Assert.That(first.Event, Is.InstanceOf<UserInputEvent>(),
                "第一条事件应为 UserInputEvent，实际：" + first.Event.GetType().Name);
            Assert.That(first.InstanceId, Is.EqualTo(agent.InstanceId),
                "UserInput 写入的 instanceId 必须等于 CBIM Agent.InstanceId（非 AIAgent.Id）");
            Assert.That(((UserInputEvent)first.Event).UserMessage, Is.EqualTo("hello executor"));

            var second = writer.Calls[1];
            Assert.That(second.Event, Is.InstanceOf<OutputEvent>(),
                "第二条事件应为 OutputEvent，实际：" + second.Event.GetType().Name);
            Assert.That(second.InstanceId, Is.EqualTo(agent.InstanceId),
                "Output 写入的 instanceId 必须等于 CBIM Agent.InstanceId（非 AIAgent.Id）");
            Assert.That(((OutputEvent)second.Event).OutputText, Is.EqualTo(response.Text),
                "Output 事件的 text 必须与 AgentResponse.Text 一致");

            // 双保险：两条都 != AIAgent.Id
            Assert.That(first.InstanceId, Is.Not.EqualTo(agent.AIAgent.Id),
                "回归保护：instanceId 不能误用 Microsoft AIAgent.Id");
            Assert.That(second.InstanceId, Is.Not.EqualTo(agent.AIAgent.Id),
                "回归保护：instanceId 不能误用 Microsoft AIAgent.Id");

            await system.CloseInstanceAsync(agent);
        }

        // ===== Fakes =====

        private sealed class FakeChatClient : IChatClient
        {
            private readonly string _replyText;

            public FakeChatClient(string replyText)
            {
                _replyText = replyText;
            }

            public Task<ChatResponse> GetResponseAsync(
                IEnumerable<ChatMessage> messages,
                ChatOptions options = null,
                CancellationToken cancellationToken = default)
            {
                var msg = new ChatMessage(ChatRole.Assistant, _replyText);
                var resp = new ChatResponse(msg);
                return Task.FromResult(resp);
            }

            public System.Collections.Generic.IAsyncEnumerable<ChatResponseUpdate> GetStreamingResponseAsync(
                IEnumerable<ChatMessage> messages,
                ChatOptions options = null,
                CancellationToken cancellationToken = default)
            {
                // CbimTaskExecutor 走非流式 RunAsync → IChatClient.GetResponseAsync，
                // 不应触发流式接口。若被调到，立即失败暴露集成漂移。
                throw new NotSupportedException(
                    "FakeChatClient.GetStreamingResponseAsync 未实现——本测试假定 Executor 仅走非流式路径。");
            }

            public object GetService(Type serviceType, object serviceKey = null) => null;

            public void Dispose() { /* nothing to dispose */ }
        }

        private sealed class FakeSessionWriter : IAgentSystemSessionWriter
        {
            public readonly List<(string InstanceId, SessionEvent Event)> Calls
                = new List<(string, SessionEvent)>();

            public void AppendSessionEvent(string instanceId, SessionEvent ev)
            {
                Calls.Add((instanceId, ev));
            }

            public IReadOnlyList<SessionEvent> ReadSessionTail(string instanceId, int n)
            {
                return Array.Empty<SessionEvent>();
            }
        }

        /// <summary>
        /// 任何成员被触发都抛——验证 Executor 当前版本不依赖 IWorkflowContext。
        /// 若未来 Executor 真要用 context，此 stub 会立即失败，提示同步更新测试假对象。
        /// </summary>
        private sealed class StubWorkflowContext : IWorkflowContext
        {
            public IReadOnlyDictionary<string, string> TraceContext
                => throw NotUsed();

            public bool ConcurrentRunsEnabled
                => throw NotUsed();

            public ValueTask AddEventAsync(WorkflowEvent workflowEvent, CancellationToken cancellationToken = default)
                => throw NotUsed();

            public ValueTask QueueClearScopeAsync(string scopeName = null, CancellationToken cancellationToken = default)
                => throw NotUsed();

            public ValueTask QueueStateUpdateAsync<T>(string key, T value, string scopeName = null, CancellationToken cancellationToken = default)
                => throw NotUsed();

            public ValueTask<T> ReadOrInitStateAsync<T>(string key, Func<T> initialStateFactory, string scopeName = null, CancellationToken cancellationToken = default)
                => throw NotUsed();

            public ValueTask<T> ReadStateAsync<T>(string key, string scopeName = null, CancellationToken cancellationToken = default)
                => throw NotUsed();

            public ValueTask<HashSet<string>> ReadStateKeysAsync(string scopeName = null, CancellationToken cancellationToken = default)
                => throw NotUsed();

            public ValueTask RequestHaltAsync()
                => throw NotUsed();

            public ValueTask SendMessageAsync(object message, string targetId, CancellationToken cancellationToken = default)
                => throw NotUsed();

            public ValueTask YieldOutputAsync(object output, CancellationToken cancellationToken = default)
                => throw NotUsed();

            private static NotSupportedException NotUsed(
                [CallerMemberName] string member = null)
                => new NotSupportedException(
                    $"StubWorkflowContext.{member} 不应被 CbimTaskExecutor 调用——测试假对象未实现。");
        }
    }
}
#endif
