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
using CBIM.Channel;
using CBIM.Memory;

// Alias 消歧——CBIM.AgentSystem 既是 namespace 也是 sealed class（AgentSystem 服务门面）。
// 测试文件用 `AgentSystemService` 引用类型，避免「AgentSystem.AgentSystem」重名段。
using AgentSystemService = CBIM.AgentSystem.AgentSystem;

namespace CBIM.Channel.Tests.E2E
{
    /// <summary>
    /// 端到端测试——验证完整调用链：
    ///   <c>Channel.SendAsync</c> → <c>PrefrontalCortex.Agent.RunAsync</c>
    ///   → LLM 决策 → <c>__brain_call_motor_cortex_native</c> AIFunction
    ///   → <c>NativeMotorCortex.InvokeAsync</c> → <c>BrainOutcome.Summary</c>
    ///   → 主脑汇总 → 返 <see cref="ChannelOutcome"/> → 触发 <see cref="Channel.OnOutput"/>。
    ///
    /// <para><b>测试边界</b>：</para>
    /// <list type="bullet">
    ///   <item>不启 subprocess、不调真 LLM——全部走 <see cref="ScriptedFakeChatClient"/> 脚本化响应。</item>
    ///   <item>不写真实文件——TempDir 用 <see cref="System.IO.Path.GetTempPath"/> 共享路径，<see cref="ChannelService"/> 校验通过即可（无人真正写到该目录）。</item>
    ///   <item>不依赖 task-7 同名 fake——asmdef 独立，本测试用 nested private fake 自包含。</item>
    /// </list>
    ///
    /// <para><b>覆盖两 case</b>：</para>
    /// <list type="number">
    ///   <item>Case 1：完整端到端闭环——脚本化 LLM 三轮交互（tool_call → tool_result → final_text），
    ///   断 outcome 文本 + OnOutput 事件 + Motor 路径被实际驱动。</item>
    ///   <item>Case 2：Dispose 释放序——CloseChannelAsync 后 Memory / Session 已释放、
    ///   <c>GetChannel(id)</c> 返 null。</item>
    /// </list>
    ///
    /// <para><b>关于 Motor override 的折中（架构师批注）</b>：</para>
    /// 本测试坚持走完整的 <see cref="Microsoft.Extensions.AI"/> FunctionInvokingChatClient 闭环——
    /// <see cref="ScriptedFakeChatClient"/> 顺序返 (1) FunctionCall → (2) Motor LLM 文本 → (3) 主脑 final 文本。
    /// 这是更接近真实路径的方案（架构师推荐）。如果未来 msai 版本升级导致 FIC 闭环行为变化、
    /// 本脚本化路径不稳，可回退到「子类化 <see cref="MotorCortex"/> override InvokeAsync」的折中方案
    /// （在测试中标注该折中）；当前阶段不需要。
    /// </summary>
    [TestFixture]
    public sealed class PrefrontalToMotorE2ETests
    {
        // ===== Case 1: 端到端闭环 =====

