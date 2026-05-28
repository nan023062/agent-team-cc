#if UNITY_INCLUDE_TESTS
using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using NUnit.Framework;
using CBIM.Mcp;

namespace CBIM.Mcp.Tests
{
    /// <summary>
    /// DefaultMcpInstanceManager 单元测试。
    ///
    /// 覆盖契约规约：
    ///   - 构造校验（null starter）
    ///   - 单 Request / 单 Dispose 基本路径
    ///   - 同 Id 双 Request → starter 只调 1 次，ActiveCount=1，RefCount=2
    ///   - 同 Id 双 Dispose 后 client.Dispose 调 1 次，字典清空
    ///   - 不同 Id 各启各的（互不干扰）
    ///   - 并发 Request 同 Id：N 线程同时触发，starter 仍只调 1 次
    ///   - handle.Dispose 幂等（重复调不二次 release）
    ///   - Request 时 starter 抛异常：字典不留垃圾，下次同 Id 可重试
    ///   - RefCount(unknown) = 0；ActiveCount 初始 0
    ///   - handle.AiFunctions 同 Id 兄弟共享同一引用
    ///   - Token 分配：首次同 Id 三连 InstanceId 单调递增、Gen=0；跨 Id 不撞 Token
    ///   - Slot 复用 + ABA 防护：旧 token 在 slot 重分配后失效，再次 Dispose 不影响新条目
    ///
    /// 用注入的 fake starter 替代 Microsoft.Agents.AI.Mcp，本测试不依赖任何外部进程 / 网络。
    /// </summary>
    [TestFixture]
    public sealed class DefaultMcpInstanceManagerTests
    {
        // ===== 构造 =====

        [Test]
        public void Constructor_WithNullStarter_Throws()
        {
            Assert.Throws<ArgumentNullException>(() => new McpManager(null));
        }

        [Test]
        public void EmptyManager_ActiveCount_IsZero_And_RefCount_IsZero()
        {
            var starter = new FakeStarter();
            var mgr = new McpManager(starter);

            Assert.That(mgr.ActiveCount, Is.EqualTo(0));
            Assert.That(mgr.RefCount("anything"), Is.EqualTo(0));
            Assert.That(mgr.RefCount(null), Is.EqualTo(0));
            Assert.That(mgr.RefCount(""), Is.EqualTo(0));
        }

        // ===== 单 Request / Dispose 基本路径 =====

        [Test]
        public void Request_Once_StartsClient_AndReturnsHandle()
        {
            var starter = new FakeStarter();
            var mgr = new McpManager(starter);
            var desc = NewStdio("a");

            var handle = mgr.Request(desc);

            Assert.That(handle, Is.Not.Null);
            Assert.That(handle.McpId, Is.EqualTo("a"));
            Assert.That(handle.Descriptor, Is.SameAs(desc));
            Assert.That(handle.AiFunctions, Is.Not.Null);
            Assert.That(starter.StartCallCount, Is.EqualTo(1));
            Assert.That(mgr.ActiveCount, Is.EqualTo(1));
            Assert.That(mgr.RefCount("a"), Is.EqualTo(1));
        }

        [Test]
        public void RequestThenDispose_DisposesClient_AndClearsEntry()
        {
            var starter = new FakeStarter();
            var mgr = new McpManager(starter);
            var handle = mgr.Request(NewStdio("a"));
            var client = starter.LastStartedClient;

            handle.Dispose();

            Assert.That(client.DisposeCallCount, Is.EqualTo(1));
            Assert.That(mgr.ActiveCount, Is.EqualTo(0));
            Assert.That(mgr.RefCount("a"), Is.EqualTo(0));
        }

        // ===== 同 Id 多次 Request 合并 =====

