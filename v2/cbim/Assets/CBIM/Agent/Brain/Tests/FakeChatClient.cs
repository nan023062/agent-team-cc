#if UNITY_INCLUDE_TESTS
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.AI;

namespace CBIM.AgentSystem.Brain.Tests
{
    /// <summary>
    /// 测试用 <see cref="IChatClient"/> 桩——返回固定文本（或队列中的下一条），
    /// 记录每次 <see cref="GetResponseAsync"/> 的入参（messages / options）以便断言。
    ///
    /// 流式接口未实现：本套件 BrainBase.InvokeAsync / Channel.SendAsync 走非流式路径；
    /// 若被流式路径触发，立即抛 <see cref="NotSupportedException"/> 暴露集成漂移。
    /// </summary>
    internal sealed class FakeChatClient : IChatClient
    {
        private readonly Queue<string> _replyQueue = new Queue<string>();
        private readonly string _defaultReply;

        public int CallCount { get; private set; }

        /// <summary>最近一次调用收到的 messages 清单（拷贝；调用方可安全枚举）。</summary>
        public IReadOnlyList<ChatMessage> LastMessages { get; private set; } = Array.Empty<ChatMessage>();

        /// <summary>最近一次调用收到的 <see cref="ChatOptions"/>（含 Tools / Instructions 等）。</summary>
        public ChatOptions LastOptions { get; private set; }

        public FakeChatClient(string defaultReply)
        {
            if (defaultReply == null) throw new ArgumentNullException(nameof(defaultReply));
            _defaultReply = defaultReply;
        }

        /// <summary>追加一条「下一次响应」——按 FIFO 取，队列空时退回 <see cref="_defaultReply"/>。</summary>
        public void EnqueueReply(string reply)
        {
            if (reply == null) throw new ArgumentNullException(nameof(reply));
            _replyQueue.Enqueue(reply);
        }

        public Task<ChatResponse> GetResponseAsync(
            IEnumerable<ChatMessage> messages,
            ChatOptions options = null,
            CancellationToken cancellationToken = default)
        {
            CallCount++;
            LastMessages = messages?.ToList() ?? new List<ChatMessage>();
            LastOptions = options;

            string text = _replyQueue.Count > 0 ? _replyQueue.Dequeue() : _defaultReply;
            var msg = new ChatMessage(ChatRole.Assistant, text);
            var resp = new ChatResponse(msg);
            return Task.FromResult(resp);
        }

        public IAsyncEnumerable<ChatResponseUpdate> GetStreamingResponseAsync(
            IEnumerable<ChatMessage> messages,
            ChatOptions options = null,
            CancellationToken cancellationToken = default)
        {
            throw new NotSupportedException(
                "FakeChatClient.GetStreamingResponseAsync 未实现——本套件假定脑区路径仅走非流式。");
        }

        public object GetService(Type serviceType, object serviceKey = null) => null;

        public void Dispose() { /* 无资源 */ }
    }
}
#endif