        [Test]
        public async Task E2E_user_request_triggers_motor_via_prefrontal_and_returns_summary()
        {
            // ── Arrange ───────────────────────────────────────────────────────────
            // 脚本三轮：
            //   ① Prefrontal 首轮 LLM 调用 → 返 FunctionCallContent("call-1", "__brain_call_motor_cortex_native", { intent: "create file X" })
            //   ② NativeMotorCortex 内嵌 LLM 调用 (BrainBase.InvokeAsync 默认走 Agent.RunAsync) → 返文本 "已创建文件 X"
            //      这段文本成为 BrainOutcome.Summary，回流为 BrainCallTrampoline 返给主脑 LLM 的 ToolMessage
            //   ③ Prefrontal 第二轮 LLM 调用（拿到 tool result 后续推理）→ 返最终文本 "已为你创建文件 X 并记录"
            //
            // 注意：FunctionInvokingChatClient 闭环序列正好需要 3 次 GetResponseAsync——
            // 同一 ScriptedFakeChatClient 在主脑 / 运动皮层之间复用（AgentSystem 全脑共享一份 IChatClient）。
            var chat = new ScriptedFakeChatClient();

            chat.EnqueueFunctionCall(
                callId: "call-1",
                functionName: "__brain_call_motor_cortex_native",
                arguments: new Dictionary<string, object?>
                {
                    ["intent"] = "create file X",
                    ["structured_input"] = null,
                    ["context"] = null,
                });

            chat.EnqueueText("已创建文件 X");
            chat.EnqueueText("已为你创建文件 X 并记录副作用");

            var memorySpy = new DisposalTrackingMemory(label: "memory");
            var desc = new AgentDescription(
                id: "e2e-agent",
                name: "E2E Agent",
                soul: "soul",
                identity: "identity",
                memoryFactory: _ => memorySpy);

            var system = new AgentSystemService(new[] { desc }, chat);
            var channels = new ChannelService(system);

            var channel = await channels.OpenChannelAsync(desc.Id, new ChannelOptions
            {
                WorkspaceRoot = System.IO.Path.GetTempPath(),
            });

            var outputs = new List<ChannelOutputEvent>();
            channel.OnOutput += ev => outputs.Add(ev);

            try
            {
                // ── Act ───────────────────────────────────────────────────────────
                var outcome = await channel.SendAsync("请创建文件 X");

                // ── Assert (5) outcome.IsError == false ──────────────────────────
                Assert.That(outcome, Is.Not.Null);
                Assert.That(outcome.IsError, Is.False,
                    "脚本化路径全程无异常——outcome 应成功。ErrorMessage=" + outcome.ErrorMessage);
                Assert.That(outcome.ErrorMessage, Is.Null);

                // ── Assert (6) outcome.ResultText 含期望文本 ──────────────────────
                Assert.That(outcome.ResultText, Does.Contain("文件 X"),
                    "主脑 final 文本应包含 '文件 X'——脚本化第 3 段返的 '已为你创建文件 X 并记录副作用'。");

                // ── Assert (7) __brain_call_motor_cortex_native 被装入主脑 Tools ─
                var prefrontalTools = ExtractPrefrontalTools(channel.Agent);
                Assert.That(
                    prefrontalTools.OfType<AIFunction>().Select(f => f.Name).ToList(),
                    Has.Member("__brain_call_motor_cortex_native"),
                    "主脑 ChatOptions.Tools 必须含 __brain_call_motor_cortex_native AIFunction"
                    + "——这是 PrefrontalCortex 装配子脑区调度入口的物理体现。");

                // ── Assert (8) Motor 路径被实际驱动 ──────────────────────────────
                // 验证手段：FakeChatClient 总调用次数 ≥ 3（主脑 1 + 运动皮层 1 + 主脑 2）。
                // 同时检查调用历史里出现了「单条 user 消息 = motor intent」的 Motor 路径调用。
                Assert.That(chat.CallCount, Is.GreaterThanOrEqualTo(3),
                    "FunctionInvokingChatClient 闭环至少触发 3 次 LLM 调用：主脑首轮 → 运动皮层 → 主脑收尾。"
                    + " 实际 CallCount=" + chat.CallCount);

                bool motorCallSeen = chat.CallHistory.Any(call =>
                    call.Messages.Count == 1
                    && call.Messages[0].Role == ChatRole.User
                    && (call.Messages[0].Text ?? "").Contains("create file X"));
                Assert.That(motorCallSeen, Is.True,
                    "应能在 ChatClient 调用历史中找到 Motor.InvokeAsync 触发的那次调用"
                    + "（单条 User 消息 = 主脑下发的 intent 'create file X'）。"
                    + " 实际历史长度=" + chat.CallHistory.Count);

                // 加固：最后一次主脑收尾调用应在 messages 中含 FunctionResultContent (call-1) 的 Tool 消息。
                bool toolResultSeen = chat.CallHistory.Any(call =>
                    call.Messages.Any(m =>
                        m.Role == ChatRole.Tool
                        && m.Contents.OfType<FunctionResultContent>().Any(frc => frc.CallId == "call-1")));
                Assert.That(toolResultSeen, Is.True,
                    "主脑第二轮调用应在 messages 历史中包含 FunctionResultContent(call-1)"
                    + "——证明 FIC 闭环把 motor 的 outcome.Summary 作为 tool 返回值回填给主脑。");

                // ── Assert (9) Channel.OnOutput 至少触发一次 ─────────────────────
                Assert.That(outputs.Count, Is.EqualTo(1),
                    "Channel.OnOutput 应在 SendAsync 完成时触发恰好 1 次。");
                Assert.That(outputs[0].ChannelId, Is.EqualTo(channel.ChannelId));
                Assert.That(outputs[0].Text, Does.Contain("文件 X"),
                    "OnOutput.Text 应携带主脑 final 文本。");
            }
            finally
            {
                // ── Cleanup ───────────────────────────────────────────────────────
                await channels.CloseChannelAsync(channel.ChannelId);
            }
        }

        // ===== Case 2: Dispose 释放序 =====