        [Test]
        public void Request_SameId_Twice_StartsClientOnce_RefCountIsTwo()
        {
            var starter = new FakeStarter();
            var mgr = new McpManager(starter);
            var desc = NewStdio("a");

            var h1 = mgr.Request(desc);
            var h2 = mgr.Request(desc);

            Assert.That(starter.StartCallCount, Is.EqualTo(1),
                "同 Id 第二次 Request 必须复用，不能再调 starter");
            Assert.That(mgr.ActiveCount, Is.EqualTo(1));
            Assert.That(mgr.RefCount("a"), Is.EqualTo(2));
            Assert.That(h1, Is.Not.SameAs(h2), "应返回独立的 handle 实例");
            Assert.That(h1.AiFunctions, Is.SameAs(h2.AiFunctions),
                "同 Id 兄弟 handle 必须共享同一 AiFunctions 引用");
        }

        [Test]
        public void Request_SameId_Twice_BothDisposed_DisposesClientOnce()
        {
            var starter = new FakeStarter();
            var mgr = new McpManager(starter);
            var desc = NewStdio("a");

            var h1 = mgr.Request(desc);
            var h2 = mgr.Request(desc);
            var client = starter.LastStartedClient;

            h1.Dispose();
            Assert.That(client.DisposeCallCount, Is.EqualTo(0),
                "RefCount 还剩 1，不能 Dispose client");
            Assert.That(mgr.RefCount("a"), Is.EqualTo(1));
            Assert.That(mgr.ActiveCount, Is.EqualTo(1));

            h2.Dispose();
            Assert.That(client.DisposeCallCount, Is.EqualTo(1),
                "RefCount 归零，client 必须正好 Dispose 一次");
            Assert.That(mgr.RefCount("a"), Is.EqualTo(0));
            Assert.That(mgr.ActiveCount, Is.EqualTo(0));
        }

        // ===== 不同 Id 互不干扰 =====

        [Test]
        public void Request_DifferentIds_StartsEachIndependently()
        {
            var starter = new FakeStarter();
            var mgr = new McpManager(starter);

            var ha = mgr.Request(NewStdio("a"));
            var hb = mgr.Request(NewStdio("b"));

            Assert.That(starter.StartCallCount, Is.EqualTo(2),
                "不同 Id 必须各启各的");
            Assert.That(mgr.ActiveCount, Is.EqualTo(2));
            Assert.That(mgr.RefCount("a"), Is.EqualTo(1));
            Assert.That(mgr.RefCount("b"), Is.EqualTo(1));
            Assert.That(ha.AiFunctions, Is.Not.SameAs(hb.AiFunctions),
                "不同 Id 的 AiFunctions 必须是不同列表");

            ha.Dispose();
            Assert.That(mgr.RefCount("a"), Is.EqualTo(0));
            Assert.That(mgr.RefCount("b"), Is.EqualTo(1),
                "释放 a 不能影响 b 的引用计数");
            Assert.That(mgr.ActiveCount, Is.EqualTo(1));

            hb.Dispose();
            Assert.That(mgr.ActiveCount, Is.EqualTo(0));
        }

        // ===== handle.Dispose 幂等 =====

        [Test]
        public void Handle_Dispose_IsIdempotent()
        {
            var starter = new FakeStarter();
            var mgr = new McpManager(starter);
            var h = mgr.Request(NewStdio("a"));
            var client = starter.LastStartedClient;

            h.Dispose();
            h.Dispose(); // 第二次必须 no-op
            h.Dispose(); // 第三次也是

            Assert.That(client.DisposeCallCount, Is.EqualTo(1),
                "重复 Dispose 同一 handle 不应造成多次 release / 多次 client.Dispose");
            Assert.That(mgr.ActiveCount, Is.EqualTo(0));
        }

