using System.Collections.Generic;

namespace CBIM.AgentSystem
{
    /// <summary>
    /// Session 写侧接口——FlowGraph 的 CbimTaskExecutor 依赖此接口写日志。
    ///
    /// C3 铁律：稳定方持有接口定义权——AgentSystem 是能力维度服务层（更稳定），
    /// FlowGraph 是业务层（更易变），所以接口归属在此模块。
    ///
    /// 唯一实现：CBIM.AgentSystem.AgentSystem（本模块）。
    /// 唯一写入调用方：CbimTaskExecutor（FlowGraph）。
    /// 唯一读出调用方：ContextProviders.SessionContextProvider（Kernel）。
    /// </summary>
    public interface IAgentSystemSessionWriter
    {
        /// <summary>
        /// 追加一条 Session 事件。
        ///
        /// 同步落盘（jsonl 一行一条）——保证写后立刻可读。
        /// 失败抛异常，调用方决定降级策略（CbimTaskExecutor 当前选 swallow + log）。
        /// </summary>
        /// <param name="instanceId">Agent 实例 ID（来自 AgentSystem.OpenInstanceAsync 返回的 Agent.InstanceId）。</param>
        /// <param name="ev">事件对象（UserInput / LlmCall / ToolInvocation / Output / Error 五选一）。</param>
        void AppendSessionEvent(string instanceId, SessionEvent ev);

        /// <summary>
        /// 读 jsonl 末 N 行，反序列化为 SessionEvent 列表。
        /// 顺序：旧→新（与文件中物理顺序一致）。
        ///
        /// 若 instanceId 对应文件不存在 → 返空列表（视为"该实例尚无事件"，不报错）。
        /// 解析失败的行直接跳过（不让一行损坏拖垮整次读取）。
        /// </summary>
        /// <param name="instanceId">Agent 实例 ID。</param>
        /// <param name="n">取末 N 条。&lt;=0 时返空列表。</param>
        IReadOnlyList<SessionEvent> ReadSessionTail(string instanceId, int n);
    }
}
