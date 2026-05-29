using System;
using System.Collections.Generic;
using Microsoft.Extensions.AI;
using CBIM.TaskScheduler;

namespace CBIM.ContextProviders
{
    /// <summary>
    /// 装配门面——一调返回当前 task 应当挂的 Microsoft <see cref="AIContextProvider"/> 列表。
    ///
    /// 单一职责：按 <see cref="CbimContextOptions"/> 的三个 Include 开关筛选三个子 Provider
    /// 工厂，调它们各自的 For(task) 把具体 Provider 实例收集到一个列表。
    /// 不做任何上下文计算——计算在各 Provider 自己的 ProvideAIContextAsync 内做。
    ///
    /// 列表顺序固定：Workspace → Memory → Session。
    /// 顺序对 Microsoft 合并 Instructions 的拼接顺序有影响（按 provider 注册顺序拼），
    /// 把"业务知识 → 记忆 → 临场 Session"由远到近排列符合直觉。
    /// </summary>
    public sealed class CbimContextProviderFactory
    {
        private readonly IWorkspaceContextProvider _workspace;
        private readonly IMemoryContextProvider    _memory;
        private readonly ISessionContextProvider   _session;

        public CbimContextProviderFactory(
            IWorkspaceContextProvider workspace,
            IMemoryContextProvider    memory,
            ISessionContextProvider   session)
        {
            _workspace = workspace ?? throw new ArgumentNullException(nameof(workspace));
            _memory    = memory    ?? throw new ArgumentNullException(nameof(memory));
            _session   = session   ?? throw new ArgumentNullException(nameof(session));
        }

        /// <summary>
        /// 为 <paramref name="task"/> 装配三个 Provider（按 options 启用情况筛选）。
        /// options 为 null 时使用全默认值（三维全开）。
        /// </summary>
        public IReadOnlyList<AIContextProvider> For(CbimTask task, CbimContextOptions options = null)
        {
            if (task is null) throw new ArgumentNullException(nameof(task));
            options ??= new CbimContextOptions();

            // 三维全开是常态，预分配 3 槽足够。
            var providers = new List<AIContextProvider>(3);

            if (options.IncludeWorkspace) providers.Add(_workspace.For(task));
            if (options.IncludeMemory)    providers.Add(_memory.For(task));
            if (options.IncludeSession)   providers.Add(_session.For(task));

            return providers;
        }
    }
}
