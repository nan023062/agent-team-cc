#if UNITY_INCLUDE_TESTS
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using NUnit.Framework;
using CBIM.Mcp;
using CBIM.Storage;

namespace CBIM.Mcp.Tests
{
    /// <summary>
    /// FileMcpStore 单元测试。
    ///
    /// 覆盖契约规约：
    ///   - 构造校验（null backend / 空 subdir）
    ///   - 空 store 行为（List / Get / Query）
    ///   - Put 后 Get 拿回同实例
    ///   - 同 Id Put 是 upsert（不抛、覆盖）
    ///   - Delete 不存在的 Id 返回 false
    ///   - Stdio / Http 双子类 JSON round-trip（多态保真：类型 + 字段 + Transport）
    ///   - 启动扫盘 rehydrate
    ///   - Query 子串匹配（覆盖 Id / Name / Description）+ empty 行为 + topK
    ///
    /// 每个测试用独立临时根目录，避免相互污染。
    /// </summary>
    [TestFixture]
    public sealed class FileMcpStoreTests
    {
        private string _root;
        private FileBackend _backend;

        [SetUp]
        public void SetUp()
        {
            _root = Path.Combine(Path.GetTempPath(),
                "cbim-mcps-tests-" + Guid.NewGuid().ToString("N"));
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

        // ===== 构造 =====

        [Test]
        public void Constructor_WithNullBackend_Throws()
        {
            Assert.Throws<ArgumentNullException>(() => new FileMcpStore(null));
        }

        [Test]
        public void Constructor_WithWhitespaceSubdir_Throws()
        {
            Assert.Throws<ArgumentException>(() => new FileMcpStore(_backend, "   "));
        }

        // ===== 空 store =====

        [Test]
        public void List_OnEmptyStore_ReturnsZero()
        {
            var store = new FileMcpStore(_backend);

            Assert.That(store.List(), Is.Empty,
                "空 store 必须返回 0 条，不能抛或返 null");
        }

        [Test]
        public void Get_OnEmptyStore_ReturnsNull()
        {
            var store = new FileMcpStore(_backend);

            Assert.That(store.Get("missing"), Is.Null);
        }

        // ===== Put / Get 基本路径 =====

        [Test]
        public void Put_Stdio_ThenGet_ReturnsSameDescriptor()
        {
            var store = new FileMcpStore(_backend);
            var descriptor = new StdioMcpDescriptor(
                "unity-mcp", "Unity MCP", "Unity 桥", "python");

            store.Put(descriptor);
            var fetched = store.Get("unity-mcp");

            Assert.That(fetched, Is.SameAs(descriptor),
                "内存索引应返回原实例引用——不应过一次磁盘往返");
        }

        [Test]
        public void Put_Http_ThenGet_ReturnsSameDescriptor()
        {
            var store = new FileMcpStore(_backend);
            var descriptor = new HttpMcpDescriptor(
                "cdn-prod-mcp", "CDN Prod", "生产 CDN 接入点", "https://cdn.example.com/mcp");

            store.Put(descriptor);
            var fetched = store.Get("cdn-prod-mcp");

            Assert.That(fetched, Is.SameAs(descriptor));
        }

        [Test]
        public void Put_PersistsToDisk_UnderMcpsSubdir()
        {
            var store = new FileMcpStore(_backend);
            store.Put(new StdioMcpDescriptor("unity-mcp", "Unity MCP", "桥", "python"));

            string expected = Path.Combine(_root, "mcps", "unity-mcp.json");
            Assert.That(File.Exists(expected), Is.True,
                "落盘路径必须是 <root>/mcps/<id>.json");
        }

        [Test]
        public void List_AfterMultiplePuts_ReturnsAll()
        {
            var store = new FileMcpStore(_backend);
            store.Put(new StdioMcpDescriptor("a", "A", "alpha", "python"));
            store.Put(new HttpMcpDescriptor("b", "B", "beta", "https://b.example.com/mcp"));
            store.Put(new StdioMcpDescriptor("c", "C", "gamma", "node"));

            var all = store.List();

            Assert.That(all.Count, Is.EqualTo(3));
            Assert.That(all.Select(d => d.Id), Is.EquivalentTo(new[] { "a", "b", "c" }));
        }

        // ===== Upsert =====

        [Test]
        public void Put_SameId_IsUpsert()
        {
            var store = new FileMcpStore(_backend);
            store.Put(new StdioMcpDescriptor("unity-mcp", "旧名", "旧描述", "python"));
            store.Put(new StdioMcpDescriptor("unity-mcp", "新名", "新描述", "python3"));

            var fetched = store.Get("unity-mcp");
            var all = store.List();

            Assert.That(fetched, Is.InstanceOf<StdioMcpDescriptor>());
            Assert.That(fetched.Name, Is.EqualTo("新名"));
            Assert.That(fetched.Description, Is.EqualTo("新描述"));
            Assert.That(((StdioMcpDescriptor)fetched).Command, Is.EqualTo("python3"));
            Assert.That(all.Count, Is.EqualTo(1), "upsert 不应造成重复条目");
        }

        [Test]
        public void Put_SameId_TransportSwitch_OverwritesTypeAndFile()
        {
            // 同 Id 但形态切换（Stdio → Http）——upsert 必须替换整条记录，
            // 不能残留旧 stdio 字段，更不能保留旧类型。
            var store = new FileMcpStore(_backend);
            store.Put(new StdioMcpDescriptor("svc", "Svc", "原 stdio", "python"));
            store.Put(new HttpMcpDescriptor("svc", "Svc", "改为 http", "https://svc.example.com/mcp"));

            var fetched = store.Get("svc");

            Assert.That(fetched, Is.InstanceOf<HttpMcpDescriptor>(),
                "upsert 后类型必须切到 Http");
            Assert.That(fetched.Transport, Is.EqualTo(McpTransportKind.Http));

            // 也要从磁盘 rehydrate 验证一致
            var reloaded = new FileMcpStore(_backend).Get("svc");
            Assert.That(reloaded, Is.InstanceOf<HttpMcpDescriptor>(),
                "落盘文件必须是新形态——不能残留旧 stdio JSON");
        }

        [Test]
        public void Put_NullDescriptor_Throws()
        {
            var store = new FileMcpStore(_backend);

            Assert.Throws<ArgumentNullException>(() => store.Put(null));
        }

        // ===== Delete =====

        [Test]
        public void Delete_ExistingId_ReturnsTrue_AndRemovesFromIndexAndDisk()
        {
            var store = new FileMcpStore(_backend);
            store.Put(new StdioMcpDescriptor("tmp", "Tmp", "临时", "python"));

            bool deleted = store.Delete("tmp");

            Assert.That(deleted, Is.True);
            Assert.That(store.Get("tmp"), Is.Null);
            Assert.That(store.List(), Is.Empty);

            string path = Path.Combine(_root, "mcps", "tmp.json");
            Assert.That(File.Exists(path), Is.False, "落盘文件应同步删除");
        }

        [Test]
        public void Delete_MissingId_ReturnsFalse()
        {
            var store = new FileMcpStore(_backend);

            Assert.That(store.Delete("never-existed"), Is.False);
        }

        [Test]
        public void Delete_NullOrWhitespaceId_ReturnsFalse()
        {
            var store = new FileMcpStore(_backend);

            Assert.That(store.Delete(null), Is.False);
            Assert.That(store.Delete(""), Is.False);
            Assert.That(store.Delete("   "), Is.False);
        }

        // ===== 多态 JSON round-trip =====

        [Test]
        public void Roundtrip_Stdio_PreservesAllFields()
        {
            var args = new[] { "-m", "unity_mcp", "--port", "0" };
            var env = new Dictionary<string, string>
            {
                ["UNITY_PROJECT"] = "/tmp/proj",
                ["LOG_LEVEL"] = "debug",
            };
            var original = new StdioMcpDescriptor(
                "unity-mcp", "Unity MCP", "Unity 桥", "python", args, env);

            var writer = new FileMcpStore(_backend);
            writer.Put(original);

            // 用新 store 实例强制走磁盘 rehydrate 路径
            var reader = new FileMcpStore(_backend);
            var loaded = reader.Get("unity-mcp");

            Assert.That(loaded, Is.Not.Null);
            Assert.That(loaded, Is.InstanceOf<StdioMcpDescriptor>(),
                "rehydrate 后必须仍是 StdioMcpDescriptor 子类——多态保真");

            var stdio = (StdioMcpDescriptor)loaded;
            Assert.That(stdio.Id, Is.EqualTo("unity-mcp"));
            Assert.That(stdio.Name, Is.EqualTo("Unity MCP"));
            Assert.That(stdio.Description, Is.EqualTo("Unity 桥"));
            Assert.That(stdio.Transport, Is.EqualTo(McpTransportKind.Stdio));
            Assert.That(stdio.Command, Is.EqualTo("python"));
            Assert.That(stdio.Args, Is.EqualTo(args));
            Assert.That(stdio.Env, Is.EqualTo(env));
        }

        [Test]
        public void Roundtrip_Http_PreservesAllFields()
        {
            var headers = new Dictionary<string, string>
            {
                ["X-Tenant"] = "acme",
                ["X-Region"] = "ap-east-1",
            };
            var original = new HttpMcpDescriptor(
                "cdn-prod-mcp", "CDN Prod", "生产 CDN 接入点",
                "https://cdn.example.com/mcp",
                authToken: "secret-token",
                headers: headers);

            var writer = new FileMcpStore(_backend);
            writer.Put(original);

            var reader = new FileMcpStore(_backend);
            var loaded = reader.Get("cdn-prod-mcp");

            Assert.That(loaded, Is.Not.Null);
            Assert.That(loaded, Is.InstanceOf<HttpMcpDescriptor>(),
                "rehydrate 后必须仍是 HttpMcpDescriptor 子类——多态保真");

            var http = (HttpMcpDescriptor)loaded;
            Assert.That(http.Id, Is.EqualTo("cdn-prod-mcp"));
            Assert.That(http.Name, Is.EqualTo("CDN Prod"));
            Assert.That(http.Description, Is.EqualTo("生产 CDN 接入点"));
            Assert.That(http.Transport, Is.EqualTo(McpTransportKind.Http));
            Assert.That(http.Endpoint, Is.EqualTo("https://cdn.example.com/mcp"));
            Assert.That(http.AuthToken, Is.EqualTo("secret-token"));
            Assert.That(http.Headers, Is.EqualTo(headers));
        }

        [Test]
        public void Roundtrip_Stdio_WithDefaults_RehydratesEmptyArgsAndEnv()
        {
            var original = new StdioMcpDescriptor("git-mcp", "Git MCP", "git 桥", "git-mcp");

            new FileMcpStore(_backend).Put(original);

            var loaded = (StdioMcpDescriptor)new FileMcpStore(_backend).Get("git-mcp");

            Assert.That(loaded.Args, Is.Not.Null.And.Empty,
                "缺省 Args 必须 rehydrate 为空集合，不是 null");
            Assert.That(loaded.Env, Is.Not.Null.And.Empty,
                "缺省 Env 必须 rehydrate 为空字典，不是 null");
        }

        [Test]
        public void Roundtrip_Http_WithDefaults_RehydratesEmptyAuthAndHeaders()
        {
            var original = new HttpMcpDescriptor(
                "anon-mcp", "Anon", "无鉴权接入点", "https://anon.example.com/mcp");

            new FileMcpStore(_backend).Put(original);

            var loaded = (HttpMcpDescriptor)new FileMcpStore(_backend).Get("anon-mcp");

            Assert.That(loaded.AuthToken, Is.EqualTo(string.Empty),
                "缺省 AuthToken 必须 rehydrate 为空字符串，不是 null");
            Assert.That(loaded.Headers, Is.Not.Null.And.Empty,
                "缺省 Headers 必须 rehydrate 为空字典，不是 null");
        }

        [Test]
        public void DiskJson_ContainsTransportDiscriminator()
        {
            // 鉴别字段是契约的一部分——未来云端 / 跨语言读取依赖它。
            var store = new FileMcpStore(_backend);
            store.Put(new StdioMcpDescriptor("a", "A", "alpha", "python"));
            store.Put(new HttpMcpDescriptor("b", "B", "beta", "https://b.example.com/mcp"));

            string stdioJson = File.ReadAllText(Path.Combine(_root, "mcps", "a.json"));
            string httpJson = File.ReadAllText(Path.Combine(_root, "mcps", "b.json"));

            Assert.That(stdioJson, Does.Contain("\"transport\"")
                .And.Contain("\"Stdio\""));
            Assert.That(httpJson, Does.Contain("\"transport\"")
                .And.Contain("\"Http\""));
        }

        // ===== 启动扫盘 =====

        [Test]
        public void Constructor_RehydratesMixedTransportsFromDisk()
        {
            var first = new FileMcpStore(_backend);
            first.Put(new StdioMcpDescriptor("a", "A", "alpha", "python"));
            first.Put(new HttpMcpDescriptor("b", "B", "beta", "https://b.example.com/mcp"));

            var second = new FileMcpStore(_backend);

            Assert.That(second.List().Count, Is.EqualTo(2));
            Assert.That(second.Get("a"), Is.InstanceOf<StdioMcpDescriptor>());
            Assert.That(second.Get("b"), Is.InstanceOf<HttpMcpDescriptor>());
        }

        [Test]
        public void Constructor_WithCorruptFile_SkipsAndContinues()
        {
            var first = new FileMcpStore(_backend);
            first.Put(new StdioMcpDescriptor("good", "Good", "ok", "python"));

            // 直接写一个损坏文件——不应阻塞 store 启动
            File.WriteAllText(Path.Combine(_root, "mcps", "bad.json"), "{ not json");

            var second = new FileMcpStore(_backend);

            Assert.That(second.Get("good"), Is.Not.Null,
                "损坏文件应静默跳过，不阻塞其他条目的加载");
        }

        [Test]
        public void Constructor_WithUnknownTransport_SkipsEntry()
        {
            // 模拟未来子类被旧版本读到——未知 transport 不应抛、应跳过。
            var first = new FileMcpStore(_backend);
            first.Put(new StdioMcpDescriptor("good", "Good", "ok", "python"));

            string unknownJson =
                "{ \"transport\": \"Websocket\", \"id\": \"future\", " +
                "\"name\": \"Future\", \"description\": \"unknown\" }";
            File.WriteAllText(Path.Combine(_root, "mcps", "future.json"), unknownJson);

            var second = new FileMcpStore(_backend);

            Assert.That(second.Get("good"), Is.Not.Null);
            Assert.That(second.Get("future"), Is.Null,
                "未知 transport 必须跳过，不能反序列化为意外子类");
        }

        [Test]
        public void Constructor_WithCustomSubdir_IsolatesFromDefault()
        {
            var defaultStore = new FileMcpStore(_backend);
            defaultStore.Put(new StdioMcpDescriptor("d", "Default", "默认 subdir", "python"));

            var altStore = new FileMcpStore(_backend, subdir: "external-mcps");

            Assert.That(altStore.List(), Is.Empty,
                "自定义 subdir 应与默认 'mcps' 隔离");

            altStore.Put(new HttpMcpDescriptor(
                "w", "Workflow", "另一子目录", "https://w.example.com/mcp"));

            string expected = Path.Combine(_root, "external-mcps", "w.json");
            Assert.That(File.Exists(expected), Is.True);
        }

        // ===== Query 子串匹配 =====

        [Test]
        public void Query_MatchesSubstring_InId()
        {
            var store = new FileMcpStore(_backend);
            store.Put(new StdioMcpDescriptor("git-mcp", "Git MCP", "git 桥", "git-mcp"));
            store.Put(new StdioMcpDescriptor("git-helper-mcp", "Git Helper", "git 辅助", "node"));
            store.Put(new HttpMcpDescriptor("cdn-mcp", "CDN", "CDN 接入", "https://cdn.example.com/mcp"));

            var hits = store.Query("git", topK: 10);

            Assert.That(hits.Count, Is.EqualTo(2));
            Assert.That(hits.Select(d => d.Id),
                Is.EquivalentTo(new[] { "git-mcp", "git-helper-mcp" }));
        }

        [Test]
        public void Query_MatchesSubstring_InDescription()
        {
            var store = new FileMcpStore(_backend);
            store.Put(new StdioMcpDescriptor("a", "A", "需要拉起 git 子进程", "git"));
            store.Put(new HttpMcpDescriptor("b", "B", "远端 erp 接入", "https://erp.example.com/mcp"));

            var hits = store.Query("erp", topK: 10);

            Assert.That(hits.Count, Is.EqualTo(1));
            Assert.That(hits[0].Id, Is.EqualTo("b"));
        }

        [Test]
        public void Query_IsCaseInsensitive()
        {
            var store = new FileMcpStore(_backend);
            store.Put(new StdioMcpDescriptor("unity-mcp", "Unity MCP", "Unity 桥", "python"));

            var hits = store.Query("UNITY", topK: 10);

            Assert.That(hits.Count, Is.EqualTo(1));
            Assert.That(hits[0].Id, Is.EqualTo("unity-mcp"));
        }

        [Test]
        public void Query_RespectsTopK()
        {
            var store = new FileMcpStore(_backend);
            for (int i = 0; i < 5; i++)
            {
                store.Put(new StdioMcpDescriptor($"mcp-{i}", $"MCP {i}", "通用描述", "python"));
            }

            var hits = store.Query("通用", topK: 3);

            Assert.That(hits.Count, Is.EqualTo(3));
        }

        [Test]
        public void Query_EmptyText_ReturnsEmpty()
        {
            var store = new FileMcpStore(_backend);
            store.Put(new StdioMcpDescriptor("a", "A", "alpha", "python"));

            Assert.That(store.Query("", topK: 10), Is.Empty);
            Assert.That(store.Query("   ", topK: 10), Is.Empty);
            Assert.That(store.Query(null, topK: 10), Is.Empty);
        }

        [Test]
        public void Query_NonPositiveTopK_ReturnsEmpty()
        {
            var store = new FileMcpStore(_backend);
            store.Put(new StdioMcpDescriptor("a", "A", "alpha", "python"));

            Assert.That(store.Query("alpha", topK: 0), Is.Empty);
            Assert.That(store.Query("alpha", topK: -1), Is.Empty);
        }

        [Test]
        public void Query_OnEmptyStore_ReturnsEmpty()
        {
            var store = new FileMcpStore(_backend);

            Assert.That(store.Query("anything", topK: 10), Is.Empty,
                "空 store 上的 Query 必须空集合，不抛、不 null");
        }
    }
}
#endif
