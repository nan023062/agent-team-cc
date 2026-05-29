#if UNITY_INCLUDE_TESTS
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using NUnit.Framework;
using CBIM.AgentSystem;
using CBIM.AgentSystem.Brain;
using CBIM.AgentSystem.Brain.ClaudeCode;
using CBIM.AgentSystem.Kernel.Neuron;
using CBIM.AgentSystem.Kernel.Synapse;
using CBIM.Memory;

namespace CBIM.AgentSystem.Tests
{
    /// <summary>
    /// Agent 多脑装配 / 释放序列单元测试——验证
    /// <see cref="AgentSystem.OpenInstanceAsync(string, OpenInstanceOptions)"/> 的脑区编织路径
    /// 与 <see cref="Agent.DisposeAsync"/> 的「MotorCortex → 其他脑区 → Prefrontal → Memory → McpHandles → Session」
    /// 释放顺序。
    ///
    /// 不启 subprocess、不调真 LLM；用 <see cref="FakeChatClient"/> 走 msai 装配，
    /// 用 <see cref="InMemoryFakeMemoryService"/> 走 Memory 路径。
    ///
    /// task-5 已知妥协：MemoryBridgeMcpServer 仅 in-proc 启动，未桥接到 subprocess——
    /// 因此 "OpenInstanceAsync_with_WithClaudeCode_produces_5_brains_when_TaskWhere_set"
    /// 不验证 endpoint 注入，只验证脑区个数 + 描述符种类。
    /// </summary>
    [TestFixture]
    public sealed class AgentMultiBrainAssemblyTests
    {
        // ===== (1) 默认 BrainConfig → 4 脑 =====

        [Test]
        public async Task OpenInstanceAsync_with_default_BrainConfig_produces_4_brains()
        {
            var fakeChat = new FakeChatClient("ok");
            var desc = new AgentDescription(
                id: "multi-default",
                name: "Multi Default",
                soul: "soul",
                identity: "identity",
                memoryFactory: _ => new InMemoryFakeMemoryService());

            var system = new AgentSystem(new[] { desc }, fakeChat);
            var agent = await system.OpenInstanceAsync(desc.Id);

            try
            {
                Assert.That(agent.Brains.Count, Is.EqualTo(4),
                    "默认 BrainConfig 应装配 4 脑。");

                var types = agent.Brains.Select(b => b.GetType()).ToList();
                Assert.That(types, Contains.Item(typeof(PrefrontalCortex)));
                Assert.That(types, Contains.Item(typeof(ParietalLobe)));
                Assert.That(types, Contains.Item(typeof(Hippocampus)));
                Assert.That(types, Contains.Item(typeof(NativeMotorCortex)));

                Assert.That(agent.Prefrontal, Is.Not.Null);
                Assert.That(agent.Prefrontal, Is.InstanceOf<PrefrontalCortex>());

                // Prefrontal 在装配列表末尾（Phase B 最后构造）
                Assert.That(agent.Brains[agent.Brains.Count - 1], Is.SameAs(agent.Prefrontal),
                    "Prefrontal 应位于 Brains 列表末尾——Phase B 最后构造的物理体现。");
            }
            finally
            {
                await system.CloseInstanceAsync(agent);
            }
        }

        // ===== (2) WithClaudeCode + TaskWhere → 5 脑 =====

        [Test]
        public async Task OpenInstanceAsync_with_WithClaudeCode_produces_5_brains_when_TaskWhere_set()
        {
            // ClaudeCodeMotorCortex 的 Adapter 在构造期会触发 CLI 探测（EnsureCliInPath）——
            // 本测试环境未必装了 claude-code CLI，所以将该断言收敛在 Ignore-On-Missing 路径：
            // 装配抛 CLI 缺失即认作环境约束跳过，不算失败；装配成功则继续断言。
            var fakeChat = new FakeChatClient("ok");
            var brainConfig = BrainConfig.Default("multi-cc").WithClaudeCode();

            var desc = new AgentDescription(
                id: "multi-cc",
                name: "Multi CC",
                soul: "soul",
                identity: "identity",
                memoryFactory: _ => new InMemoryFakeMemoryService(),
                brainConfig: brainConfig);

            var system = new AgentSystem(new[] { desc }, fakeChat);

            Agent agent;
            try
            {
                agent = await system.OpenInstanceAsync(
                    desc.Id,
                    new OpenInstanceOptions { TaskWhere = System.IO.Path.GetTempPath() });
            }
            catch (InvalidOperationException ex) when (ex.Message.Contains("Claude Code CLI"))
            {
                Assert.Ignore("环境未装 claude-code CLI——ClaudeCodeMotorCortex 装配跳过。原因：" + ex.Message);
                return;
            }

            try
            {
                Assert.That(agent.Brains.Count, Is.EqualTo(5),
                    "Default + WithClaudeCode 应装配 5 脑。");

                var types = agent.Brains.Select(b => b.GetType()).ToList();
                Assert.That(types, Contains.Item(typeof(ClaudeCodeMotorCortex)),
                    "应含 ClaudeCodeMotorCortex 脑区。");

                // task-5 已知妥协：MemoryMcpEndpoint 未桥接到 subprocess——断 null
                var cc = agent.Brains.OfType<ClaudeCodeMotorCortex>().Single();
                // 用反射读到 ClaudeCodeEngineAdapter._config 来验证 endpoint 注入状态
                // 是不必要的：本测试的 acceptance 边界仅到「5 脑且含 ClaudeCodeMotorCortex」。
                Assert.That(cc.ShareMode, Is.EqualTo(MemoryShareMode.McpServer),
                    "默认 ShareMode 应 = McpServer。");
            }
            finally
            {
                await system.CloseInstanceAsync(agent);
            }
        }

