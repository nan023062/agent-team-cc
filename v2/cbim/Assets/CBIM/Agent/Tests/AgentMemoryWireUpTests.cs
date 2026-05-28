#if UNITY_INCLUDE_TESTS
using System;
using System.Collections.Generic;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.AI;
using NUnit.Framework;
using CBIM.AgentSystem;
using CBIM.Memory;
using CBIM.Storage;

namespace CBIM.AgentSystem.Tests
{
    /// <summary>
    /// Agent Memory 装配链测试——验证 IMemoryService 在 AgentSystem.OpenInstance
    /// 路径上的三级优先级 + Agent.DisposeAsync 链路。
    ///
    /// 不验数据路径（FileMemoryBackendTests 已覆盖）；只验装配链：
    ///   (a) AgentDescription.MemoryFactory 可空，构造不报错
    ///   (b) OpenInstanceOptions.MemoryFactoryOverride 优先级最高
    ///   (c) Override 缺省时落到 desc.MemoryFactory
    ///   (d) 两者都缺时 + FileBackend 已注入 → 默认 FileMemoryBackend，子目录含 instanceId
    ///   (e) Agent.DisposeAsync 调 Memory.DisposeAsync
    /// </summary>
    [TestFixture]
    public sealed class AgentMemoryWireUpTests
    {
        private string _root;
        private FileBackend _backend;

