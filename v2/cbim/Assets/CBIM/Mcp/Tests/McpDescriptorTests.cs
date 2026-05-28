#if UNITY_INCLUDE_TESTS
using System;
using System.Collections.Generic;
using NUnit.Framework;
using CBIM.Mcp;

namespace CBIM.Mcp.Tests
{
    /// <summary>
    /// McpDescriptor 家族单元测试。
    ///
    /// McpDescriptor 是 CBIM 内最显式的跨维度共享抽象——
    /// 同一个类型同时挂在 AgentDescription.McpList（能力维度）
    /// 和 ModuleDescription.McpList（业务维度）上。
    /// 三层都要锁：
    ///   1) 基类共享校验（Id / Name / Description 非空白）
    ///   2) 两子类各自字段校验 + 缺省值规范化
    ///   3) Transport 形态分派——装配器靠它分流到 stdio / http 启动器
    /// </summary>
    public static class McpDescriptorTests
    {
        // ============================================================
        // 基类校验：通过 StdioMcpDescriptor 作为测试载体
        // （McpDescriptor 是 abstract，无法直接 new）
        // ============================================================

        [TestFixture]
        public sealed class BaseValidation
        {
            [Test]
            public void Constructor_WithNullId_Throws()
            {
                var ex = Assert.Throws<ArgumentException>(() =>
                    new StdioMcpDescriptor(null, "name", "desc", "python"));

                Assert.That(ex.ParamName, Is.EqualTo("id"));
            }

            [Test]
            public void Constructor_WithEmptyId_Throws()
            {
                var ex = Assert.Throws<ArgumentException>(() =>
                    new StdioMcpDescriptor(string.Empty, "name", "desc", "python"));

                Assert.That(ex.ParamName, Is.EqualTo("id"));
            }

            [Test]
            public void Constructor_WithWhitespaceId_Throws()
            {
                var ex = Assert.Throws<ArgumentException>(() =>
                    new StdioMcpDescriptor("   ", "name", "desc", "python"));

                Assert.That(ex.ParamName, Is.EqualTo("id"),
                    "纯空格也必须被拒——IsNullOrWhiteSpace 语义不能被悄悄改成 IsNullOrEmpty");
            }

            [Test]
            public void Constructor_WithNullName_Throws()
            {
                var ex = Assert.Throws<ArgumentException>(() =>
                    new StdioMcpDescriptor("id", null, "desc", "python"));

                Assert.That(ex.ParamName, Is.EqualTo("name"));
            }

            [Test]
            public void Constructor_WithWhitespaceName_Throws()
            {
                var ex = Assert.Throws<ArgumentException>(() =>
                    new StdioMcpDescriptor("id", "  ", "desc", "python"));

                Assert.That(ex.ParamName, Is.EqualTo("name"));
            }

            [Test]
            public void Constructor_WithNullDescription_Throws()
            {
                var ex = Assert.Throws<ArgumentException>(() =>
                    new StdioMcpDescriptor("id", "name", null, "python"));

                Assert.That(ex.ParamName, Is.EqualTo("description"));
            }

            [Test]
            public void Constructor_WithWhitespaceDescription_Throws()
            {
                var ex = Assert.Throws<ArgumentException>(() =>
                    new StdioMcpDescriptor("id", "name", "\t\n", "python"));

                Assert.That(ex.ParamName, Is.EqualTo("description"));
            }

            [Test]
            public void ToString_IncludesId()
            {
                var descriptor = new StdioMcpDescriptor("unity-mcp", "Unity MCP", "Unity 桥", "python");

                Assert.That(descriptor.ToString(), Does.Contain("unity-mcp"),
                    "ToString 必须含 Id，便于日志/异常定位");
            }
        }

        // ============================================================
        // StdioMcpDescriptor
        // ============================================================

        [TestFixture]
        public sealed class Stdio
        {
            [Test]
            public void Constructor_WithRequiredFields_SetsCommandAndEmptyCollections()
            {
                var descriptor = new StdioMcpDescriptor(
                    "unity-mcp", "Unity MCP", "Unity 桥", "python");

                Assert.That(descriptor.Id, Is.EqualTo("unity-mcp"));
                Assert.That(descriptor.Name, Is.EqualTo("Unity MCP"));
                Assert.That(descriptor.Description, Is.EqualTo("Unity 桥"));
                Assert.That(descriptor.Command, Is.EqualTo("python"));
                Assert.That(descriptor.Args, Is.Not.Null.And.Empty,
                    "Args 缺省必须是空集合，不能为 null");
                Assert.That(descriptor.Env, Is.Not.Null.And.Empty,
                    "Env 缺省必须是空字典，不能为 null");
            }

