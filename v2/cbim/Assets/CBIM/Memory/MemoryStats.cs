using System;

namespace CBIM.Memory
{
    /// <summary>
    /// Memory 仓库的轻量统计快照——本轮裁剪后只暴露三个指标：
    /// 总条目数 + 最早 / 最新条目创建时间。
    /// 仓库为空时 Oldest/Newest 为 null。
    /// </summary>
    public sealed record MemoryStats(
        int TotalEntries,
        DateTime? OldestCreatedAt,
        DateTime? NewestCreatedAt);
}
