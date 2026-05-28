#if UNITY_INCLUDE_TESTS
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json.Nodes;
using System.Threading;
using System.Threading.Tasks;
using NUnit.Framework;
using CBIM.Memory;
using CBIM.Memory.Bridge;
using CBIM.Storage;

namespace CBIM.Memory.Tests
{
    /// <summary>
    /// <see cref="MemoryBridgeMcpServer"/> 单元测试。
    ///
    /// 覆盖：
    ///   - JSON-RPC 协议帧：initialize / tools/list / tools/call / 未知方法 / parse error / notification
    ///   - 5 个工具（write / query / get / scan / stats）行为透传
    ///   - 时间字段 ISO 8601 UTC 序列化 / 解析
    ///   - DisposeAsync 幂等
    ///   - 端到端 stdio loop（用内存 reader/writer 跑一整轮）
    ///
    /// 不做集成测试（真实 subprocess 拉起留给 task-5）；本套件只验证「单进程内 wrap 行为」。
    /// </summary>
    [TestFixture]
    public sealed class MemoryBridgeMcpServerTests
    {
        private string _root;
        private FileBackend _backend;
        private FileMemoryBackend _memory;
        private MemoryBridgeMcpServer _server;

        [SetUp]
        public void SetUp()
        {
            _root = Path.Combine(Path.GetTempPath(),
                "cbim-memory-bridge-tests-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(_root);
            _backend = new FileBackend(_root);
            _memory = new FileMemoryBackend(_backend);
            _server = new MemoryBridgeMcpServer(_memory);
        }

        [TearDown]
        public async Task TearDown()
        {
            await _server.DisposeAsync();
            await _memory.DisposeAsync();
            if (!string.IsNullOrEmpty(_root) && Directory.Exists(_root))
            {
                try { Directory.Delete(_root, recursive: true); }
                catch (IOException) { /* 偶发占用，忽略 */ }
            }
        }

        // ===== (1) 构造校验 =====

        [Test]
        public void Constructor_NullMemory_Throws()
        {
            Assert.Throws<ArgumentNullException>(() => new MemoryBridgeMcpServer(null));
        }

        [Test]
        public void Constructor_DefaultConfig_UsesDocumentedDefaults()
        {
            // 反向验证：initialize 帧里出现的 serverInfo 应等于默认配置。
            var resp = CallRpc(_server, BuildRequest(1, "initialize", "{}"));
            var info = resp["result"]["serverInfo"].AsObject();
            Assert.That((string)info["name"], Is.EqualTo("cbim-memory-bridge-mcp"));
            Assert.That((string)info["version"], Is.EqualTo("1.0.0"));
        }

        [Test]
        public void Constructor_CustomConfig_PropagatedToInitialize()
        {
            var server = new MemoryBridgeMcpServer(_memory,
                new MemoryBridgeMcpServerConfig("my-bridge", "9.9.9"));
            var resp = CallRpc(server, BuildRequest(1, "initialize", "{}"));
            var info = resp["result"]["serverInfo"].AsObject();
            Assert.That((string)info["name"], Is.EqualTo("my-bridge"));
            Assert.That((string)info["version"], Is.EqualTo("9.9.9"));
        }

        [Test]
        public void Config_BlankServerName_Throws()
        {
            Assert.Throws<ArgumentException>(
                () => new MemoryBridgeMcpServer(_memory, new MemoryBridgeMcpServerConfig("   ", "1.0.0")));
        }

        [Test]
        public void Config_BlankServerVersion_Throws()
        {
            Assert.Throws<ArgumentException>(
                () => new MemoryBridgeMcpServer(_memory, new MemoryBridgeMcpServerConfig("ok", "  ")));
        }

        // ===== (2) JSON-RPC 协议级 =====

        [Test]
        public void ProcessLine_InvalidJson_ReturnsParseError()
        {
            string raw = CallProcessLineRaw(_server, "not json {{");
            Assert.That(raw, Is.Not.Null);
            var obj = JsonNode.Parse(raw).AsObject();
            Assert.That((int)obj["error"]["code"], Is.EqualTo(-32700));
        }

        [Test]
        public void ProcessLine_NonObjectRoot_ReturnsInvalidRequest()
        {
            var resp = CallRpc(_server, "[1,2,3]");
            Assert.That((int)resp["error"]["code"], Is.EqualTo(-32600));
        }

        [Test]
        public void ProcessLine_UnknownMethod_ReturnsMethodNotFound()
        {
            var resp = CallRpc(_server, BuildRequest(42, "does/not/exist", null));
            Assert.That((int)resp["error"]["code"], Is.EqualTo(-32601));
            Assert.That((int)resp["id"], Is.EqualTo(42));
        }

        [Test]
        public void ProcessLine_Notification_ReturnsNullEcho()
        {
            // notification = 无 id；server 应不回包（ProcessLine 返回 null）。
            var raw = CallProcessLineRaw(_server,
                @"{""jsonrpc"":""2.0"",""method"":""notifications/initialized""}");
            Assert.That(raw, Is.Null);
        }

        [Test]
        public void ProcessLine_Initialize_ReturnsCapabilitiesAndProtocolVersion()
        {
            var resp = CallRpc(_server,
                @"{""jsonrpc"":""2.0"",""id"":""abc"",""method"":""initialize"",""params"":{}}");
            Assert.That((string)resp["id"], Is.EqualTo("abc"));
            var result = resp["result"].AsObject();
            Assert.That((string)result["protocolVersion"], Is.EqualTo("2024-11-05"));
            Assert.That(result["capabilities"]["tools"], Is.Not.Null,
                "应声明 tools capability");
        }

        [Test]
        public void ProcessLine_ToolsList_ReturnsFiveTools()
        {
            var resp = CallRpc(_server, BuildRequest(1, "tools/list", null));
            var tools = resp["result"]["tools"].AsArray();
            Assert.That(tools.Count, Is.EqualTo(5));
            var names = tools.Select(t => (string)t["name"]).OrderBy(s => s).ToArray();
            Assert.That(names, Is.EquivalentTo(new[]
            {
                "memory_get", "memory_query", "memory_scan", "memory_stats", "memory_write",
            }));
            // 每个工具都应有 inputSchema
            foreach (var t in tools)
            {
                Assert.That(t["inputSchema"], Is.Not.Null);
                Assert.That(t["description"], Is.Not.Null);
            }
        }

        // ===== (3) memory_write =====

        [Test]
        public void ToolsCall_MemoryWrite_PersistsEntry()
        {
            var resp = CallRpc(_server, BuildToolsCall("memory_write",
                @"{""id"":""w-1"",""source"":""manual"",""text"":""hello bridge"",""tags"":[""a"",""b""]}"));
            var content = UnwrapToolContent(resp);
            Assert.That((bool)content["ok"], Is.True);

            var fetched = _memory.Get("w-1");
            Assert.That(fetched, Is.Not.Null);
            Assert.That(fetched.Source, Is.EqualTo("manual"));
            Assert.That(fetched.Text, Is.EqualTo("hello bridge"));
            Assert.That(fetched.Tags, Is.EquivalentTo(new[] { "a", "b" }));
            Assert.That(fetched.CreatedAt.Kind, Is.EqualTo(DateTimeKind.Utc),
                "memory_write 应以 UTC 落 CreatedAt");
        }

        [Test]
        public void ToolsCall_MemoryWrite_MissingId_ReturnsToolError()
        {
            var resp = CallRpc(_server, BuildToolsCall("memory_write",
                @"{""source"":""x"",""text"":""y""}"));
            var result = resp["result"].AsObject();
            Assert.That((bool)result["isError"], Is.True);
        }

        // ===== (4) memory_get =====

        [Test]
        public void ToolsCall_MemoryGet_ExistingId_ReturnsEntry()
        {
            _memory.Write(new MemoryEntry("g-1", "src",
                new DateTime(2026, 5, 28, 12, 0, 0, DateTimeKind.Utc),
                "fetch me", new[] { "tag1" }));

            var resp = CallRpc(_server, BuildToolsCall("memory_get",
                @"{""id"":""g-1""}"));
            var content = UnwrapToolContent(resp);
            var entry = content["entry"].AsObject();
            Assert.That((string)entry["id"], Is.EqualTo("g-1"));
            Assert.That((string)entry["source"], Is.EqualTo("src"));
            Assert.That((string)entry["text"], Is.EqualTo("fetch me"));
            Assert.That((string)entry["createdAt"], Is.EqualTo("2026-05-28T12:00:00.000Z"));
            var tagsArr = entry["tags"].AsArray();
            Assert.That(tagsArr.Count, Is.EqualTo(1));
            Assert.That((string)tagsArr[0], Is.EqualTo("tag1"));
        }

        [Test]
        public void ToolsCall_MemoryGet_MissingId_ReturnsNullEntry()
        {
            var resp = CallRpc(_server, BuildToolsCall("memory_get",
                @"{""id"":""never-existed""}"));
            var content = UnwrapToolContent(resp);
            Assert.That(content["entry"], Is.Null);
        }

        // ===== (5) memory_query =====

        [Test]
        public void ToolsCall_MemoryQuery_TopKEnforced()
        {
            _memory.Write(new MemoryEntry("q-a", "src", DateTime.UtcNow, "fox jumps", Array.Empty<string>()));
            _memory.Write(new MemoryEntry("q-b", "src", DateTime.UtcNow.AddSeconds(1), "fox runs", Array.Empty<string>()));
            _memory.Write(new MemoryEntry("q-c", "src", DateTime.UtcNow.AddSeconds(2), "fox sleeps", Array.Empty<string>()));

            var resp = CallRpc(_server, BuildToolsCall("memory_query",
                @"{""text"":""fox"",""topK"":2}"));
            var content = UnwrapToolContent(resp);
            var entries = content["entries"].AsArray();
            Assert.That(entries.Count, Is.EqualTo(2));
        }

        [Test]
        public void ToolsCall_MemoryQuery_NoMatch_ReturnsEmpty()
        {
            _memory.Write(new MemoryEntry("q-x", "src", DateTime.UtcNow, "alpha", Array.Empty<string>()));
            var resp = CallRpc(_server, BuildToolsCall("memory_query",
                @"{""text"":""zeta"",""topK"":5}"));
            var content = UnwrapToolContent(resp);
            Assert.That(content["entries"].AsArray().Count, Is.EqualTo(0));
        }

        // ===== (6) memory_scan =====

        [Test]
        public void ToolsCall_MemoryScan_FiltersBySource()
        {
            _memory.Write(new MemoryEntry("s-1", "distill", DateTime.UtcNow, "a", Array.Empty<string>()));
            _memory.Write(new MemoryEntry("s-2", "manual", DateTime.UtcNow.AddSeconds(1), "b", Array.Empty<string>()));
            _memory.Write(new MemoryEntry("s-3", "distill", DateTime.UtcNow.AddSeconds(2), "c", Array.Empty<string>()));

            var resp = CallRpc(_server, BuildToolsCall("memory_scan",
                @"{""source"":""distill""}"));
            var content = UnwrapToolContent(resp);
            var entries = content["entries"].AsArray();
            Assert.That(entries.Count, Is.EqualTo(2));
            var ids = entries.Select(e => (string)e["id"]).ToArray();
            Assert.That(ids, Is.EquivalentTo(new[] { "s-1", "s-3" }));
        }

        [Test]
        public void ToolsCall_MemoryScan_SinceFilterParsesIso8601()
        {
            var t0 = new DateTime(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc);
            var t1 = new DateTime(2026, 6, 1, 0, 0, 0, DateTimeKind.Utc);
            _memory.Write(new MemoryEntry("old", "src", t0, "old", Array.Empty<string>()));
            _memory.Write(new MemoryEntry("new", "src", t1, "new", Array.Empty<string>()));

            var resp = CallRpc(_server, BuildToolsCall("memory_scan",
                @"{""since"":""2026-03-01T00:00:00.000Z""}"));
            var content = UnwrapToolContent(resp);
            var entries = content["entries"].AsArray();
            Assert.That(entries.Count, Is.EqualTo(1));
            Assert.That((string)entries[0]["id"], Is.EqualTo("new"));
        }

        [Test]
        public void ToolsCall_MemoryScan_BadSince_ReturnsToolError()
        {
            var resp = CallRpc(_server, BuildToolsCall("memory_scan",
                @"{""since"":""not-a-date""}"));
            var result = resp["result"].AsObject();
            Assert.That((bool)result["isError"], Is.True);
        }

        [Test]
        public void ToolsCall_MemoryScan_NoArgs_ReturnsAll()
        {
            _memory.Write(new MemoryEntry("n-1", "x", DateTime.UtcNow, "a", Array.Empty<string>()));
            _memory.Write(new MemoryEntry("n-2", "y", DateTime.UtcNow.AddSeconds(1), "b", Array.Empty<string>()));

            var resp = CallRpc(_server, BuildToolsCall("memory_scan", "{}"));
            var content = UnwrapToolContent(resp);
            Assert.That(content["entries"].AsArray().Count, Is.EqualTo(2));
        }

        // ===== (7) memory_stats =====

        [Test]
        public void ToolsCall_MemoryStats_Empty_ReturnsZeroAndNulls()
        {
            var resp = CallRpc(_server, BuildToolsCall("memory_stats", "{}"));
            var content = UnwrapToolContent(resp);
            Assert.That((int)content["entryCount"], Is.EqualTo(0));
            Assert.That(content["oldestCreatedAt"], Is.Null);
            Assert.That(content["newestCreatedAt"], Is.Null);
        }

        [Test]
        public void ToolsCall_MemoryStats_FormatsTimesAsIso8601Utc()
        {
            var t0 = new DateTime(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc);
            var t1 = new DateTime(2026, 6, 1, 0, 0, 0, DateTimeKind.Utc);
            _memory.Write(new MemoryEntry("a", "x", t0, "a", Array.Empty<string>()));
            _memory.Write(new MemoryEntry("b", "x", t1, "b", Array.Empty<string>()));

            var resp = CallRpc(_server, BuildToolsCall("memory_stats", "{}"));
            var content = UnwrapToolContent(resp);
            Assert.That((int)content["entryCount"], Is.EqualTo(2));
            Assert.That((string)content["oldestCreatedAt"], Is.EqualTo("2026-01-01T00:00:00.000Z"));
            Assert.That((string)content["newestCreatedAt"], Is.EqualTo("2026-06-01T00:00:00.000Z"));
        }

        // ===== (8) tools/call 错误路径 =====

        [Test]
        public void ToolsCall_UnknownToolName_ReturnsMethodNotFoundError()
        {
            var resp = CallRpc(_server, BuildToolsCall("memory_nope", "{}"));
            Assert.That((int)resp["error"]["code"], Is.EqualTo(-32601));
        }

        [Test]
        public void ToolsCall_MissingParams_ReturnsInvalidParams()
        {
            var resp = CallRpc(_server, BuildRequest(1, "tools/call", null));
            Assert.That((int)resp["error"]["code"], Is.EqualTo(-32602));
        }

        // ===== (9) DisposeAsync =====

        [Test]
        public async Task DisposeAsync_Idempotent()
        {
            var server = new MemoryBridgeMcpServer(_memory);
            await server.DisposeAsync();
            await server.DisposeAsync();
            await server.DisposeAsync();
            Assert.Pass("多次 dispose 不抛");
        }

        [Test]
        public void RunAsync_AfterDispose_Throws()
        {
            var server = new MemoryBridgeMcpServer(_memory);
            server.DisposeAsync().AsTask().Wait();

            Assert.ThrowsAsync<ObjectDisposedException>(
                () => server.RunAsync(new StringReader(""), new StringWriter(), CancellationToken.None));
        }

        // ===== (10) 端到端 stdio loop =====

        [Test]
        public async Task RunAsync_ProcessesMultipleRequests_UntilEof()
        {
            // 三条请求 + EOF；预期三个响应回写到 output。
            var input = new StringReader(string.Join("\n", new[]
            {
                BuildRequest(1, "initialize", "{}"),
                BuildRequest(2, "tools/list", null),
                BuildToolsCall("memory_stats", "{}", id: 3),
            }) + "\n");
            var output = new StringWriter();

            await _server.RunAsync(input, output, CancellationToken.None);

            var lines = output.ToString().Split(new[] { '\n' }, StringSplitOptions.RemoveEmptyEntries);
            Assert.That(lines.Length, Is.EqualTo(3));

            var first = JsonNode.Parse(lines[0]).AsObject();
            Assert.That((int)first["id"], Is.EqualTo(1));
            Assert.That(first["result"]["serverInfo"], Is.Not.Null);

            var second = JsonNode.Parse(lines[1]).AsObject();
            Assert.That(second["result"]["tools"].AsArray().Count, Is.EqualTo(5));

            var third = JsonNode.Parse(lines[2]).AsObject();
            var thirdContent = JsonNode.Parse((string)third["result"]["content"][0]["text"]).AsObject();
            Assert.That((int)thirdContent["entryCount"], Is.EqualTo(0));
        }

        [Test]
        public async Task RunAsync_Notification_NoResponseEmitted()
        {
            var input = new StringReader(
                @"{""jsonrpc"":""2.0"",""method"":""notifications/initialized""}" + "\n" +
                BuildRequest(1, "ping", null) + "\n");
            var output = new StringWriter();

            await _server.RunAsync(input, output, CancellationToken.None);

            var lines = output.ToString().Split(new[] { '\n' }, StringSplitOptions.RemoveEmptyEntries);
            Assert.That(lines.Length, Is.EqualTo(1),
                "notification 不应产生响应；只有 ping 这一条应回包");
            Assert.That((int)JsonNode.Parse(lines[0])["id"], Is.EqualTo(1));
        }

        [Test]
        public async Task RunAsync_CancellationToken_StopsLoop()
        {
            // 不传 EOF——用一个永不结束的 reader，靠 cts 切断。
            var blocker = new BlockingReader();
            var output = new StringWriter();
            using var cts = new CancellationTokenSource();

            var runTask = _server.RunAsync(blocker, output, cts.Token);
            cts.Cancel();
            blocker.Unblock();   // 让 ReadLineAsync 返回 null（模拟 EOF + 取消同时发生）

            await runTask;       // 应正常完成，不抛
            Assert.Pass();
        }

        // ===== helpers =====

        /// <summary>
        /// 构造一条 JSON-RPC 2.0 请求字符串——把数字 id / 方法名 / 可选 params 拼出来。
        /// </summary>
        private static string BuildRequest(int id, string method, string paramsJson)
        {
            string paramsClause = string.IsNullOrEmpty(paramsJson) ? string.Empty : ",\"params\":" + paramsJson;
            return "{\"jsonrpc\":\"2.0\",\"id\":" + id + ",\"method\":\"" + method + "\"" + paramsClause + "}";
        }

        /// <summary>构造 tools/call 请求帧，<paramref name="argumentsJson"/> 为 arguments 对象 JSON。</summary>
        private static string BuildToolsCall(string toolName, string argumentsJson, int id = 1)
        {
            string paramsJson = "{\"name\":\"" + toolName + "\",\"arguments\":" + argumentsJson + "}";
            return BuildRequest(id, "tools/call", paramsJson);
        }

        private static JsonObject CallRpc(MemoryBridgeMcpServer server, string request)
        {
            string raw = CallProcessLineRaw(server, request);
            Assert.That(raw, Is.Not.Null, "本调用预期同步返回响应（非 notification）");
            return JsonNode.Parse(raw).AsObject();
        }

        private static string CallProcessLineRaw(MemoryBridgeMcpServer server, string request)
        {
            var mi = typeof(MemoryBridgeMcpServer).GetMethod(
                "ProcessLine",
                System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
            Assert.That(mi, Is.Not.Null, "未找到 ProcessLine — 接口契约破坏");
            return (string)mi.Invoke(server, new object[] { request });
        }

        private static JsonObject UnwrapToolContent(JsonObject rpcResp)
        {
            Assert.That(rpcResp["error"], Is.Null,
                "工具调用预期成功；意外错误：" + (rpcResp["error"] == null ? "<none>" : rpcResp["error"].ToJsonString()));
            var result = rpcResp["result"].AsObject();
            Assert.That((bool)result["isError"], Is.False,
                "工具结果不应是错误：" + result.ToJsonString());
            var text = (string)result["content"][0]["text"];
            return JsonNode.Parse(text).AsObject();
        }

        /// <summary>
        /// 测试用 reader——ReadLineAsync 阻塞到调用 <see cref="Unblock"/> 后才返回 null（模拟 EOF）。
        /// 用来验证「外部 ct 取消能让 RunAsync 退出，且 RunAsync 的 finally 不会卡死」。
        /// </summary>
        private sealed class BlockingReader : TextReader
        {
            private readonly SemaphoreSlim _gate = new SemaphoreSlim(0, 1);

            public void Unblock() => _gate.Release();

            public override async Task<string> ReadLineAsync()
            {
                await _gate.WaitAsync().ConfigureAwait(false);
                return null;
            }

            public override string ReadLine()
            {
                _gate.Wait();
                return null;
            }
        }
    }
}
#endif