        [Test]
        public async Task E2E_dispose_releases_all_resources_in_correct_order()
        {
            // ── Arrange ───────────────────────────────────────────────────────────
            // 用「带 disposal log 的 Memory」+「带 disposal log 的 IChatClient」+
            // 进程内 spy IAsyncDisposable 三类资源，验证 Agent.DisposeAsync 释放顺序铁律：
            //   MotorCortex → 其他脑区 → Prefrontal → Memory → McpHandles → Session
            //
            // ChannelService 不暴露 mcpHandles 注入点（OpenChannelAsync 走 AgentSystem 默认装配），
            // 默认 BrainConfig 不含 ExternalMotorCortex，所以 mcpHandles 集合为空——
            // 本 case 仅断言 Memory 被释放 + Channel 注销，释放顺序细节由
            // CBIM.AgentSystem.Tests.AgentMultiBrainAssemblyTests 已覆盖。
            var chat = new ScriptedFakeChatClient();
            // 无脚本——本 case 不发 SendAsync，仅做 Open / Close 路径。

            var memorySpy = new DisposalTrackingMemory(label: "memory");
            var desc = new AgentDescription(
                id: "e2e-dispose",
                name: "E2E Dispose",
                soul: "soul",
                identity: "identity",
                memoryFactory: _ => memorySpy);

            var system = new AgentSystemService(new[] { desc }, chat);
            var channels = new ChannelService(system);

            var channel = await channels.OpenChannelAsync(desc.Id, new ChannelOptions
            {
                WorkspaceRoot = System.IO.Path.GetTempPath(),
            });

            // 装配完成后注册表应能查到本 channel。
            Assert.That(channels.GetChannel(channel.ChannelId), Is.SameAs(channel),
                "OpenChannelAsync 完成后 GetChannel 应返回同一实例。");
            Assert.That(memorySpy.DisposeCallCount, Is.EqualTo(0),
                "Open 阶段不应触发 Memory.DisposeAsync。");

            // ── Act ───────────────────────────────────────────────────────────────
            await channels.CloseChannelAsync(channel.ChannelId);

            // ── Assert ────────────────────────────────────────────────────────────
            // (a) 注册表清空——GetChannel 返 null、ListChannels 不含本 channel
            Assert.That(channels.GetChannel(channel.ChannelId), Is.Null,
                "CloseChannelAsync 后 GetChannel 应返回 null。");
            Assert.That(channels.ListChannels(), Does.Not.Contain(channel),
                "CloseChannelAsync 后 ListChannels 不应再含本 channel。");

            // (b) Memory 已 dispose——Agent.DisposeAsync 在「Prefrontal 之后、McpHandles 之前」释放 Memory
            Assert.That(memorySpy.DisposeCallCount, Is.GreaterThanOrEqualTo(1),
                "Close 路径必须把 Memory.DisposeAsync 调到——「Prefrontal → Memory → McpHandles」释放铁律。");

            // (c) 幂等——重复 close 不抛
            Assert.DoesNotThrowAsync(async () => await channels.CloseChannelAsync(channel.ChannelId),
                "CloseChannelAsync 应幂等：未知 channelId 静默返回。");
        }

        // ===== helpers =====

        /// <summary>
        /// 从主脑 AIAgent 上抽 ChatOptions.Tools 列表。
        /// 走 <c>AIAgent.GetService(typeof(ChatOptions))</c> —— ChatClientAgent.GetService
        /// 已为 ChatOptions 类型派出 <c>_agentOptions.ChatOptions</c>。
        /// </summary>
        private static IList<AITool> ExtractPrefrontalTools(AIAgent agent)
        {
            var chatOpts = agent.GetService(typeof(ChatOptions)) as ChatOptions;
            Assert.That(chatOpts, Is.Not.Null,
                "PrefrontalCortex.Agent.GetService(typeof(ChatOptions)) 应返非 null"
                + "——主脑构造期挂载 __brain_call_* 工具到 ChatOptions.Tools。");
            return chatOpts.Tools ?? new List<AITool>();
        }

        // ===== Local fakes (nested · 跨 asmdef 不复用 task-7 同名 fake) =====

        /// <summary>
        /// 一次 LLM 调用的快照——便于 case 1 在调用历史中检索 Motor 路径 / Tool 消息证据。
        /// </summary>
        private sealed record ChatCall(
            IReadOnlyList<ChatMessage> Messages,
            ChatOptions Options);

