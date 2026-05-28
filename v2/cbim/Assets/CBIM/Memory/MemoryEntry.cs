using System;
using System.Collections.Generic;

namespace CBIM.Memory
{
    /// <summary>
    /// 中期记忆条目——CBIM 独有的「跨会话浓缩事实」语义。
    /// distill 作业产出 / 手动写入 / 治理流程生成的事实 / 决策 / 原则 / 过程。
    ///
    /// 由 <see cref="MemoryService"/> 扁平 JSON 落到
    /// <c>persistentDataPath/.cbim/memory/medium/&lt;id&gt;.json</c>。
    /// 完全无 Task / Module / Agent 感知——这是它能跨业务跨能力的前提。
    /// </summary>
    /// <param name="Id">条目唯一 Id（调用方决定，不重复；不为空白）。</param>
    /// <param name="Source">写入来源标签。例："distill" / "manual"。</param>
    /// <param name="CreatedAt">创建时间。</param>
    /// <param name="Text">条目正文（自由文本）。</param>
    /// <param name="Tags">条目标签集（关键词 / 主题）；过滤检索用。</param>
    public sealed record MemoryEntry(
        string Id,
        string Source,
        DateTime CreatedAt,
        string Text,
        IReadOnlyList<string> Tags);
}