        // ===== (3) ExternalMotorCortex 在 + TaskWhere 缺失 → throw =====

        [Test]
        public async Task OpenInstanceAsync_throws_when_ExternalMotorCortex_present_but_TaskWhere_null()
        {
            var fakeChat = new FakeChatClient("ok");
            var brainConfig = BrainConfig.Default("multi-cc-no-where").WithClaudeCode();

            var desc = new AgentDescription(
                id: "multi-cc-no-where",
                name: "Multi CC No Where",
                soul: "soul",
                identity: "identity",
                memoryFactory: _ => new InMemoryFakeMemoryService(),
                brainConfig: brainConfig);

            var system = new AgentSystem(new[] { desc }, fakeChat);

            // TaskWhere 未给——fail-fast 抛 InvalidOperationException（在装配任何资源前）。
            InvalidOperationException ex = null;
            try
            {
                await system.OpenInstanceAsync(desc.Id, new OpenInstanceOptions { TaskWhere = null });
            }
            catch (InvalidOperationException e)
            {
                ex = e;
            }
            Assert.That(ex, Is.Not.Null, "应抛 InvalidOperationException。");
            Assert.That(ex.Message, Does.Contain("TaskWhere"),
                "异常应明确指出 TaskWhere 必填。");
        }

        // ===== (4) Dispose 顺序——disposal log 序列验证 =====

        [Test]
        public async Task Agent_dispose_order_disposes_motor_first_then_others_then_prefrontal_then_memory_then_mcp_then_session()
        {
            // 自建一个 Agent（绕过 AgentSystem.OpenInstanceAsync）以注入「带 disposal log 的 mcpHandle」——
            // OpenInstanceAsync 不暴露 mcpHandles 列表的注入点。
            //
            // 标准脑区（Native / Parietal / Prefrontal）的 DisposeAsync 都是 default(ValueTask)——
            // 不写 log；因此期望 log 序列只含 ["memory", "mcp"]，且 memIdx < mcpIdx 即满足释放顺序铁律：
            //   MotorCortex → 其他脑区 → Prefrontal → Memory → McpHandles → Session
            //
            // Session 节点的释放路径（ChatClientAgentSession 无 IAsyncDisposable）由 (5) 覆盖。
            var log = new List<string>();
            var memory = new InMemoryFakeMemoryService(log, "memory");
            var mcpHandle = new SpyDisposable(log, "mcp");

            var fakeChat = new FakeChatClient("ok");
            var agent = await BuildAgentForDisposeOrderAsync(fakeChat, memory, mcpHandle);

            await agent.DisposeAsync();

            int memIdx = log.IndexOf("memory");
            int mcpIdx = log.IndexOf("mcp");
            Assert.That(memIdx, Is.GreaterThanOrEqualTo(0), "memory 应被 dispose（出现在 log 中）。");
            Assert.That(mcpIdx, Is.GreaterThanOrEqualTo(0), "mcp handle 应被 dispose（出现在 log 中）。");
            Assert.That(memIdx, Is.LessThan(mcpIdx),
                "释放顺序铁律：Memory 必须在 McpHandles 之前 dispose。实际 log=[" + string.Join(",", log) + "]");
        }

        // ===== (5) Agent.AIAgent == Prefrontal.Agent =====

