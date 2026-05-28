using System;
using System.Collections.Generic;
using System.Linq;

namespace CBIM.Mcp
{
    /// <summary>
    /// <see cref="IMcpInstanceManager"/> 的默认实现。
    ///
    /// 实现策略（单锁 + 内存字典 + token set）：
    ///   - 一个 <c>_gate</c> 守护整个 <c>_entries</c> 字典；
    ///     与 <see cref="FileMcpStore"/> / FileSkillStore 同款风格。
    ///   - 每个 Id 对应一条 <see cref="Entry"/>：持已启动的 <see cref="IStartedMcpClient"/>
    ///     + <see cref="McpDescriptor"/> + 活跃 token 集合（HashSet&lt;McpRefToken&gt;）。
    ///   - token 由 <see cref="AllocToken"/> 在锁内分配：slot 复用 + 代次递增，
    ///     保证 ABA 安全；Release 时按 token 精确移除，HashSet.Remove 天然幂等。
    ///
    /// Request 路径：
    ///   1. 进 <c>_gate</c>。
    ///   2. 锁内 <see cref="AllocToken"/> 分配新 token。
    ///   3. 若 Id 已在字典：把 token 加入 entry.ActiveRefs，构造 handle 包同一个 client.AiFunctions，返回。
    ///   4. 否则在锁内调 <see cref="IMcpClientStarter.Start(McpDescriptor)"/>——
    ///      成功则加入字典 ActiveRefs = { token } + 构造 handle 返回；
    ///      抛异常 / 返 null 则**不**加入字典，原样上抛——
    ///      已 alloc 的 token 自然遗弃，下次同 slot 复用时 gen +1 即可，无需回滚到 _freeSlots（更简单 + ABA 安全）。
    ///
    /// Release 路径（由 handle.Dispose 通过接口路由进入）：
    ///   1. 进 <c>_gate</c>。
    ///   2. entry.ActiveRefs.Remove(token)——返 false 即重复释放 / ABA 防护命中，幂等无操作。
    ///   3. 集合空则移出字典、把 client 暂存待锁外 Dispose、把 slot 推回 <c>_freeSlots</c> 供复用。
    ///   4. 锁外 client.Dispose——避免 kill 子进程 / 关 socket 阻塞兄弟 Id。
    ///
    /// 并发安全（铁律 8）：
    ///   - 同 Id 并发 Request 被单锁串行——starter 只调一次，后续 N-1 次走 ActiveRefs.Add 分支。
    ///   - 不同 Id 也走同一个锁——简化设计，starter 在锁内调可能阻塞同期其他 Id 的请求；
    ///     基建场景下 MCP 数量为个位数 / 启动期一次性装配，可接受。
    ///
    /// 启动失败不留垃圾（铁律 9）：
    ///   starter.Start 抛异常 → 字典里没记录 → 后续同 Id Request 会再试一次。
    /// </summary>
    public sealed class McpManager : IMcpInstanceManager
    {
        private readonly IMcpClientStarter _starter;
        private readonly object _gate = new object();
        private readonly Dictionary<string, Entry> _entries =
            new Dictionary<string, Entry>(StringComparer.Ordinal);

        // Slot 分配状态——全部由 _gate 守护，禁止锁外访问。
        private int _nextNewSlot = 0;
        private readonly Stack<int> _freeSlots = new Stack<int>();
        private readonly Dictionary<int, int> _genBySlot = new Dictionary<int, int>();

        /// <summary>
        /// 构造。
        /// </summary>
        /// <param name="starter">装配侧注入的 MCP 启动器（SPI，见 <see cref="IMcpClientStarter"/>）。</param>
        public McpManager(IMcpClientStarter starter)
        {
            _starter = starter ?? throw new ArgumentNullException(nameof(starter));
        }

        /// <inheritdoc />
        public int ActiveCount
        {
            get
            {
                lock (_gate) { return _entries.Count; }
            }
        }

