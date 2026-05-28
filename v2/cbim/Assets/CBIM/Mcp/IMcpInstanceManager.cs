using System.Collections.Generic;

namespace CBIM.Mcp
{
    /// <summary>
    /// MCP 运行期实例管理器——跨装配侧按 token set 同 Id MCP server，
    /// 零引用时关进程 / 连接。
    ///
    /// 为什么需要这个抽象（驱动原因）：
    ///   - 同一个 MCP server（例 git-mcp）可能被多个 Agent / Module 同时使用——
    ///     能力侧装配 Agent A 启一次、Agent B 又启一次是资源浪费；
    ///     业务侧两个 Module 包同 Id MCP 同时进入 task 上下文同理。
    ///   - 唯一能维护 token set 的点是跨 Agent / 跨 Module 的全局唯一所有者——
    ///     该职责落在本模块。
    ///
    /// 全局单例（铁律 7）：
    ///   一个 CBIM 进程内 IMcpInstanceManager 需为单例（由组合根提供）；
    ///   否则多实例不能跨使用方共享 token set。本模块不强制单例实现 / 不提供 static 入口——
    ///   约束靠装配时纪律。
    ///
    /// 并发安全（铁律 8）：
    ///   <see cref="Request(McpDescriptor)"/> / <see cref="Release(string, McpRefToken)"/> 可多线程调用；
    ///   实现需按 Id 锁，同 Id 启动竞况里 Manager 负责合并 Request——
    ///   不启两个同名 server。
    ///
    /// 与 <see cref="IMcpStore"/> 职责分离（铁律 12）：
    ///   Store 仅管描述符的增删查（纯配置），不启进程；
    ///   Manager 仅管运行期实例（进程 / 连接 + token set），不持久化描述符。
    ///   调用方负责从 Store 拉描述符后交给 Manager Request。
    /// </summary>
    public interface IMcpInstanceManager
    {
        /// <summary>
        /// 申请一个 MCP 实例。
        ///   - 首次按 Id 申请：调用注入的 <see cref="IMcpClientStarter.Start(McpDescriptor)"/>
        ///     启动 + 握手 + tools/list，登记进字典，token set = { 新分配的 McpRefToken token }。
        ///   - 同 Id 后续申请：返回新 handle 包同一个底层 client，token set 加入新 McpRefToken token。
        ///
        /// 启动失败（starter 抛异常）原样上抛——不在字典残留任何条目。
        /// 装配侧应当捕获并转 warning 实现优雅降级（铁律 9）。
        /// </summary>
        McpInstanceHandle Request(McpDescriptor descriptor);

        /// <summary>
        /// 释放一个 token。handle 是 struct，其 Dispose 必须经此方法路由——
        /// 故 Release 必须在接口上，否则 handle 的 _manager 字段只能持具体类，
        /// 导致 IMcpInstanceManager 实现不可替换。
        ///
        /// 行为：
        ///   - mcpId 已知且 token 在其 token set 中：移除该 token。set 空则关进程 / 连接、移除字典条目。
        ///   - mcpId 未知 / token 不在 set 中：幂等无操作（不抛）。
        /// </summary>
        void Release(string mcpId, McpRefToken token);

        /// <summary>
        /// 某个 Id 当前活跃 token 的不可变快照（拷贝）。
        /// mcpId 未知 / 已被全部 Release 归零移除时返回空集合。
        /// 主要供诊断 / 测试使用。
        /// </summary>
        IReadOnlyCollection<McpRefToken> ActiveRefs(string mcpId);

        /// <summary>
        /// 当前被持有的不同 Id 实例数量（即字典里有几个独立的 MCP server 活着）。
        /// 主要供诊断 / 测试 / Dashboard 使用，非业务热路径。
        /// </summary>
        int ActiveCount { get; }

        /// <summary>
        /// 某个 Id 当前 token set 的大小（便捷视图，等价于 ActiveRefs(mcpId).Count）。
        /// 未启动 / 已被全部 Release 归零移除的 Id 返回 0。
        /// </summary>
        int RefCount(string mcpId);
    }
}
