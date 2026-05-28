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
using CBIM.Memory;

namespace CBIM.AgentSystem.Brain.Tests
{
    /// <summary>
    /// <see cref="PrefrontalCortex"/> 单元测试。
    ///
    /// 覆盖：
    ///   - CallableBrains 中每个子脑区被包装成一个 <c>__brain_call_*</c> AIFunction
    ///   - 命名规则：BrainId 中 <c>'.'</c> 与 <c>'-'</c> 替换为 <c>'_'</c>
    ///       例：<c>"motor-cortex.native"</c> → <c>__brain_call_motor_cortex_native</c>
    ///   - handler 投递到子脑区 InvokeAsync 并返回 outcome.Summary（透过 FakeChatClient
    ///     直接 invoke 包装好的 AIFunction 验证）
    ///   - descriptor.Kind 必须 = PrefrontalCortex，否则 throw
    ///   - 「主脑回调恒为 null」铁律——基类 PrefrontalCallback 字段为 null
    ///   - 「CallableBrains 不含 PrefrontalCortex 自身」铁律
    /// </summary>
    [TestFixture]
    public sealed class PrefrontalCortexTests
    {
        // ===== (1) 每个子脑区 → 一个 __brain_call_* AIFunction =====

        [Test]
        public void PrefrontalCortex_registers_brain_call_function_per_callable()
        {
            var memory = new InMemoryFakeMemoryService();
            var chat = new FakeChatClient("ok");
            var callback = new FakePrefrontalCallback();

            var parietalDesc = BuildStandardDescriptor(
                "parietal-lobe", "parietal", StandardBrainKind.ParietalLobe);
            var motorDesc = BuildStandardDescriptor(
                "motor-cortex.native", "motor", StandardBrainKind.NativeMotorCortex);

            var parietal = new ParietalLobe(parietalDesc, memory, chat, callback);
            var motor = new NativeMotorCortex(motorDesc, memory, chat, callback);

            var pfcDesc = BuildPrefrontalDescriptor();
            var pfc = new PrefrontalCortex(pfcDesc, memory, chat, new BrainBase[] { parietal, motor });

            Assert.That(pfc.CallableBrains.Count, Is.EqualTo(2));
            var toolNames = ExtractToolNames(pfc.Agent);
            Assert.That(toolNames, Is.EquivalentTo(new[]
            {
                "__brain_call_parietal_lobe",
                "__brain_call_motor_cortex_native",
            }));
        }

        // ===== (2) 命名规则：'.' / '-' → '_' =====

        [Test]
        public void Brain_call_function_name_replaces_dots_and_dashes_with_underscores()
        {
            var memory = new InMemoryFakeMemoryService();
            var chat = new FakeChatClient("ok");
            var callback = new FakePrefrontalCallback();

            // BrainId 含 '.' 与 '-' 两种字符——命名规则同时校验。
            var motorDesc = BuildStandardDescriptor(
                "motor-cortex.claude-code", "motor", StandardBrainKind.NativeMotorCortex);
            var motor = new NativeMotorCortex(motorDesc, memory, chat, callback);

            var pfcDesc = BuildPrefrontalDescriptor();
            var pfc = new PrefrontalCortex(pfcDesc, memory, chat, new BrainBase[] { motor });

            var toolNames = ExtractToolNames(pfc.Agent);
            Assert.That(toolNames, Has.Member("__brain_call_motor_cortex_claude_code"),
                "BrainId 'motor-cortex.claude-code' 应映射到 '__brain_call_motor_cortex_claude_code'");
        }

        // ===== (3) handler 投递到子脑区 + 返回 Summary =====

        [Test]
        public async Task Brain_call_handler_dispatches_to_callable_InvokeAsync_and_returns_summary()
        {
            var memory = new InMemoryFakeMemoryService();
            var motorChat = new FakeChatClient("motor-says-hello");
            var pfcChat = new FakeChatClient("not-used-here");
            var callback = new FakePrefrontalCallback();

            var motorDesc = BuildStandardDescriptor(
                "motor-cortex.native", "motor", StandardBrainKind.NativeMotorCortex);
            var motor = new NativeMotorCortex(motorDesc, memory, motorChat, callback);

            var pfcDesc = BuildPrefrontalDescriptor();
            var pfc = new PrefrontalCortex(pfcDesc, memory, pfcChat, new BrainBase[] { motor });

            var fn = ExtractTools(pfc.Agent)
                .OfType<AIFunction>()
                .Single(f => f.Name == "__brain_call_motor_cortex_native");

            // 调用 AIFunction handler——绕过 LLM 闭环，直接验证「下发到子脑区」语义。
            var args = new Dictionary<string, object>
            {
                ["intent"] = "请帮我建文件",
                ["structured_input"] = null,
                ["context"] = null,
            };
            var result = await fn.InvokeAsync(new AIFunctionArguments(args), CancellationToken.None);

            // result.ToString() 应等于子脑区 outcome.Summary（FakeChatClient 固定返回值）。
            string text = result?.ToString();
            Assert.That(text, Is.EqualTo("motor-says-hello"),
                "handler 应把 callable.InvokeAsync 的 Summary 直返给 LLM 作 ToolMessage。");

            Assert.That(motorChat.CallCount, Is.GreaterThanOrEqualTo(1),
                "子脑区 (NativeMotorCortex) 的 IChatClient 应被驱动至少一次。");
        }

