using System;
using System.Collections.Generic;
using System.Threading.Tasks;

namespace CBIM.Memory
{
    /// <summary>
    /// CBIM Memory 基建抽象接口——中期记忆条目的最小读写契约。
    ///
    /// 实例归属：<b>per-Agent</b>——每个 Agent 实例持一个 <see cref="IMemoryService"/>；
    /// 同一 Agent 内 N 个 <c>AIAgent</c>（同质子代理）共享该实例。
    ///
    /// 调用方按接口编程、不感知后端选型：默认实现为基于本地扁平 JSON 的
    /// <c>FileMemoryBackend</c>；第三方后端（Pinecone / Weaviate / Chroma /
    /// Microsoft VectorStore 等）通过实现本接口接入，无需改 Agent 层代码。
    ///
    /// 实例隔离 ≠ 数据隔离——多个 Agent 持的 <see cref="IMemoryService"/> 实例
    /// 若指向同一后端（同一目录 / 同一 Pinecone index），即共享同一份数据。
    ///
    /// 接口为同步方法——异步调用方自行包装；接口本身不强加异步开销。
    /// <see cref="IAsyncDisposable"/> 仅为第三方实现保留异步关闭语义（如 Pinecone client 断开），
    /// 默认实现可返回空 <see cref="ValueTask"/>。
    /// </summary>
    public interface IMemoryService : IAsyncDisposable
    {
        /// <summary>
        /// 写入或覆盖一条记忆条目。同一 <see cref="MemoryEntry.Id"/> 会原子覆盖旧值。
        /// </summary>
        /// <param name="entry">条目；不为 null；<see cref="MemoryEntry.Id"/> 不为空白。</param>
        void Write(MemoryEntry entry);

        /// <summary>
        /// 按 Id 取条目。
        /// </summary>
        /// <param name="id">条目 Id。</param>
        /// <returns>命中返回条目；<b>不存在或 Id 空白时返回 <c>null</c></b>。</returns>
        MemoryEntry Get(string id);

        /// <summary>
        /// 按文本检索——返回与 <paramref name="text"/> 最相关的前 <paramref name="topK"/> 条。
        ///
        /// 检索算法由实现决定：可为关键词匹配（默认 <c>FileMemoryBackend</c>）或
        /// 向量相似度检索（Pinecone / VectorStore 等）。
        /// 接口契约仅承诺「返回 topK 相关条目」，不约束算法细节。
        /// </summary>
        /// <param name="text">查询文本；空白时返回空集合。</param>
        /// <param name="topK">返回数量上限；&lt;= 0 时返回空集合。</param>
        /// <returns>按相关度倒序的条目集合（可能少于 topK；不为 null）。</returns>
        IReadOnlyList<MemoryEntry> Query(string text, int topK);

        /// <summary>
        /// 按结构化过滤条件枚举全表——AND 各字段、按 <see cref="MemoryEntry.CreatedAt"/> 倒序。
        /// 实现按支持程度过滤；不支持的字段忽略。
        /// </summary>
        /// <param name="filter">过滤器；为 null 等价于「无过滤」即返回全部。</param>
        /// <returns>满足条件的条目集合（不为 null）。</returns>
        IReadOnlyList<MemoryEntry> Scan(MemoryScanFilter filter);

        /// <summary>
        /// 仓库实时统计快照——总条目数 + 最早 / 最新 <see cref="MemoryEntry.CreatedAt"/>。
        /// 实现可缓存以避免每次扫全表。
        /// </summary>
        MemoryStats Stats();
    }
}