        /// <summary>
        /// 脚本化 <see cref="IChatClient"/>——按 enqueue 顺序返预置响应。
        /// 支持两种响应：
        /// <list type="bullet">
        ///   <item><see cref="EnqueueText"/>——返 <c>ChatMessage(Assistant, text)</c>；用于 LLM 终态产出。</item>
        ///   <item><see cref="EnqueueFunctionCall"/>——返
        ///   <c>ChatMessage(Assistant, [FunctionCallContent])</c>；用于触发
        ///   FunctionInvokingChatClient 调用挂载的 AIFunction。</item>
        /// </list>
        ///
        /// <para>记录每次调用的 (messages, options) 快照到 <see cref="CallHistory"/>，
        /// 让测试可在事后扫描 Motor 路径 / Tool 返回的物理证据。</para>
        ///
        /// <para>流式 / 队列耗尽行为：流式接口抛 <see cref="NotSupportedException"/>（本套件
        /// 不走流式）；队列耗尽时抛 <see cref="InvalidOperationException"/> 暴露脚本不足
        /// （静默退回固定文本会掩盖闭环失败）。</para>
        /// </summary>
        private sealed class ScriptedFakeChatClient : IChatClient
        {
            private readonly Queue<ChatMessage> _replies = new Queue<ChatMessage>();
            private readonly List<ChatCall> _history = new List<ChatCall>();

            public int CallCount => _history.Count;
            public IReadOnlyList<ChatCall> CallHistory => _history;

            public void EnqueueText(string text)
            {
                if (text == null) throw new ArgumentNullException(nameof(text));
                _replies.Enqueue(new ChatMessage(ChatRole.Assistant, text));
            }

            public void EnqueueFunctionCall(
                string callId,
                string functionName,
                IDictionary<string, object?> arguments)
            {
                if (string.IsNullOrWhiteSpace(callId)) throw new ArgumentException(nameof(callId));
                if (string.IsNullOrWhiteSpace(functionName)) throw new ArgumentException(nameof(functionName));
                var contents = new List<AIContent>
                {
                    new FunctionCallContent(callId, functionName, arguments),
                };
                _replies.Enqueue(new ChatMessage(ChatRole.Assistant, contents));
            }

            public Task<ChatResponse> GetResponseAsync(
                IEnumerable<ChatMessage> messages,
                ChatOptions options = null,
                CancellationToken cancellationToken = default)
            {
                var snapshot = messages?.ToList() ?? new List<ChatMessage>();
                _history.Add(new ChatCall(snapshot, options));

                if (_replies.Count == 0)
                    throw new InvalidOperationException(
                        "ScriptedFakeChatClient 脚本耗尽——已发生第 " + (_history.Count) + " 次调用但无对应响应。"
                        + " 测试脚本编排错误或 FunctionInvokingChatClient 闭环超出预期轮数。");

                var reply = _replies.Dequeue();
                return Task.FromResult(new ChatResponse(reply));
            }

            public IAsyncEnumerable<ChatResponseUpdate> GetStreamingResponseAsync(
                IEnumerable<ChatMessage> messages,
                ChatOptions options = null,
                CancellationToken cancellationToken = default)
                => throw new NotSupportedException(
                    "ScriptedFakeChatClient.GetStreamingResponseAsync 未实现——本套件假定脑区路径仅走非流式。");

            public object GetService(Type serviceType, object serviceKey = null) => null;

            public void Dispose() { /* 无资源 */ }
        }

        /// <summary>
        /// 进程内 <see cref="IMemoryService"/> 桩——只够装配链 / 释放序需要，
        /// 数据面方法返回最小实装。<see cref="DisposeCallCount"/> 供释放断言。
        /// </summary>
        private sealed class DisposalTrackingMemory : IMemoryService
        {
            private readonly Dictionary<string, MemoryEntry> _entries =
                new Dictionary<string, MemoryEntry>(StringComparer.Ordinal);
            private readonly string _label;

            public int DisposeCallCount { get; private set; }
            public string Label => _label;

            public DisposalTrackingMemory(string label)
            {
                _label = label ?? "memory";
            }

            public void Write(MemoryEntry entry)
            {
                if (entry == null) throw new ArgumentNullException(nameof(entry));
                _entries[entry.Id] = entry;
            }

            public MemoryEntry Get(string id)
                => string.IsNullOrWhiteSpace(id) ? null
                   : _entries.TryGetValue(id, out var e) ? e : null;

            public IReadOnlyList<MemoryEntry> Query(string text, int topK)
                => Array.Empty<MemoryEntry>();

            public IReadOnlyList<MemoryEntry> Scan(MemoryScanFilter filter)
                => Array.Empty<MemoryEntry>();

            public MemoryStats Stats() => new MemoryStats(_entries.Count, null, null);

            public ValueTask DisposeAsync()
            {
                DisposeCallCount++;
                return default;
            }
        }
    }
}
#endif