            [Test]
            public void Constructor_WithArgsAndEnv_PreservesValues()
            {
                var args = new[] { "-m", "unity_mcp", "--port", "0" };
                var env = new Dictionary<string, string>
                {
                    ["UNITY_PROJECT"] = "/tmp/proj",
                    ["LOG_LEVEL"] = "debug",
                };

                var descriptor = new StdioMcpDescriptor(
                    "unity-mcp", "Unity MCP", "Unity 桥", "python", args, env);

                Assert.That(descriptor.Args, Is.EqualTo(args));
                Assert.That(descriptor.Env, Is.EqualTo(env));
            }

            [Test]
            public void Constructor_WithNullCommand_Throws()
            {
                var ex = Assert.Throws<ArgumentException>(() =>
                    new StdioMcpDescriptor("id", "name", "desc", null));

                Assert.That(ex.ParamName, Is.EqualTo("command"));
            }

            [Test]
            public void Constructor_WithEmptyCommand_Throws()
            {
                var ex = Assert.Throws<ArgumentException>(() =>
                    new StdioMcpDescriptor("id", "name", "desc", string.Empty));

                Assert.That(ex.ParamName, Is.EqualTo("command"));
            }

            [Test]
            public void Constructor_WithWhitespaceCommand_Throws()
            {
                var ex = Assert.Throws<ArgumentException>(() =>
                    new StdioMcpDescriptor("id", "name", "desc", "   "));

                Assert.That(ex.ParamName, Is.EqualTo("command"));
            }

            [Test]
            public void Transport_IsStdio()
            {
                var descriptor = new StdioMcpDescriptor("id", "name", "desc", "python");

                Assert.That(descriptor.Transport, Is.EqualTo(McpTransportKind.Stdio),
                    "Stdio 子类必须报 Stdio 形态——装配器靠这个分派启动器");
            }
        }

        // ============================================================
        // HttpMcpDescriptor
        // ============================================================

        [TestFixture]
        public sealed class Http
        {
            [Test]
            public void Constructor_WithRequiredFields_SetsEndpointAndEmptyAuxiliaries()
            {
                var descriptor = new HttpMcpDescriptor(
                    "cdn-prod-mcp", "CDN Prod", "生产 CDN 接入点",
                    "https://cdn.example.com/mcp");

                Assert.That(descriptor.Id, Is.EqualTo("cdn-prod-mcp"));
                Assert.That(descriptor.Name, Is.EqualTo("CDN Prod"));
                Assert.That(descriptor.Description, Is.EqualTo("生产 CDN 接入点"));
                Assert.That(descriptor.Endpoint, Is.EqualTo("https://cdn.example.com/mcp"));
                Assert.That(descriptor.AuthToken, Is.EqualTo(string.Empty),
                    "AuthToken 缺省必须是空字符串，不能为 null");
                Assert.That(descriptor.Headers, Is.Not.Null.And.Empty,
                    "Headers 缺省必须是空字典，不能为 null");
            }

            [Test]
            public void Constructor_WithAuthTokenAndHeaders_PreservesValues()
            {
                var headers = new Dictionary<string, string>
                {
                    ["X-Tenant"] = "acme",
                    ["X-Region"] = "ap-east-1",
                };

                var descriptor = new HttpMcpDescriptor(
                    "cdn-prod-mcp", "CDN Prod", "生产 CDN 接入点",
                    "https://cdn.example.com/mcp",
                    authToken: "secret-token",
                    headers: headers);

                Assert.That(descriptor.AuthToken, Is.EqualTo("secret-token"));
                Assert.That(descriptor.Headers, Is.EqualTo(headers));
            }

            [Test]
            public void Constructor_WithNullEndpoint_Throws()
            {
                var ex = Assert.Throws<ArgumentException>(() =>
                    new HttpMcpDescriptor("id", "name", "desc", null));

                Assert.That(ex.ParamName, Is.EqualTo("endpoint"));
            }

            [Test]
            public void Constructor_WithEmptyEndpoint_Throws()
            {
                var ex = Assert.Throws<ArgumentException>(() =>
                    new HttpMcpDescriptor("id", "name", "desc", string.Empty));

                Assert.That(ex.ParamName, Is.EqualTo("endpoint"));
            }

            [Test]
            public void Constructor_WithWhitespaceEndpoint_Throws()
            {
                var ex = Assert.Throws<ArgumentException>(() =>
                    new HttpMcpDescriptor("id", "name", "desc", "   "));

                Assert.That(ex.ParamName, Is.EqualTo("endpoint"));
            }

            [Test]
            public void Transport_IsHttp()
            {
                var descriptor = new HttpMcpDescriptor(
                    "id", "name", "desc", "https://example.com/mcp");

                Assert.That(descriptor.Transport, Is.EqualTo(McpTransportKind.Http),
                    "Http 子类必须报 Http 形态——装配器靠这个分派启动器");
            }
        }
    }
}
#endif
