#if UNITY_INCLUDE_TESTS
using System;
using NUnit.Framework;
using CBIM.Skills;

namespace CBIM.Skills.Tests
{
    /// <summary>
    /// SkillDescriptor 单元测试。
    ///
    /// SkillDescriptor 跨维度共享——agent.Skills 与 module.Workflows 都用它。
    /// 四字段（Id / Name / Description / Content）的校验逻辑必须被 lock 住，
    /// 防止任一调用方将不合规的描述符注入 AIAgent 装配链。
    /// </summary>
    [TestFixture]
    public sealed class SkillDescriptorTests
    {
        // ===== 合法构造 =====

        [Test]
        public void Constructor_WithAllFields_SetsAllProperties()
        {
            var descriptor = new SkillDescriptor(
                id: "memory-write",
                name: "Memory Write",
                description: "把当前上下文落到 .cbim/memory/",
                content: "# Memory Write\n使用指引...");

            Assert.That(descriptor.Id, Is.EqualTo("memory-write"));
            Assert.That(descriptor.Name, Is.EqualTo("Memory Write"));
            Assert.That(descriptor.Description, Is.EqualTo("把当前上下文落到 .cbim/memory/"));
            Assert.That(descriptor.Content, Is.EqualTo("# Memory Write\n使用指引..."));
        }

        [Test]
        public void Constructor_WithoutContent_DefaultsToEmptyString()
        {
            var descriptor = new SkillDescriptor("dispatch", "Dispatch", "请求分类与路由");

            Assert.That(descriptor.Content, Is.EqualTo(string.Empty),
                "Content 缺省必须为空字符串，不能为 null");
        }

        [Test]
        public void Constructor_WithExplicitNullContent_FallsBackToEmpty()
        {
            var descriptor = new SkillDescriptor("dispatch", "Dispatch", "请求分类与路由", content: null);

            Assert.That(descriptor.Content, Is.EqualTo(string.Empty),
                "显式传 null 也应规范化为空字符串");
        }

        // ===== 非法 Id =====

        [Test]
        public void Constructor_WithNullId_Throws()
        {
            var ex = Assert.Throws<ArgumentException>(
                () => new SkillDescriptor(null, "Name", "Desc"));

            Assert.That(ex.ParamName, Is.EqualTo("id"));
        }

        [Test]
        public void Constructor_WithEmptyId_Throws()
        {
            var ex = Assert.Throws<ArgumentException>(
                () => new SkillDescriptor(string.Empty, "Name", "Desc"));

            Assert.That(ex.ParamName, Is.EqualTo("id"));
        }

        [Test]
        public void Constructor_WithWhitespaceId_Throws()
        {
            var ex = Assert.Throws<ArgumentException>(
                () => new SkillDescriptor("   ", "Name", "Desc"));

            Assert.That(ex.ParamName, Is.EqualTo("id"),
                "纯空格也必须被拒——IsNullOrWhiteSpace 语义不能被悄悄改成 IsNullOrEmpty");
        }

        // ===== 非法 Name =====

        [Test]
        public void Constructor_WithNullName_Throws()
        {
            var ex = Assert.Throws<ArgumentException>(
                () => new SkillDescriptor("id", null, "Desc"));

            Assert.That(ex.ParamName, Is.EqualTo("name"));
        }

        [Test]
        public void Constructor_WithEmptyName_Throws()
        {
            var ex = Assert.Throws<ArgumentException>(
                () => new SkillDescriptor("id", string.Empty, "Desc"));

            Assert.That(ex.ParamName, Is.EqualTo("name"));
        }

        [Test]
        public void Constructor_WithWhitespaceName_Throws()
        {
            var ex = Assert.Throws<ArgumentException>(
                () => new SkillDescriptor("id", "   ", "Desc"));

            Assert.That(ex.ParamName, Is.EqualTo("name"));
        }

        // ===== 非法 Description =====

        [Test]
        public void Constructor_WithNullDescription_Throws()
        {
            var ex = Assert.Throws<ArgumentException>(
                () => new SkillDescriptor("id", "Name", null));

            Assert.That(ex.ParamName, Is.EqualTo("description"));
        }

        [Test]
        public void Constructor_WithEmptyDescription_Throws()
        {
            var ex = Assert.Throws<ArgumentException>(
                () => new SkillDescriptor("id", "Name", string.Empty));

            Assert.That(ex.ParamName, Is.EqualTo("description"));
        }

        [Test]
        public void Constructor_WithWhitespaceDescription_Throws()
        {
            var ex = Assert.Throws<ArgumentException>(
                () => new SkillDescriptor("id", "Name", "   "));

            Assert.That(ex.ParamName, Is.EqualTo("description"));
        }

        // ===== ToString =====

        [Test]
        public void ToString_IncludesId()
        {
            var descriptor = new SkillDescriptor("memory-write", "Memory Write", "落盘");

            Assert.That(descriptor.ToString(), Does.Contain("memory-write"),
                "ToString 必须含 Id，便于日志/异常定位");
        }
    }
}
#endif
