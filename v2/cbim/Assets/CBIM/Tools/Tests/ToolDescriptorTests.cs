#if UNITY_INCLUDE_TESTS
using System;
using NUnit.Framework;
using CBIM.Tools;

namespace CBIM.Tools.Tests
{
    /// <summary>
    /// ToolDescriptor 单元测试。
    ///
    /// ToolDescriptor 是基建抽象层第一公民——任何调用方都会构造它。
    /// 校验逻辑（FamilyName 非空 / 非空白）必须被测试 lock 住，
    /// 防止后续重构悄悄放宽前置条件。
    /// </summary>
    [TestFixture]
    public sealed class ToolDescriptorTests
    {
        // ===== 合法构造 =====

        [Test]
        public void Constructor_WithFamilyNameOnly_SetsFamilyAndEmptyDescription()
        {
            var descriptor = new ToolDescriptor("Files");

            Assert.That(descriptor.FamilyName, Is.EqualTo("Files"));
            Assert.That(descriptor.Description, Is.EqualTo(string.Empty),
                "Description 缺省必须为空字符串，不能为 null");
        }

        [Test]
        public void Constructor_WithFamilyAndDescription_SetsBoth()
        {
            var descriptor = new ToolDescriptor("Search", "全文检索能力");

            Assert.That(descriptor.FamilyName, Is.EqualTo("Search"));
            Assert.That(descriptor.Description, Is.EqualTo("全文检索能力"));
        }

        [Test]
        public void Constructor_WithExplicitNullDescription_FallsBackToEmpty()
        {
            var descriptor = new ToolDescriptor("Files", description: null);

            Assert.That(descriptor.Description, Is.EqualTo(string.Empty),
                "显式传 null 也应规范化为空字符串");
        }

        // ===== 非法 FamilyName =====

        [Test]
        public void Constructor_WithNullFamilyName_Throws()
        {
            var ex = Assert.Throws<ArgumentException>(() => new ToolDescriptor(null));

            Assert.That(ex.ParamName, Is.EqualTo("familyName"),
                "ArgumentException 必须携带 paramName=familyName");
        }

        [Test]
        public void Constructor_WithEmptyFamilyName_Throws()
        {
            var ex = Assert.Throws<ArgumentException>(() => new ToolDescriptor(string.Empty));

            Assert.That(ex.ParamName, Is.EqualTo("familyName"));
        }

        [Test]
        public void Constructor_WithWhitespaceFamilyName_Throws()
        {
            var ex = Assert.Throws<ArgumentException>(() => new ToolDescriptor("   "));

            Assert.That(ex.ParamName, Is.EqualTo("familyName"),
                "纯空格也必须被拒——IsNullOrWhiteSpace 语义不能被悄悄改成 IsNullOrEmpty");
        }

        // ===== ToString =====

        [Test]
        public void ToString_IncludesFamilyName()
        {
            var descriptor = new ToolDescriptor("Files");

            Assert.That(descriptor.ToString(), Does.Contain("Files"),
                "ToString 必须含 FamilyName，便于日志/异常定位");
        }
    }
}
#endif
