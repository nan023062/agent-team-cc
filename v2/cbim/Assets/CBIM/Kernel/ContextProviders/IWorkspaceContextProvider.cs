using Microsoft.Extensions.AI;
using CBIM.Kernel.TaskScheduler;

namespace CBIM.Kernel.ContextProviders
{
    /// <summary>
    /// CBIM 上下文桥之一：把 Task.Where 中模块的业务知识（ModuleDescription.Metadata + Workflows
    /// 概要）注入到 Microsoft AIAgent 调用前的 system prompt 片段。
    ///
    /// 这是函数式工厂——For(task) 是纯函数：不同 task 各得一个独立的
    /// <see cref="AIContextProvider"/>，互不共享状态。
    /// </summary>
    public interface IWorkspaceContextProvider
    {
        /// <summary>为指定 task 构造一个 Workspace 维度的 AIContextProvider。</summary>
        AIContextProvider For(CbimTask task);
    }
}
