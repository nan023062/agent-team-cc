namespace CBIM.Kernel.ContextProviders
{
    /// <summary>
    /// CBIM 三大 ContextProvider 的装配开关 + 调参。
    ///
    /// 调用方按需关闭某一维（例如只需要 Memory 不需要 Workspace 时设
    /// IncludeWorkspace=false），或调整每维的取样深度（MemoryTopK / SessionTailN）。
    /// 默认值为日常稳态使用——三维全开，K=5，N=20。
    /// </summary>
    /// <param name="IncludeWorkspace">是否装配 WorkspaceContextProvider。默认 true。</param>
    /// <param name="IncludeMemory">是否装配 MemoryContextProvider。默认 true。</param>
    /// <param name="IncludeSession">是否装配 SessionContextProvider。默认 true。</param>
    /// <param name="MemoryTopK">MemoryService.Query 的 topK 参数。默认 5。</param>
    /// <param name="SessionTailN">ReadSessionTail 的 N 参数。默认 20。</param>
    public sealed record CbimContextOptions(
        bool IncludeWorkspace = true,
        bool IncludeMemory    = true,
        bool IncludeSession   = true,
        int  MemoryTopK       = 5,
        int  SessionTailN     = 20);
}
