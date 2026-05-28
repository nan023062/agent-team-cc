using System;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.AI;
using CBIM.Kernel.TaskScheduler;
using CBIM.Memory;

namespace CBIM.Kernel.ContextProviders
{
    /// <summary>
    /// Memory 维度 ContextProvider 工厂。
    ///
    /// 数据源：构造期注入的 <see cref="IMemoryService"/>。
    /// For(task) 产出一个轻量子类，调用时以 task.What 为 query 调
    /// IMemoryService.Query(text, topK=5)（topK 默认值；如需调参由调用方在
    /// <see cref="CbimContextOptions"/> 一层透传——本切片暂以固定默认值 5 实现，
    /// 后续切片可把 options 透到 ctor）。
    ///
    /// 拼装：每条 MemoryEntry 一行——Id + Text 截断到 200 字内（避免单条噪声打爆 prompt）。
    /// 不做向量检索、不维护游标、不持任何缓存——IMemoryService 实现内部自有策略。
    /// </summary>
    public sealed class MemoryContextProvider : IMemoryContextProvider
    {
        private const int DefaultTopK = 5;
        private const int MaxTextSnippet = 200;

        private readonly IMemoryService _memory;

        public MemoryContextProvider(IMemoryService memory)
        {
            _memory = memory ?? throw new ArgumentNullException(nameof(memory));
        }

        public AIContextProvider For(CbimTask task)
        {
            if (task is null) throw new ArgumentNullException(nameof(task));
            return new Provider(_memory, task);
        }

        private sealed class Provider : AIContextProvider
        {
            private readonly IMemoryService _memory;
            private readonly CbimTask       _task;

            public Provider(IMemoryService memory, CbimTask task)
            {
                _memory = memory;
                _task = task;
            }

            protected override ValueTask<AIContext> ProvideAIContextAsync(
                InvokingContext context, CancellationToken cancellationToken = default)
            {
                string text = BuildInstructions();
                return new ValueTask<AIContext>(new AIContext { Instructions = text });
            }

            private string BuildInstructions()
            {
                var entries = _memory.Query(_task.What, DefaultTopK);
                if (entries is null || entries.Count == 0)
                {
                    return "[CBIM Memory] 检索无命中。";
                }

                var sb = new StringBuilder();
                sb.AppendLine($"[CBIM Memory] 与本次任务相关的中期记忆 (top {entries.Count})：");
                foreach (var entry in entries)
                {
                    sb.Append("- ").Append(entry.Id).Append(": ")
                      .AppendLine(Snippet(entry.Text));
                }
                return sb.ToString();
            }

            private static string Snippet(string text)
            {
                if (string.IsNullOrEmpty(text)) return string.Empty;
                if (text.Length <= MaxTextSnippet) return text;
                return text.Substring(0, MaxTextSnippet) + "…";
            }
        }
    }
}
