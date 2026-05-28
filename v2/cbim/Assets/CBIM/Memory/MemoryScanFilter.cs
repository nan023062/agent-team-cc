using System;
using System.Collections.Generic;

namespace CBIM.Memory
{
    /// <summary>
    /// <see cref="MemoryService.Scan"/> 的过滤参数。
    /// 多字段同时给定时取交集（AND）；字段为 null 表示不约束该维度。
    /// </summary>
    /// <param name="SourceEquals">仅返回 Source 等于此值的条目。</param>
    /// <param name="TagsAny">仅返回 Tags 中至少包含其一的条目（OR 语义）；空列表与 null 等价。</param>
    /// <param name="Since">仅返回 CreatedAt &gt;= 此时间的条目。</param>
    public sealed record MemoryScanFilter(
        string SourceEquals = null,
        IReadOnlyList<string> TagsAny = null,
        DateTime? Since = null);
}