        [SetUp]
        public void SetUp()
        {
            _root = Path.Combine(Path.GetTempPath(),
                "cbim-agent-mem-tests-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(_root);
            _backend = new FileBackend(_root);
        }

        [TearDown]
        public void TearDown()
        {
            if (!string.IsNullOrEmpty(_root) && Directory.Exists(_root))
            {
                try { Directory.Delete(_root, recursive: true); }
                catch (IOException) { /* 测试机偶发占用，忽略 */ }
            }
        }

        // ===== (a) AgentDescription.MemoryFactory 可空通过 ctor =====

        [Test]
        public void AgentDescription_NullMemoryFactory_DoesNotThrow()
        {
            // 不传 memoryFactory（默认 null）必须能构造成功——
            // 描述符不强加 Memory 选型，由 OpenInstance 选默认。
            var desc = new AgentDescription(
                id: "wire-a",
                name: "Wire A",
                soul: "you are wire a",
                identity: "wire test agent");

            Assert.That(desc.MemoryFactory, Is.Null,
                "缺省 memoryFactory 应保持 null（不预填默认）——默认由 AgentSystem 装配时决定");
        }

        // ===== (b) MemoryFactoryOverride 优先级最高 =====

        [Test]
        public async Task OpenInstanceAsync_WithOverride_PrefersOverrideOver_DescriptionFactory()
        {
            // 描述符自带工厂返 stubFromDesc；override 返 stubFromOverride。
            // 期望：Agent.Memory == stubFromOverride。
            var fromDesc = new SpyMemoryService(label: "from-desc");
            var fromOverride = new SpyMemoryService(label: "from-override");

            var desc = new AgentDescription(
                id: "wire-b",
                name: "Wire B",
                soul: "soul",
                identity: "identity",
                memoryFactory: _ => fromDesc);

            var system = new AgentSystem(
                descriptions: new[] { desc },
                chatClient: new FakeChatClient("ok"));

            var options = new OpenInstanceOptions
            {
                MemoryFactoryOverride = _ => fromOverride,
            };

            Agent agent = await system.OpenInstanceAsync(desc.Id, options);

            try
            {
                Assert.That(agent.Memory, Is.SameAs(fromOverride),
                    "Override 必须压过 desc.MemoryFactory");
                Assert.That(agent.Memory, Is.Not.SameAs(fromDesc),
                    "desc.MemoryFactory 不应被调用——回归保护");
            }
            finally
            {
                await system.CloseInstanceAsync(agent);
            }
        }

        // ===== (c) 仅描述符工厂 → 用描述符工厂 =====

        [Test]
        public async Task OpenInstanceAsync_NoOverride_UsesDescriptionFactory()
        {
            var fromDesc = new SpyMemoryService(label: "from-desc-only");

            var desc = new AgentDescription(
                id: "wire-c",
                name: "Wire C",
                soul: "soul",
                identity: "identity",
                memoryFactory: _ => fromDesc);

            var system = new AgentSystem(
                descriptions: new[] { desc },
                chatClient: new FakeChatClient("ok"));

            Agent agent = await system.OpenInstanceAsync(desc.Id);

            try
            {
                Assert.That(agent.Memory, Is.SameAs(fromDesc),
                    "无 override 时应用 desc.MemoryFactory 产物");
            }
            finally
            {
                await system.CloseInstanceAsync(agent);
            }
        }

        // ===== (d) 两者都缺 + FileBackend 已注入 → 默认 FileMemoryBackend, subDir 含 instanceId =====

        [Test]
        public async Task OpenInstanceAsync_NoFactories_WithFileBackend_BuildsDefaultBackend_WithInstanceIdSubDir()
        {
            var desc = new AgentDescription(
                id: "wire-d",
                name: "Wire D",
                soul: "soul",
                identity: "identity");
            // 注意：memoryFactory 缺省 = null

            var system = new AgentSystem(
                descriptions: new[] { desc },
                chatClient: new FakeChatClient("ok"),
                fileBackend: _backend);

            Agent agent = await system.OpenInstanceAsync(desc.Id);

            try
            {
                Assert.That(agent.Memory, Is.Not.Null, "应自动装配默认 Memory");
                Assert.That(agent.Memory, Is.InstanceOf<FileMemoryBackend>(),
                    "默认 Memory 应为 FileMemoryBackend");

                // 装配链产物：subDir = "memory/{instanceId}"——通过写入一条 entry
                // 后检查落盘路径来反推 subDir 是否含 instanceId。
                var probe = new MemoryEntry(
                    Id: "probe",
                    Source: "wireup-test",
                    CreatedAt: DateTime.UtcNow,
                    Text: "ping",
                    Tags: Array.Empty<string>());
                agent.Memory.Write(probe);

                string expected = Path.Combine(
                    _root, ".cbim", "memory", agent.InstanceId, "probe.json");
                Assert.That(File.Exists(expected), Is.True,
                    "默认装配应使用 subDir='memory/{instanceId}'；期望落盘到 " + expected);
            }
            finally
            {
                await system.CloseInstanceAsync(agent);
            }
        }

        // ===== (e) Agent.DisposeAsync 调用 Memory.DisposeAsync =====

        [Test]
        public async Task AgentDisposeAsync_InvokesMemoryDisposeAsync_AtLeastOnce()
        {
            var spy = new SpyMemoryService(label: "spy");

            var desc = new AgentDescription(
                id: "wire-e",
                name: "Wire E",
                soul: "soul",
                identity: "identity",
                memoryFactory: _ => spy);

            var system = new AgentSystem(
                descriptions: new[] { desc },
                chatClient: new FakeChatClient("ok"));

            Agent agent = await system.OpenInstanceAsync(desc.Id);

            // 预检：装配后未触发 dispose
            Assert.That(spy.DisposeCallCount, Is.EqualTo(0),
                "OpenInstance 不应提前 dispose memory");

            await system.CloseInstanceAsync(agent);

            Assert.That(spy.DisposeCallCount, Is.GreaterThanOrEqualTo(1),
                "Agent.DisposeAsync 必须传递 dispose 到 Memory");
        }

        // ===== Fakes =====

        /// <summary>
        /// IMemoryService 桩——只记录 DisposeAsync 调用次数。
        /// 数据面方法全 throw NotSupportedException——本测试不验数据路径，
        /// 若被意外触发立即失败暴露集成漂移。
        /// </summary>
        private sealed class SpyMemoryService : IMemoryService
        {
            private readonly string _label;
            public int DisposeCallCount { get; private set; }

            public SpyMemoryService(string label)
            {
                _label = label;
            }

            public void Write(MemoryEntry entry) =>
                throw new NotSupportedException(
                    "SpyMemoryService.Write 不应被装配链测试触发（label=" + _label + ")");

            public MemoryEntry Get(string id) =>
                throw new NotSupportedException(
                    "SpyMemoryService.Get 不应被装配链测试触发（label=" + _label + ")");

            public IReadOnlyList<MemoryEntry> Query(string text, int topK) =>
                throw new NotSupportedException(
                    "SpyMemoryService.Query 不应被装配链测试触发（label=" + _label + ")");

            public IReadOnlyList<MemoryEntry> Scan(MemoryScanFilter filter) =>
                throw new NotSupportedException(
                    "SpyMemoryService.Scan 不应被装配链测试触发（label=" + _label + ")");

            public MemoryStats Stats() =>
                throw new NotSupportedException(
                    "SpyMemoryService.Stats 不应被装配链测试触发（label=" + _label + ")");

            public ValueTask DisposeAsync()
            {
                DisposeCallCount++;
                return default;
            }

            public override string ToString() => "SpyMemoryService(" + _label + ")";
        }

        /// <summary>
        /// IChatClient 桩——AgentSystem.OpenInstance 走 AsAIAgent 时需要一个有效的
        /// IChatClient 引用；本测试不发起 LLM 调用，因此只需 GetResponseAsync 给出
        /// 一个合法响应即可。流式接口被触发即失败（防漂移）。
        /// 复制自 CbimTaskExecutorTests 的同名 fake，保持风格一致。
        /// </summary>
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

            public IAsyncEnumerable<ChatResponseUpdate> GetStreamingResponseAsync(
                IEnumerable<ChatMessage> messages,
                ChatOptions options = null,
                CancellationToken cancellationToken = default)
            {
                throw new NotSupportedException(
                    "FakeChatClient.GetStreamingResponseAsync 未实现——本测试不走流式路径。");
            }

            public object GetService(Type serviceType, object serviceKey = null) => null;

            public void Dispose() { /* nothing to dispose */ }
        }
    }
}
#endif
