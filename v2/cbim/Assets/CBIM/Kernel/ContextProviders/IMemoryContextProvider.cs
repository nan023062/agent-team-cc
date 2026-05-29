using Microsoft.Extensions.AI;
using CBIM.TaskScheduler;

namespace CBIM.ContextProviders
{
    /// <summary>
    /// CBIM 上下文桥之一：以 Task.What 为 query 调 <c>IMemoryService.Query</c> 取前 K 条
    /// MemoryEntry，拼成 prompt 片段注入。
    ///
    /// 函数式工厂——For(task) 是纯函数；topK 由 <see cref="CbimContextOptions.MemoryTopK"/> 决定，
    /// 但本接口签名不透出，options 在装配门面 <see cref="CbimContextProviderFactory"/> 一层透传。
    /// </summary>
    public interface IMemoryContextProvider
    {
        /// <summary>为指定 task 构造一个 Memory 维度的 AIContextProvider。</summary>
        AIContextProvider For(CbimTask task);
    }
}