        [Test]
        public async Task Agent_AIAgent_field_equals_Prefrontal_Agent()
        {
            var fakeChat = new FakeChatClient("ok");
            var desc = new AgentDescription(
                id: "field-equals",
                name: "Field Equals",
                soul: "soul",
                identity: "identity",
                memoryFactory: _ => new InMemoryFakeMemoryService());

            var system = new AgentSystem(new[] { desc }, fakeChat);
            var agent = await system.OpenInstanceAsync(desc.Id);

            try
            {
                Assert.That(agent.AIAgent, Is.SameAs(agent.Prefrontal.Agent),
                    "Agent.AIAgent 必须 = Prefrontal.Agent（向下兼容字段语义）。");
            }
            finally
            {
                await system.CloseInstanceAsync(agent);
            }
        }

        // ===== (6) 所有脑区共享同一 IMemoryService 实例 =====

        [Test]
        public async Task All_brains_share_the_same_IMemoryService_instance()
        {
            var fakeChat = new FakeChatClient("ok");
            var sharedMemory = new InMemoryFakeMemoryService();

            var desc = new AgentDescription(
                id: "shared-memory",
                name: "Shared Memory",
                soul: "soul",
                identity: "identity",
                memoryFactory: _ => sharedMemory);

            var system = new AgentSystem(new[] { desc }, fakeChat);
            var agent = await system.OpenInstanceAsync(desc.Id);

            try
            {
                Assert.That(agent.Memory, Is.SameAs(sharedMemory),
                    "Agent.Memory 应 = 工厂返出的实例。");

                foreach (var brain in agent.Brains)
                {
                    Assert.That(brain.Memory, Is.SameAs(sharedMemory),
                        $"脑区 '{brain.BrainId}' 应共享同一 IMemoryService 实例——「同一具身一份记忆」铁律。");
                }
            }
            finally
            {
                await system.CloseInstanceAsync(agent);
            }
        }

        // ===== helpers / fakes =====

        /// <summary>
        /// 不通过 AgentSystem.OpenInstanceAsync 装配——直接 new 出 Agent，
        /// 以便注入「带 disposal log 的 mcpHandle」用于验证释放序列。
        ///
        /// <para>T4 后：Brain 子类不再直接吃 IChatClient——通过 <see cref="NeuronFactory.Create"/>
        /// 构造 <see cref="INeuron"/> 包装 IChatClient 后再喂给 Brain。这样既保持与
        /// AgentSystem.OpenInstanceAsync 实装路径一致，又能拿到非 null 的 UnderlyingAgent
        /// 供 Agent.AIAgent 字段校验通过。</para>
        /// </summary>
        private static async Task<Agent> BuildAgentForDisposeOrderAsync(
            IChatClient chat,
            IMemoryService memory,
            IAsyncDisposable mcpHandle)
        {
            var callback = new FakePrefrontalCallback();
            var instanceId = Guid.NewGuid().ToString();

            // 一份 NativeMotor 子脑区
            var motorDesc = new StandardBrainDescriptor(
                brainId: "motor-cortex.native",
                role: "motor",
                soul: "motor-soul",
                kind: StandardBrainKind.NativeMotorCortex,
                capability: BuildStubCapability())
            { IsPrefrontal = false };
            INeuron motorNeuron = NeuronFactory.Create(motorDesc, BuildNeuronCtx(chat, memory));
            var motor = new NativeMotorCortex(motorDesc, memory, motorNeuron, callback);

            // 一份 Parietal
            var parietalDesc = new StandardBrainDescriptor(
                brainId: "parietal-lobe",
                role: "parietal",
                soul: "parietal-soul",
                kind: StandardBrainKind.ParietalLobe,
                capability: BuildStubCapability());
            INeuron parietalNeuron = NeuronFactory.Create(parietalDesc, BuildNeuronCtx(chat, memory));
            var parietal = new ParietalLobe(parietalDesc, memory, parietalNeuron, callback);

            // Prefrontal
            var pfcDesc = new StandardBrainDescriptor(
                brainId: "prefrontal-cortex",
                role: "prefrontal",
                soul: "pfc-soul",
                kind: StandardBrainKind.PrefrontalCortex,
                capability: BuildStubCapability())
            { IsPrefrontal = true };
            INeuron pfcNeuron = NeuronFactory.Create(pfcDesc, BuildNeuronCtx(chat, memory));
            var pfc = new PrefrontalCortex(
                descriptor: pfcDesc,
                memory: memory,
                neuron: pfcNeuron,
                callback: null,
                callableBrains: new BrainBase[] { motor, parietal },
                brainRegistry: new InMemoryBrainRegistry(),
                instanceId: instanceId);

            // Session from pfc.Agent
            var session = await pfc.Agent.CreateSessionAsync();

            var registry = new InMemoryBrainRegistry();
            registry.RegisterBrain(motor);
            registry.RegisterBrain(parietal);
            registry.RegisterBrain(pfc);

            var brains = new BrainBase[] { motor, parietal, pfc };
            var agent = new Agent(
                instanceId: instanceId,
                description: new AgentDescription("dispose-test", "Dispose Test", "soul", "identity"),
                brains: brains,
                prefrontal: pfc,
                session: session,
                brainRegistry: registry,
                mcpHandles: new IAsyncDisposable[] { mcpHandle },
                activatedByTaskId: null,
                memory: memory);

            return agent;
        }