        /// <inheritdoc />
        public int RefCount(string mcpId)
        {
            if (string.IsNullOrEmpty(mcpId)) return 0;
            lock (_gate)
            {
                return _entries.TryGetValue(mcpId, out var entry) ? entry.ActiveRefs.Count : 0;
            }
        }

        /// <inheritdoc />
        public IReadOnlyCollection<McpRefToken> ActiveRefs(string mcpId)
        {
            if (string.IsNullOrEmpty(mcpId)) return Array.Empty<McpRefToken>();
            lock (_gate)
            {
                if (!_entries.TryGetValue(mcpId, out var entry)) return Array.Empty<McpRefToken>();
                // 快照拷贝——禁止把内部 HashSet 引用泄露给调用方。
                return entry.ActiveRefs.ToArray();
            }
        }

        /// <inheritdoc />
        public McpInstanceHandle Request(McpDescriptor descriptor)
        {
            if (descriptor == null) throw new ArgumentNullException(nameof(descriptor));

            lock (_gate)
            {
                var token = AllocToken();

                if (_entries.TryGetValue(descriptor.Id, out var existing))
                {
                    existing.ActiveRefs.Add(token);
                    return new McpInstanceHandle(
                        this,
                        descriptor.Id,
                        token,
                        existing.Descriptor,
                        existing.Client.AiFunctions);
                }

                // 首调启动——在锁内调 starter，确保并发竞况里同 Id 只启一次。
                // 启动失败则不入字典，异常原样上抛（铁律 9 优雅降级在装配侧实现）。
                // 已 alloc 的 token 自然遗弃——下次同 slot 复用时 gen +1，无需回滚 _freeSlots。
                var client = _starter.Start(descriptor);
                if (client == null)
                    throw new InvalidOperationException(
                        $"IMcpClientStarter.Start returned null for descriptor '{descriptor.Id}'");

                var entry = new Entry
                {
                    Client = client,
                    Descriptor = descriptor,
                    ActiveRefs = new HashSet<McpRefToken> { token },
                };
                _entries[descriptor.Id] = entry;
                return new McpInstanceHandle(
                    this,
                    descriptor.Id,
                    token,
                    descriptor,
                    client.AiFunctions);
            }
        }

        /// <inheritdoc />
        public void Release(string mcpId, McpRefToken token)
        {
            if (string.IsNullOrEmpty(mcpId)) return;

            IStartedMcpClient toDispose = null;

            lock (_gate)
            {
                if (!_entries.TryGetValue(mcpId, out var entry)) return;
                if (!entry.ActiveRefs.Remove(token)) return; // 天然幂等 + ABA 防护
                if (entry.ActiveRefs.Count > 0) return;

                _entries.Remove(mcpId);
                toDispose = entry.Client;
                // entry 清空——只剩这一个 token 在 ActiveRefs 里，归还其 slot 供复用即可。
                _freeSlots.Push(token.InstanceId);
            }

            // 在锁外 Dispose——client.Dispose 可能阻塞（kill 子进程 / 关 socket），
            // 不应卡住其他 Id 的 Request / Release。
            toDispose?.Dispose();
        }

        /// <summary>
        /// 在锁内分配一个新 token：优先复用 <c>_freeSlots</c>，否则从 <c>_nextNewSlot</c> 推进；
        /// 同 slot 的 gen 单调递增以提供 ABA 防护。**调用方必须已持有 <c>_gate</c>。**
        /// </summary>
        private McpRefToken AllocToken()
        {
            int slot = _freeSlots.Count > 0 ? _freeSlots.Pop() : _nextNewSlot++;
            int gen = _genBySlot.TryGetValue(slot, out var g) ? g + 1 : 0;
            _genBySlot[slot] = gen;
            return new McpRefToken(slot, gen);
        }

        private sealed class Entry
        {
            public IStartedMcpClient Client;
            public McpDescriptor Descriptor;
            public HashSet<McpRefToken> ActiveRefs = new HashSet<McpRefToken>();
        }
    }
}
