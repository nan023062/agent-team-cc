#if UNITY_INCLUDE_TESTS
using System;
using System.IO;
using System.Linq;
using NUnit.Framework;
using CBIM.Skills;
using CBIM.Storage;

namespace CBIM.Skills.Tests
{
    /// <summary>
    /// FileSkillStore 单元测试。
    ///
    /// 覆盖契约规约：
    ///   - 空 store List 返回 0
    ///   - Put 后 Get 拿回同实例
    ///   - 同 Id Put 是 upsert（不抛、覆盖）
    ///   - Delete 不存在的 Id 返回 false
    ///   - Query 子串匹配
    ///
    /// 每个测试用独立临时根目录，避免相互污染。
    /// </summary>
    [TestFixture]
    public sealed class FileSkillStoreTests
    {
        private string _root;
        private FileBackend _backend;

        [SetUp]
        public void SetUp()
        {
            _root = Path.Combine(Path.GetTempPath(),
                "cbim-skills-tests-" + Guid.NewGuid().ToString("N"));
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
            Assert.Throws<ArgumentNullException>(() => new FileSkillStore(null));
        }

        [Test]
        public void Constructor_WithWhitespaceSubdir_Throws()
        {
            Assert.Throws<ArgumentException>(() => new FileSkillStore(_backend, "   "));
        }

        // ===== 空 store =====

        [Test]
        public void List_OnEmptyStore_ReturnsZero()
        {
            var store = new FileSkillStore(_backend);

            Assert.That(store.List(), Is.Empty,
                "空 store 必须返回 0 条，不能抛或返 null");
        }

        [Test]
        public void Get_OnEmptyStore_ReturnsNull()
        {
            var store = new FileSkillStore(_backend);

            Assert.That(store.Get("missing"), Is.Null);
        }

        // ===== Put / Get 基本路径 =====

        [Test]
        public void Put_ThenGet_ReturnsSameDescriptor()
        {
            var store = new FileSkillStore(_backend);
            var descriptor = new SkillDescriptor("memory-write", "Memory Write", "把上下文落盘");

            store.Put(descriptor);
            var fetched = store.Get("memory-write");

            Assert.That(fetched, Is.SameAs(descriptor),
                "内存索引应返回原实例引用——不应过一次磁盘往返");
        }

        [Test]
        public void Put_PersistsToDisk()
        {
            var store = new FileSkillStore(_backend);
            store.Put(new SkillDescriptor("dispatch", "Dispatch", "请求分类与路由", "# 内容"));

            string expected = Path.Combine(_root, "skills", "dispatch.json");
            Assert.That(File.Exists(expected), Is.True,
                "落盘路径必须是 <root>/skills/<id>.json");
        }

        [Test]
        public void List_AfterMultiplePuts_ReturnsAll()
        {
            var store = new FileSkillStore(_backend);
            store.Put(new SkillDescriptor("a", "A", "alpha"));
            store.Put(new SkillDescriptor("b", "B", "beta"));
            store.Put(new SkillDescriptor("c", "C", "gamma"));

            var all = store.List();

            Assert.That(all.Count, Is.EqualTo(3));
            Assert.That(all.Select(d => d.Id), Is.EquivalentTo(new[] { "a", "b", "c" }));
        }

        // ===== Upsert =====

        [Test]
        public void Put_SameId_IsUpsert()
        {
            var store = new FileSkillStore(_backend);
            store.Put(new SkillDescriptor("dispatch", "旧名", "旧描述", "旧内容"));
            store.Put(new SkillDescriptor("dispatch", "新名", "新描述", "新内容"));

            var fetched = store.Get("dispatch");
            var all = store.List();

            Assert.That(fetched.Name, Is.EqualTo("新名"));
            Assert.That(fetched.Description, Is.EqualTo("新描述"));
            Assert.That(fetched.Content, Is.EqualTo("新内容"));
            Assert.That(all.Count, Is.EqualTo(1),
                "upsert 不应造成重复条目");
        }

        [Test]
        public void Put_NullDescriptor_Throws()
        {
            var store = new FileSkillStore(_backend);

            Assert.Throws<ArgumentNullException>(() => store.Put(null));
        }

        // ===== Delete =====

        [Test]
        public void Delete_ExistingId_ReturnsTrue_AndRemovesFromIndexAndDisk()
        {
            var store = new FileSkillStore(_backend);
            store.Put(new SkillDescriptor("tmp", "Tmp", "临时"));

            bool deleted = store.Delete("tmp");

            Assert.That(deleted, Is.True);
            Assert.That(store.Get("tmp"), Is.Null);
            Assert.That(store.List(), Is.Empty);

            string path = Path.Combine(_root, "skills", "tmp.json");
            Assert.That(File.Exists(path), Is.False, "落盘文件应同步删除");
        }

