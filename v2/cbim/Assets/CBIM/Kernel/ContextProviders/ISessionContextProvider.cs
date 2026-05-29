using Microsoft.Extensions.AI;
using CBIM.TaskScheduler;

namespace CBIM.ContextProviders
{
    /// <summary>
    /// CBIM 上下文桥之一：读 Task.Who 对应 Agent 实例的 Session 末 N 条事件，拼成
    /// prompt 片段注入下一次 AIAgent 调用。
    ///
    /// 实例 ID 来源约定：AIAgent 抽象没有 CBIM Agent.InstanceId 字段，所以
    /// SessionContextProvider 从 <c>task.Params["InstanceId"]</c> 读 Guid 字符串；
    /// 缺失时 fallback 到 task.TaskId（带 TODO，便于追踪未来调用方补 InstanceId）。
    /// </summary>
    public interface ISessionContextProvider
    {
        /// <summary>为指定 task 构造一个 Session 维度的 AIContextProvider。</summary>
        AIContextProvider For(CbimTask task);
    }
}
