using System;
using System.Collections.Generic;

namespace CBIM.Mcp
{
    /// <summary>
    /// 不可变值类型 handle，由 <see cref="McpManager"/> 在 Request 路径上构造并返回。
    ///
    /// 设计要点：
    ///   - <c>readonly struct</c>：零堆分配；所有字段 readonly，构造后不可变。
    ///   - 直接持 Manager 引用 + (mcpId, token) 二元组定位归属——
    ///     Release 由 Manager 通过 HashSet.Remove 天然幂等保证。
    ///   - <see cref="AiFunctions"/> 引用与同 McpId 兄弟 handle 共享同一列表——
    ///     由 Manager 在 Request 路径上传入同一个 IStartedMcpClient 的 AiFunctions。
    ///
    /// 并发安全：字段不可变；Dispose 不持有锁，依赖 Manager.Release 的内部同步。
    /// <c>default(McpInstanceHandle).Dispose()</c> 安全 no-op。
    /// </summary>
    public readonly struct McpInstanceHandle : IDisposable
    {
        private readonly McpManager _manager;
        private readonly string _mcpId;
        private readonly McpRefToken _token;
        private readonly McpDescriptor _descriptor;
        private readonly IReadOnlyList<object> _aiFunctions;

        public string McpId => _mcpId;
        public McpRefToken Token => _token;
        public McpDescriptor Descriptor => _descriptor;
        public IReadOnlyList<object> AiFunctions => _aiFunctions;

        internal McpInstanceHandle(
            McpManager manager,
            string mcpId,
            McpRefToken token,
            McpDescriptor descriptor,
            IReadOnlyList<object> aiFunctions)
        {
            _manager = manager;
            _mcpId = mcpId;
            _token = token;
            _descriptor = descriptor;
            _aiFunctions = aiFunctions;
        }

        public void Dispose()
        {
            if (_manager == null) return; // default(struct) 安全 noop
            _manager.Release(_mcpId, _token);
        }
    }
}