        [Test]
        public void Handle_Dispose_Idempotent_DoesNotCorruptSiblingRefCount()
        {
            // 同 Id 两次 Request → h1 重复 Dispose 不应错误地把 h2 的引用也减掉。
            var starter = new FakeStarter();
            var mgr = new McpManager(starter);
            var desc = NewStdio("a");
            var h1 = mgr.Request(desc);
            var h2 = mgr.Request(desc);
            var client = starter.LastStartedClient;

            h1.Dispose();
            h1.Dispose(); // 幂等
            h1.Dispose(); // 仍然幂等

            Assert.That(mgr.RefCount("a"), Is.EqualTo(1),
                "h1 多次 Dispose 不能蚕食 h2 的引用计数");
            Assert.That(client.DisposeCallCount, Is.EqualTo(0));

            h2.Dispose();
            Assert.That(client.DisposeCallCount, Is.EqualTo(1));
        }

        // ===== 启动失败不留垃圾 =====

        [Test]
        public void Request_StarterThrows_BubblesException_AndLeavesNoEntry()
        {
            var starter = new ThrowingStarter(new InvalidOperationException("boom"));
            var mgr = new McpManager(starter);
            var desc = NewStdio("a");

            var ex = Assert.Throws<InvalidOperationException>(() => mgr.Request(desc));
            Assert.That(ex.Message, Is.EqualTo("boom"),
                "starter 的异常必须原样上抛，不被吞 / 不被包装");
            Assert.That(mgr.ActiveCount, Is.EqualTo(0),
                "启动失败不能在字典留垃圾");
            Assert.That(mgr.RefCount("a"), Is.EqualTo(0));
        }

        [Test]
        public void Request_StarterThrowsThenRecovers_NextRequestRetries()
        {
            // 模拟一次失败后修复——第二次 Request 应当能重启，不能因为前一次失败被「拉黑」。
            var starter = new FlakyStarter(throwsFirst: 1);
            var mgr = new McpManager(starter);
            var desc = NewStdio("a");

            Assert.Throws<InvalidOperationException>(() => mgr.Request(desc));

            var handle = mgr.Request(desc);

            Assert.That(handle, Is.Not.Null);
            Assert.That(starter.StartCallCount, Is.EqualTo(2),
                "失败后下次 Request 应该再调一次 starter——字典里没残留");
            Assert.That(mgr.ActiveCount, Is.EqualTo(1));
            Assert.That(mgr.RefCount("a"), Is.EqualTo(1));
        }

        [Test]
        public void Request_StarterReturnsNull_Throws_AndLeavesNoEntry()
        {
            var starter = new NullReturningStarter();
            var mgr = new McpManager(starter);

            Assert.Throws<InvalidOperationException>(() => mgr.Request(NewStdio("a")));
            Assert.That(mgr.ActiveCount, Is.EqualTo(0),
                "starter 违约返回 null 同样不能在字典留垃圾");
        }

        [Test]
        public void Request_NullDescriptor_Throws()
        {
            var mgr = new McpManager(new FakeStarter());

            Assert.Throws<ArgumentNullException>(() => mgr.Request(null));
        }

        // ===== 多线程并发 Request 同 Id =====

        [Test]
        public void Request_ConcurrentSameId_StartsClientOnlyOnce()
        {
            // N 线程并行抢同一个 Id：starter 必须只调 1 次，
            // 所有 handle 都拿到同一个底层 client 的 AiFunctions。
            const int threadCount = 16;
            using (var gate = new ManualResetEventSlim(initialState: false))
            {
                var starter = new FakeStarter();
                var mgr = new McpManager(starter);
                var desc = NewStdio("hot");
                var handles = new McpInstanceHandle[threadCount];
                var errors = new Exception[threadCount];

                var threads = new Thread[threadCount];
                for (int i = 0; i < threadCount; i++)
                {
                    int idx = i;
                    threads[i] = new Thread(() =>
                    {
                        try
                        {
                            gate.Wait();
                            handles[idx] = mgr.Request(desc);
                        }
                        catch (Exception ex)
                        {
                            errors[idx] = ex;
                        }
                    });
                    threads[i].Start();
                }

                // 全部就位后一齐放行——制造真实竞况。
                gate.Set();
                foreach (var t in threads) t.Join();

                Assert.That(errors, Is.All.Null, "并发 Request 不应抛");
                Assert.That(starter.StartCallCount, Is.EqualTo(1),
                    $"同 Id {threadCount} 线程并发 Request 必须合并为单次 starter.Start");
                Assert.That(mgr.ActiveCount, Is.EqualTo(1));
                Assert.That(mgr.RefCount("hot"), Is.EqualTo(threadCount));

                // 所有 handle 共享同一个 AiFunctions 引用。
                var shared = handles[0].AiFunctions;
                foreach (var h in handles)
                    Assert.That(h.AiFunctions, Is.SameAs(shared));

                // 全部 Dispose 后字典清空，client.Dispose 调一次。
                var client = starter.LastStartedClient;
                foreach (var h in handles) h.Dispose();

                Assert.That(mgr.ActiveCount, Is.EqualTo(0));
                Assert.That(client.DisposeCallCount, Is.EqualTo(1));
            }
        }