        [Test]
        public void Delete_MissingId_ReturnsFalse()
        {
            var store = new FileSkillStore(_backend);

            Assert.That(store.Delete("never-existed"), Is.False);
        }

        [Test]
        public void Delete_NullOrWhitespaceId_ReturnsFalse()
        {
            var store = new FileSkillStore(_backend);

            Assert.That(store.Delete(null), Is.False);
            Assert.That(store.Delete(""), Is.False);
            Assert.That(store.Delete("   "), Is.False);
        }

        // ===== Query 子串匹配 =====

        [Test]
        public void Query_MatchesSubstring_InId()
        {
            var store = new FileSkillStore(_backend);
            store.Put(new SkillDescriptor("memory-write", "Memory Write", "落盘"));
            store.Put(new SkillDescriptor("memory-query", "Memory Query", "查询"));
            store.Put(new SkillDescriptor("dispatch", "Dispatch", "路由"));

            var hits = store.Query("memory", topK: 10);

            Assert.That(hits.Count, Is.EqualTo(2));
            Assert.That(hits.Select(d => d.Id),
                Is.EquivalentTo(new[] { "memory-write", "memory-query" }));
        }

        [Test]
        public void Query_MatchesSubstring_InContent()
        {
            var store = new FileSkillStore(_backend);
            store.Put(new SkillDescriptor("a", "A", "alpha", "需要调 git-mcp 看 diff"));
            store.Put(new SkillDescriptor("b", "B", "beta", "需要调 read_text 读 README"));

            var hits = store.Query("git-mcp", topK: 10);

            Assert.That(hits.Count, Is.EqualTo(1));
            Assert.That(hits[0].Id, Is.EqualTo("a"));
        }

        [Test]
        public void Query_IsCaseInsensitive()
        {
            var store = new FileSkillStore(_backend);
            store.Put(new SkillDescriptor("dispatch", "Dispatch", "请求分类与路由"));

            var hits = store.Query("DISPATCH", topK: 10);

            Assert.That(hits.Count, Is.EqualTo(1));
            Assert.That(hits[0].Id, Is.EqualTo("dispatch"));
        }

        [Test]
        public void Query_RespectsTopK()
        {
            var store = new FileSkillStore(_backend);
            for (int i = 0; i < 5; i++)
            {
                store.Put(new SkillDescriptor($"skill-{i}", $"Skill {i}", "通用描述"));
            }

            var hits = store.Query("通用", topK: 3);

            Assert.That(hits.Count, Is.EqualTo(3));
        }

        [Test]
        public void Query_EmptyText_ReturnsEmpty()
        {
            var store = new FileSkillStore(_backend);
            store.Put(new SkillDescriptor("a", "A", "alpha"));

            Assert.That(store.Query("", topK: 10), Is.Empty);
            Assert.That(store.Query("   ", topK: 10), Is.Empty);
            Assert.That(store.Query(null, topK: 10), Is.Empty);
        }

        [Test]
        public void Query_NonPositiveTopK_ReturnsEmpty()
        {
            var store = new FileSkillStore(_backend);
            store.Put(new SkillDescriptor("a", "A", "alpha"));

            Assert.That(store.Query("alpha", topK: 0), Is.Empty);
            Assert.That(store.Query("alpha", topK: -1), Is.Empty);
        }

        // ===== 启动扫盘 =====

        [Test]
        public void Constructor_RehydratesFromDisk()
        {
            // 先用一个 store 写入两条，再用新 store 实例验证启动扫描
            var first = new FileSkillStore(_backend);
            first.Put(new SkillDescriptor("a", "A", "alpha", "内容 A"));
            first.Put(new SkillDescriptor("b", "B", "beta"));

            var second = new FileSkillStore(_backend);

            Assert.That(second.List().Count, Is.EqualTo(2));
            var a = second.Get("a");
            Assert.That(a, Is.Not.Null);
            Assert.That(a.Name, Is.EqualTo("A"));
            Assert.That(a.Description, Is.EqualTo("alpha"));
            Assert.That(a.Content, Is.EqualTo("内容 A"));
        }

        [Test]
        public void Constructor_WithCustomSubdir_IsolatesFromDefault()
        {
            var defaultStore = new FileSkillStore(_backend);
            defaultStore.Put(new SkillDescriptor("d", "Default", "默认 subdir"));

            var altStore = new FileSkillStore(_backend, subdir: "workflows");

            Assert.That(altStore.List(), Is.Empty,
                "自定义 subdir 应与默认 'skills' 隔离");

            altStore.Put(new SkillDescriptor("w", "Workflow", "另一子目录"));

            string expected = Path.Combine(_root, "workflows", "w.json");
            Assert.That(File.Exists(expected), Is.True);
        }
    }
}
#endif
