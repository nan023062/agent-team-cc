using System.Collections.Generic;

namespace CBIM.Mcp
{
    /// <summary>
    /// MCP 服务描述符的配置仓储抽象。
    ///
    /// McpDescriptor 是「配置类资产」——描述外部 MCP server 接入点的形态
    /// （stdio 命令 / http endpoint）。可被作者本地维护，也可统一在云端集中
    /// 管理后下发各 Agent / Module 装配侧。本接口屏蔽后端差异，让能力侧
    /// （Agent.McpList）与业务侧（Module.McpList）共用同一查询面。
    ///
    /// 设计要点：
    ///   - 同步方法——本模块不引入 Task / async（与 CBIM.Storage / ISkillStore 一致）。
    ///     云后端如需异步，由装配侧自己包装。
    ///   - 描述符不可变——<see cref="Put"/> 替换整条记录，不支持 in-place 字段更新。
    ///   - <see cref="Query"/> 是可选能力——本地后端做最简子串匹配；
    ///     接 Pinecone / Weaviate 时再做向量检索。
    ///   - 多态——返回类型为基类 <see cref="McpDescriptor"/>，调用方按 is 模式
    ///     匹配分派到 <see cref="StdioMcpDescriptor"/> / <see cref="HttpMcpDescriptor"/>。
    ///
    /// 与 ISkillStore 形态对称但故意不抽通用 Store&lt;T&gt;——
    /// 后续进化方向（Mcp 加「模板变量」 / Skills 加「Content 全文检索」）可能发散，
    /// 强行同名会反耦合。同形状不同语义是抽象复用的边界。
    ///
    /// 与 IMcpInstanceManager 职责分离（详见模块铁律 12）——
    /// Store 仅管描述符的增删查（纯配置），不启进程；Manager 仅管运行期实例。
    /// </summary>
    public interface IMcpStore
    {
        /// <summary>按 Id 取一条 MCP 描述符。找不到返回 null。</summary>
        McpDescriptor Get(string id);

        /// <summary>当前后端全量快照。</summary>
        IReadOnlyList<McpDescriptor> List();

        /// <summary>
        /// 简单文本检索——后端可选实现，默认最多返回 <paramref name="topK"/> 条。
        /// 本地后端做忽略大小写的子串匹配；空查询 / 非正 topK 返回空集合。
        /// </summary>
        IReadOnlyList<McpDescriptor> Query(string text, int topK);

        /// <summary>按 Id upsert——存在则替换整条记录，不存在则新增。</summary>
        void Put(McpDescriptor descriptor);

        /// <summary>按 Id 删除一条记录。不存在返回 false。</summary>
        bool Delete(string id);
    }
}