        [Test]
        public void Request_ConcurrentDispose_DoesNotUnderflowRefCount()
        {
            // 并发场景：N 线程各抢一个 handle 再各自 Dispose——结果必须正好归零，
            // 不能出现负引用计数 / 重复 client.Dispose。
            const int threadCount = 32;
            var starter = new FakeStarter();
            var mgr = new McpManager(starter);
            var desc = NewStdio("churn");

            var tasks = new Task[threadCount];
            for (int i = 0; i < threadCount; i++)
            {
                tasks[i] = Task.Run(() =>
                {
                    var h = mgr.Request(desc);
                    h.Dispose();
                });
            }
            Task.WaitAll(tasks);

            Assert.That(mgr.ActiveCount, Is.EqualTo(0));
            Assert.That(mgr.RefCount("churn"), Is.EqualTo(0));
            // 启动可能发生 1 次或 N 次（取决于调度交错），但最终引用必为 0、
            // 且每个被启动的 client 必须恰好 Dispose 一次。
            foreach (var c in starter.AllStartedClients)
                Assert.That(c.DisposeCallCount, Is.EqualTo(1),
                    "每个被启动的 client 必须正好 Dispose 一次");
        }

        // ===== Token 分配 & ActiveRefs 快照 & default(handle) 安全 =====

        [Test]
        public void Request_FirstAllocs_HaveIncreasingInstanceIds_AndZeroGen()
        {
            // 全新 manager 三次同 Id Request——slot 单调 0/1/2，gen 全 0，三个 token 互不相等。
            var mgr = new McpManager(new FakeStarter());
            var desc = NewStdio("a");

            var h1 = mgr.Request(desc);
            var h2 = mgr.Request(desc);
            var h3 = mgr.Request(desc);

            Assert.That(h1.Token.InstanceId, Is.EqualTo(0));
            Assert.That(h1.Token.Gen, Is.EqualTo(0));
            Assert.That(h2.Token.InstanceId, Is.EqualTo(1));
            Assert.That(h2.Token.Gen, Is.EqualTo(0));
            Assert.That(h3.Token.InstanceId, Is.EqualTo(2));
            Assert.That(h3.Token.Gen, Is.EqualTo(0));

            Assert.That(h1.Token, Is.Not.EqualTo(h2.Token));
            Assert.That(h2.Token, Is.Not.EqualTo(h3.Token));
            Assert.That(h1.Token, Is.Not.EqualTo(h3.Token));
        }

        [Test]
        public void Request_TokensUniqueAcrossDifferentIds()
        {
            // Token 分配跨 Id 单调，不按 Id 分桶——不同 Id 之间也必须互不撞 token。
            var mgr = new McpManager(new FakeStarter());

            var ha1 = mgr.Request(NewStdio("a"));
            var hb = mgr.Request(NewStdio("b"));
            var ha2 = mgr.Request(NewStdio("a"));

            var tokens = new[] { ha1.Token, hb.Token, ha2.Token };
            Assert.That(tokens, Is.Unique,
                "Token 分配必须跨 Id 单调，不能按 Id 分桶导致 token 冲突");
        }

