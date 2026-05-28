#if UNITY_INCLUDE_TESTS
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using NUnit.Framework;
using CBIM.Memory;
using CBIM.Storage;

namespace CBIM.Memory.Tests
{
    /// <summary>
    /// FileMemoryBackend 行为测试。
    ///
    /// 三层覆盖：
    ///   - 接口契约：可经 <see cref="IMemoryService"/> 引用调用（编译即验证 LSP）
    ///   - 落盘路径：默认 / 自定义 subDir 都按 .cbim/&lt;subDir&gt;/&lt;id&gt;.json 落
    ///   - CRUD + Query/Scan/Stats + Dispose 幂等
    ///
    /// 每个测试独立临时根目录，TearDown 清理。
    /// </summary>
    [TestFixture]
    public sealed class FileMemoryBackendTests
    {
        private string _root;
        private FileBackend _backend;

        [SetUp]
        public void SetUp()
        {
            _root = Path.Combine(Path.GetTempPath(),
                "cbim-memory-tests-" + Guid.NewGuid().ToString("N"));
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

        // ===== (1) 接口契约 =====

        [Test]
        public void Constructor_ReturnsInstance_AssignableToIMemoryService()
        {
            // 编译期断言 LSP：FileMemoryBackend 必须可替换 IMemoryService 使用。
            IMemoryService svc = new FileMemoryBackend(_backend);

            Assert.That(svc, Is.Not.Null);
            Assert.That(svc, Is.InstanceOf<IMemoryService>());
        }

        [Test]
        public void Constructor_WithNullStorage_Throws()
        {
            Assert.Throws<ArgumentNullException>(() => new FileMemoryBackend(null));
        }

        [Test]
        public void Constructor_WithWhitespaceSubDir_Throws()
        {
            Assert.Throws<ArgumentException>(() => new FileMemoryBackend(_backend, "   "));
        }

        // ===== (2) 默认 subDir 落盘路径 =====

        [Test]
        public void Write_WithDefaultSubDir_PersistsTo_MemoryMedium()
        {
            IMemoryService svc = new FileMemoryBackend(_backend);
            var entry = MakeEntry("entry-a", "distill", "hello world");

            svc.Write(entry);

            string expected = Path.Combine(_root, ".cbim", "memory", "medium", "entry-a.json");
            Assert.That(File.Exists(expected), Is.True,
                "默认 subDir 应落盘到 .cbim/memory/medium/<id>.json，实际未发现：" + expected);
        }

        // ===== (3) 自定义 subDir 落盘路径 =====

        [Test]
        public void Write_WithCustomSubDir_PersistsTo_CustomPath()
        {
            IMemoryService svc = new FileMemoryBackend(_backend, "memory/agent-xyz");
            var entry = MakeEntry("entry-b", "manual", "custom-dir payload");

            svc.Write(entry);

            string expected = Path.Combine(_root, ".cbim", "memory", "agent-xyz", "entry-b.json");
            Assert.That(File.Exists(expected), Is.True,
                "自定义 subDir 应落盘到 .cbim/memory/agent-xyz/<id>.json，实际未发现：" + expected);
        }

        // ===== (4) Write + Get 往返 =====

        [Test]
        public void WriteThenGet_RoundTrip_PreservesAllFields()
        {
            IMemoryService svc = new FileMemoryBackend(_backend);
            var when = new DateTime(2026, 1, 15, 9, 30, 0, DateTimeKind.Utc);
            var original = new MemoryEntry(
                Id: "rt-1",
                Source: "distill",
                CreatedAt: when,
                Text: "round trip text",
                Tags: new[] { "alpha", "beta" });

            svc.Write(original);
            var fetched = svc.Get("rt-1");

            Assert.That(fetched, Is.Not.Null, "Get 应返回写入的条目");
            Assert.That(fetched.Id, Is.EqualTo("rt-1"));
            Assert.That(fetched.Source, Is.EqualTo("distill"));
            Assert.That(fetched.CreatedAt, Is.EqualTo(when));
            Assert.That(fetched.Text, Is.EqualTo("round trip text"));
            Assert.That(fetched.Tags, Is.EquivalentTo(new[] { "alpha", "beta" }));
        }

        [Test]
        public void Write_NullEntry_Throws()
        {
            IMemoryService svc = new FileMemoryBackend(_backend);

            Assert.Throws<ArgumentNullException>(() => svc.Write(null));
        }

        [Test]
        public void Write_EntryWithBlankId_Throws()
        {
            IMemoryService svc = new FileMemoryBackend(_backend);
            var bad = new MemoryEntry("   ", "src", DateTime.UtcNow, "x", Array.Empty<string>());

            Assert.Throws<ArgumentException>(() => svc.Write(bad));
        }

        [Test]
        public void Write_NullTags_NormalizedToEmptyList_OnReadBack()
        {
            IMemoryService svc = new FileMemoryBackend(_backend);
            var entry = new MemoryEntry("nt-1", "src", DateTime.UtcNow, "txt", Tags: null);

            svc.Write(entry);
            var fetched = svc.Get("nt-1");

            Assert.That(fetched, Is.Not.Null);
            Assert.That(fetched.Tags, Is.Not.Null,
                "写入时 null Tags 应规范化为空列表，避免反序列化分支");
            Assert.That(fetched.Tags.Count, Is.EqualTo(0));
        }

        // ===== (5) Query 关键词命中 =====

        [Test]
        public void Query_KeywordHit_ReturnsRelevantEntries()
        {
            IMemoryService svc = new FileMemoryBackend(_backend);
            svc.Write(MakeEntry("q-a", "distill", "the quick brown fox"));
            svc.Write(MakeEntry("q-b", "distill", "lazy dog sleeps"));

            var hits = svc.Query("fox", topK: 10);

            Assert.That(hits.Count, Is.EqualTo(1),
                "Query 应只命中含 'fox' 的条目");
            Assert.That(hits[0].Id, Is.EqualTo("q-a"));
        }

        [Test]
        public void Query_EmptyText_ReturnsEmpty()
        {
            IMemoryService svc = new FileMemoryBackend(_backend);
            svc.Write(MakeEntry("q-x", "distill", "anything"));

            Assert.That(svc.Query("", topK: 10), Is.Empty);
            Assert.That(svc.Query("   ", topK: 10), Is.Empty);
            Assert.That(svc.Query(null, topK: 10), Is.Empty);
        }

        [Test]
        public void Query_NonPositiveTopK_ReturnsEmpty()
        {
            IMemoryService svc = new FileMemoryBackend(_backend);
            svc.Write(MakeEntry("q-y", "distill", "anything"));

            Assert.That(svc.Query("anything", topK: 0), Is.Empty);
            Assert.That(svc.Query("anything", topK: -1), Is.Empty);
        }

        // ===== (6) Scan 按 SourceEquals 过滤 =====

        [Test]
        public void Scan_FiltersBy_SourceEquals()
        {
            IMemoryService svc = new FileMemoryBackend(_backend);
            svc.Write(MakeEntry("s-1", "distill", "auto from distill"));
            svc.Write(MakeEntry("s-2", "manual", "manual note"));
            svc.Write(MakeEntry("s-3", "distill", "another distill"));

            var hits = svc.Scan(new MemoryScanFilter(SourceEquals: "distill"));

            Assert.That(hits.Count, Is.EqualTo(2));
            Assert.That(hits.Select(e => e.Id),
                Is.EquivalentTo(new[] { "s-1", "s-3" }),
                "SourceEquals='distill' 应只返回 distill 来源");
        }

        [Test]
        public void Scan_NullFilter_ReturnsAll_OrderedByCreatedAtDesc()
        {
            IMemoryService svc = new FileMemoryBackend(_backend);
            var older = new MemoryEntry("o-old", "x",
                new DateTime(2025, 1, 1, 0, 0, 0, DateTimeKind.Utc),
                "old", Array.Empty<string>());
            var newer = new MemoryEntry("o-new", "x",
                new DateTime(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc),
                "new", Array.Empty<string>());

            svc.Write(older);
            svc.Write(newer);

            var all = svc.Scan(null);

            Assert.That(all.Count, Is.EqualTo(2));
            Assert.That(all[0].Id, Is.EqualTo("o-new"),
                "Scan 应按 CreatedAt 倒序——最新在最前");
            Assert.That(all[1].Id, Is.EqualTo("o-old"));
        }

        // ===== (7) Stats EntryCount =====

        [Test]
        public void Stats_OnEmpty_ReturnsZero_AndNullExtremes()
        {
            IMemoryService svc = new FileMemoryBackend(_backend);

            var stats = svc.Stats();

            Assert.That(stats.TotalEntries, Is.EqualTo(0));
            Assert.That(stats.OldestCreatedAt, Is.Null);
            Assert.That(stats.NewestCreatedAt, Is.Null);
        }

        [Test]
        public void Stats_CountReflectsWrites()
        {
            IMemoryService svc = new FileMemoryBackend(_backend);
            svc.Write(MakeEntry("c-1", "src", "a"));
            svc.Write(MakeEntry("c-2", "src", "b"));
            svc.Write(MakeEntry("c-3", "src", "c"));

            var stats = svc.Stats();

            Assert.That(stats.TotalEntries, Is.EqualTo(3));
            Assert.That(stats.OldestCreatedAt, Is.Not.Null);
            Assert.That(stats.NewestCreatedAt, Is.Not.Null);
        }

        // ===== (8) DisposeAsync 幂等 =====

        [Test]
        public async Task DisposeAsync_CalledMultipleTimes_IsIdempotent_AndDoesNotThrow()
        {
            IMemoryService svc = new FileMemoryBackend(_backend);
            svc.Write(MakeEntry("d-1", "src", "any"));

            await svc.DisposeAsync();
            await svc.DisposeAsync();
            await svc.DisposeAsync();

            // 没抛即通过；显式断言以让失败信息清楚。
            Assert.Pass("DisposeAsync 多次调用未抛异常。");
        }

        // ===== (9) Get 不存在 / 空白 Id =====

        [Test]
        public void Get_MissingId_ReturnsNull()
        {
            IMemoryService svc = new FileMemoryBackend(_backend);

            Assert.That(svc.Get("never-existed"), Is.Null);
        }

        [Test]
        public void Get_BlankId_ReturnsNull()
        {
            IMemoryService svc = new FileMemoryBackend(_backend);

            Assert.That(svc.Get(null), Is.Null);
            Assert.That(svc.Get(""), Is.Null);
            Assert.That(svc.Get("   "), Is.Null);
        }

        // ===== helpers =====

        private static MemoryEntry MakeEntry(string id, string source, string text)
        {
            return new MemoryEntry(
                Id: id,
                Source: source,
                CreatedAt: DateTime.UtcNow,
                Text: text,
                Tags: Array.Empty<string>());
        }
    }
}
#endif