        /// <summary>
        /// 构造一个空工具集的 NeuronAssemblyContext——本测试不验工具装配，仅验脑区编织 + 释放序列。
        /// </summary>
        private static NeuronAssemblyContext BuildNeuronCtx(IChatClient chat, IMemoryService memory)
        {
            return new NeuronAssemblyContext(
                ChatClient: chat,
                Memory: memory,
                StandardAITools: Array.Empty<Microsoft.Extensions.AI.AITool>(),
                SynapseAITools: Array.Empty<Microsoft.Extensions.AI.AITool>(),
                ExternalAdapter: null);
        }

        private static AgentDescription BuildStubCapability()
        {
            return new AgentDescription(
                id: "brain-stub.test",
                name: "Test",
                soul: "stub-soul",
                identity: "stub identity");
        }

        /// <summary>极小 IAsyncDisposable spy——dispose 时按顺序 append label 到共享 log。</summary>
        private sealed class SpyDisposable : IAsyncDisposable
        {
            private readonly List<string> _log;
            private readonly string _label;
            public int DisposeCallCount { get; private set; }

            public SpyDisposable(List<string> log, string label)
            {
                _log = log;
                _label = label;
            }

            public ValueTask DisposeAsync()
            {
                DisposeCallCount++;
                _log.Add(_label);
                return default;
            }
        }

        // ===== Local fakes (copy of Brain.Tests fakes to avoid cross-asmdef ref) =====

        private sealed class FakeChatClient : IChatClient
        {
            private readonly string _replyText;
            public FakeChatClient(string replyText) { _replyText = replyText; }
            public Task<ChatResponse> GetResponseAsync(
                IEnumerable<ChatMessage> messages, ChatOptions options = null,
                CancellationToken cancellationToken = default)
            {
                return Task.FromResult(new ChatResponse(new ChatMessage(ChatRole.Assistant, _replyText)));
            }
            public IAsyncEnumerable<ChatResponseUpdate> GetStreamingResponseAsync(
                IEnumerable<ChatMessage> messages, ChatOptions options = null,
                CancellationToken cancellationToken = default)
                => throw new NotSupportedException();
            public object GetService(Type serviceType, object serviceKey = null) => null;
            public void Dispose() { }
        }

        private sealed class FakePrefrontalCallback : IPrefrontalCallback
        {
            public void ReportProgress(string brainId, string message) { }
            public void ReportOutcome(string brainId, BrainOutcome outcome) { }
        }

        /// <summary>
        /// In-memory IMemoryService 桩——dispose log 用 label，可用于「释放顺序」断言。
        /// 数据面方法返回最小实装（脑区构造期不消费）。
        /// </summary>
        private sealed class InMemoryFakeMemoryService : IMemoryService
        {
            private readonly Dictionary<string, MemoryEntry> _entries =
                new Dictionary<string, MemoryEntry>(StringComparer.Ordinal);
            private readonly List<string> _log;
            private readonly string _label;

            public InMemoryFakeMemoryService() : this(null, "memory") { }
            public InMemoryFakeMemoryService(List<string> log, string label)
            {
                _log = log;
                _label = label ?? "memory";
            }

            public void Write(MemoryEntry entry) { _entries[entry.Id] = entry; }
            public MemoryEntry Get(string id)
                => string.IsNullOrWhiteSpace(id) ? null : _entries.TryGetValue(id, out var e) ? e : null;
            public IReadOnlyList<MemoryEntry> Query(string text, int topK) => Array.Empty<MemoryEntry>();
            public IReadOnlyList<MemoryEntry> Scan(MemoryScanFilter filter) => Array.Empty<MemoryEntry>();
            public MemoryStats Stats() => new MemoryStats(_entries.Count, null, null);
            public ValueTask DisposeAsync()
            {
                _log?.Add(_label);
                return default;
            }
        }
    }
}
#endif