        [Test]
        public void ActiveRefs_AfterRequest_ContainsAllHeldTokens()
        {
            var mgr = new McpManager(new FakeStarter());
            var desc = NewStdio("a");

            var h1 = mgr.Request(desc);
            var h2 = mgr.Request(desc);
            var h3 = mgr.Request(desc);

            var active = mgr.ActiveRefs("a");

            CollectionAssert.AreEquivalent(
                new[] { h1.Token, h2.Token, h3.Token },
                active);
        }

        [Test]
        public void ActiveRefs_ReturnsSnapshot_NotInternalSet()
        {
            // 拿到快照后再 Request 一次：第一次的快照不应被后续 mutation 影响。
            var mgr = new McpManager(new FakeStarter());
            var desc = NewStdio("a");

            var h1 = mgr.Request(desc);
            var snapshot = mgr.ActiveRefs("a");
            var h2 = mgr.Request(desc);

            Assert.That(snapshot, Does.Not.Contain(h2.Token),
                "ActiveRefs 必须返回快照拷贝，不能是 live 视图");
            Assert.That(snapshot.Count, Is.EqualTo(1));
            Assert.That(snapshot, Does.Contain(h1.Token));
        }

        [Test]
        public void ActiveRefs_UnknownOrUnstartedId_ReturnsEmpty()
        {
            var mgr = new McpManager(new FakeStarter());

            Assert.That(mgr.ActiveRefs("never-requested"), Is.Empty,
                "未知 Id 必须返空集合而非抛异常");

            var desc = NewStdio("a");
            var h = mgr.Request(desc);
            h.Dispose();

            Assert.That(mgr.ActiveRefs("a"), Is.Empty,
                "全部 Dispose 后 entry 已移出字典——ActiveRefs 必须返空");
        }

        [Test]
        public void Default_Handle_Dispose_IsSafeNoOp()
        {
            // default(McpInstanceHandle) 内部 _manager 字段为 null——Dispose 必须 null-check 后 noop。
            var h = default(McpInstanceHandle);

            Assert.That(h.McpId, Is.Null);
            Assert.That(h.Token, Is.EqualTo(default(McpRefToken)));
            Assert.DoesNotThrow(() => h.Dispose());
            Assert.DoesNotThrow(() => h.Dispose()); // 多次依然 noop
        }

        // ===== Slot 复用 + ABA 防护 =====

        [Test]
        public void Aba_SameSlotReuse_OldHandleDispose_DoesNotAffectNewEntry()
        {
            // 关键 ABA 场景：
            //   1. h1 占 slot 0 gen 0 → Dispose 后 slot 0 归池。
            //   2. h2 同 Id 再 Request：slot 0 复用、gen +1，新 token 与 h1.Token 不相等。
            //   3. 再次 Dispose h1（陈旧 token）必须被 HashSet.Remove 拒收——不能蚕食 h2。
            var starter = new FakeStarter();
            var mgr = new McpManager(starter);
            var descA = NewStdio("a");

            var h1 = mgr.Request(descA);
            Assert.That(h1.Token.InstanceId, Is.EqualTo(0));
            Assert.That(h1.Token.Gen, Is.EqualTo(0));

            h1.Dispose();
            Assert.That(mgr.ActiveCount, Is.EqualTo(0));

            var h2 = mgr.Request(descA);
            Assert.That(h2.Token.InstanceId, Is.EqualTo(0), "slot 应被复用");
            Assert.That(h2.Token.Gen, Is.EqualTo(1), "复用后 gen 必须 +1");
            Assert.That(h2.Token, Is.Not.EqualTo(h1.Token),
                "新旧 token 必须不相等——ABA 防护的核心");

            // 关键：再次 Dispose h1（旧 token）不应影响 h2 持有的新条目。
            h1.Dispose();
            Assert.That(mgr.RefCount("a"), Is.EqualTo(1),
                "陈旧 token 的 release 必须被拒收，h2 仍持有");
            Assert.That(mgr.ActiveCount, Is.EqualTo(1));

            h2.Dispose();
            Assert.That(mgr.ActiveCount, Is.EqualTo(0));
        }