        // ===== (4) descriptor.Kind 不对 → throw =====

        [Test]
        public void PrefrontalCortex_rejects_descriptor_with_wrong_kind()
        {
            var memory = new InMemoryFakeMemoryService();
            var chat = new FakeChatClient("ok");

            // descriptor.Kind = ParietalLobe 而非 PrefrontalCortex——构造期 throw。
            var wrong = new StandardBrainDescriptor(
                brainId: "prefrontal-cortex",
                role: "prefrontal",
                soul: "soul",
                kind: StandardBrainKind.ParietalLobe,
                capability: BuildStubCapability())
            {
                IsPrefrontal = false,
            };

            Assert.Throws<InvalidOperationException>(
                () => new PrefrontalCortex(wrong, memory, chat, Array.Empty<BrainBase>()),
                "PrefrontalCortex 构造期要求 descriptor.Kind=PrefrontalCortex。");
        }

        // ===== (5) 主脑回调恒为 null =====

        [Test]
        public void PrefrontalCortex_callback_is_null_by_design()
        {
            var memory = new InMemoryFakeMemoryService();
            var chat = new FakeChatClient("ok");

            var pfcDesc = BuildPrefrontalDescriptor();
            var pfc = new PrefrontalCortex(pfcDesc, memory, chat, Array.Empty<BrainBase>());

            // PrefrontalCallback 是 protected——用反射验证「主脑自己不回报自己」。
            var prop = typeof(BrainBase).GetProperty("PrefrontalCallback",
                System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
            Assert.That(prop, Is.Not.Null, "未找到 BrainBase.PrefrontalCallback——内部不变量违反。");

            var value = prop.GetValue(pfc);
            Assert.That(value, Is.Null,
                "PrefrontalCortex.PrefrontalCallback 必须为 null——「主脑不回报自己」铁律。");
        }

        // ===== (6) CallableBrains 不含 PrefrontalCortex 自身 =====

        [Test]
        public void PrefrontalCortex_does_not_register_itself_in_CallableBrains()
        {
            var memory = new InMemoryFakeMemoryService();
            var chat = new FakeChatClient("ok");
            var callback = new FakePrefrontalCallback();

            // 准备一个外部「假主脑」以模拟「错误地把 Prefrontal 类型脑区放进 CallableBrains」。
            var otherPfcDesc = BuildPrefrontalDescriptor("prefrontal-cortex-other");
            var otherPfc = new PrefrontalCortex(otherPfcDesc, memory, chat, Array.Empty<BrainBase>());

            var pfcDesc = BuildPrefrontalDescriptor();

            Assert.Throws<InvalidOperationException>(() =>
                new PrefrontalCortex(pfcDesc, memory, chat, new BrainBase[] { otherPfc }),
                "CallableBrains 不允许包含 PrefrontalCortex 类型脑区——「主脑唯一」铁律。");
        }

        // ===== helpers =====

        private static StandardBrainDescriptor BuildPrefrontalDescriptor(string brainId = "prefrontal-cortex")
        {
            return new StandardBrainDescriptor(
                brainId: brainId,
                role: "prefrontal",
                soul: "主脑魂",
                kind: StandardBrainKind.PrefrontalCortex,
                capability: BuildStubCapability())
            {
                IsPrefrontal = true,
            };
        }

        private static StandardBrainDescriptor BuildStandardDescriptor(
            string brainId, string role, StandardBrainKind kind)
        {
            return new StandardBrainDescriptor(
                brainId: brainId,
                role: role,
                soul: $"{role}-魂",
                kind: kind,
                capability: BuildStubCapability());
        }

        private static AgentDescription BuildStubCapability()
        {
            return new AgentDescription(
                id: "brain-stub.test",
                name: "Test",
                soul: "stub-soul",
                identity: "stub identity");
        }

        /// <summary>
        /// 从 msai AIAgent 上抽出 ChatOptions.Tools——走 <see cref="AIAgent.GetService(System.Type, object)"/>
        /// 拿 ChatOptions（ChatClientAgent.GetService 已为 typeof(ChatOptions) 派出 _agentOptions.ChatOptions）。
        /// </summary>
        private static IList<AITool> ExtractTools(AIAgent agent)
        {
            var chatOpts = agent.GetService(typeof(ChatOptions)) as ChatOptions;
            Assert.That(chatOpts, Is.Not.Null,
                "AIAgent.GetService(typeof(ChatOptions)) 应返非 null——PrefrontalCortex 装配 Tools 时已塞入 ChatOptions。");
            return chatOpts.Tools ?? new List<AITool>();
        }

        private static IReadOnlyList<string> ExtractToolNames(AIAgent agent)
        {
            return ExtractTools(agent)
                .OfType<AIFunction>()
                .Select(f => f.Name)
                .ToList();
        }
    }
}
#endif