        [Test]
        public void SlotReuse_FreedSlot_IsReused()
        {
            // slot 归池后，下一次 Request（即便换了 Id）应优先复用归池 slot 而非分配新 slot。
            var starter = new FakeStarter();
            var mgr = new McpManager(starter);
            var descA = NewStdio("a");
            var descB = NewStdio("b");

            var h1 = mgr.Request(descA);
            h1.Dispose(); // slot 0 归池

            var h2 = mgr.Request(descB);
            Assert.That(h2.Token.InstanceId, Is.EqualTo(0),
                "_freeSlots 应优先 Pop，h2 须拿到 slot 0");
            Assert.That(h2.Token.Gen, Is.EqualTo(1),
                "slot 0 复用，gen 必须 +1");
        }

        // ===== Fixture helpers =====

        private static StdioMcpDescriptor NewStdio(string id) =>
            new StdioMcpDescriptor(id, id, $"desc-{id}", "python");

        // ===== Fake starters =====

        /// <summary>
        /// 记录调用次数 + 返回独立 mock client 的 starter。
        /// </summary>
        private sealed class FakeStarter : IMcpClientStarter
        {
            private int _count;
            private readonly List<FakeStartedClient> _clients = new List<FakeStartedClient>();

            public int StartCallCount => Volatile.Read(ref _count);
            public FakeStartedClient LastStartedClient
            {
                get { lock (_clients) return _clients[_clients.Count - 1]; }
            }
            public IReadOnlyList<FakeStartedClient> AllStartedClients
            {
                get { lock (_clients) return _clients.ToArray(); }
            }

            public IStartedMcpClient Start(McpDescriptor descriptor)
            {
                Interlocked.Increment(ref _count);
                var c = new FakeStartedClient(descriptor.Id);
                lock (_clients) _clients.Add(c);
                return c;
            }
        }

        /// <summary>
        /// 永远抛指定异常的 starter——用于「启动失败不留垃圾」测试。
        /// </summary>
        private sealed class ThrowingStarter : IMcpClientStarter
        {
            private readonly Exception _ex;
            public ThrowingStarter(Exception ex) { _ex = ex; }
            public IStartedMcpClient Start(McpDescriptor descriptor) => throw _ex;
        }

        /// <summary>
        /// 前 N 次抛、之后正常返回的 starter——用于「失败后可重试」测试。
        /// </summary>
        private sealed class FlakyStarter : IMcpClientStarter
        {
            private readonly int _failingTimes;
            private int _count;

            public int StartCallCount => _count;

            public FlakyStarter(int throwsFirst) { _failingTimes = throwsFirst; }

            public IStartedMcpClient Start(McpDescriptor descriptor)
            {
                int n = Interlocked.Increment(ref _count);
                if (n <= _failingTimes)
                    throw new InvalidOperationException($"flaky #{n}");
                return new FakeStartedClient(descriptor.Id);
            }
        }

        /// <summary>
        /// 违约返回 null 的 starter——用于验证 Manager 的防御性校验。
        /// </summary>
        private sealed class NullReturningStarter : IMcpClientStarter
        {
            public IStartedMcpClient Start(McpDescriptor descriptor) => null;
        }

        private sealed class FakeStartedClient : IStartedMcpClient
        {
            private int _disposeCount;
            public string Id { get; }
            public IReadOnlyList<object> AiFunctions { get; } = new object[] { new object() };

            public int DisposeCallCount => Volatile.Read(ref _disposeCount);

            public FakeStartedClient(string id) { Id = id; }

            public void Dispose() => Interlocked.Increment(ref _disposeCount);
        }
    }
}
#endif
