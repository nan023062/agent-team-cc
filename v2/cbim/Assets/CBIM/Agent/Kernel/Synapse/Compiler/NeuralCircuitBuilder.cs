using System;
using System.Collections.Generic;

namespace CBIM.AgentSystem.Kernel.Synapse.Compiler
{
    /// <summary>
    /// 神经回路构建器——per-invocation 可变状态收集器，由
    /// <c>PrefrontalCortex.InvokeAsync</c>（T14）在「编译期」实例化一次、
    /// <c>CompilerToolFactory</c>（T10）封装的 <c>__circuit_add_*</c> AITool handler
    /// 闭包持本实例引用、LLM 通过工具调用反复调 <c>Add*</c> 累积节点 / 边、
    /// 最终主脑调 <see cref="Commit"/> 冻结成 <see cref="NeuralCircuit"/>。
    ///
    /// <para>设计约束：</para>
    /// <list type="bullet">
    ///   <item><b>per-invocation mutable</b>——非 fully immutable；handler 须能持本实例引用反复修改，
    ///         主脑每轮 InvokeAsync 新建一个并覆盖 <c>_activeBuilder</c> 字段。</item>
    ///   <item><b>sealed</b>——节点扩展走 C5（新增 <see cref="CircuitNode"/> 子类 + 新加
    ///         <c>Add*</c> 方法），不开继承窗口。</item>
    ///   <item><b>commit 即冻</b>——<see cref="Commit"/> 一旦成功，<see cref="Compiled"/> 被写入，
    ///         其后任何 <c>Add*</c> 调用必抛 <see cref="InvalidOperationException"/>。</item>
    ///   <item><b>StartNodeId 隐式约定</b>——第一个 <c>Add*</c> 返回的节点即入口节点；
    ///         由主脑 prompt 与 LLM 对齐（首条加 <c>add_call_brain</c> 或 <c>add_branch</c>）。</item>
    /// </list>
    ///
    /// <para>NodeId 分配：内部 <c>_nextId</c> 自 1 起，每次 <c>Add*</c> 产出 <c>n01</c> / <c>n02</c> /…
    /// （形如 <c>$"n{_nextId++:D2}"</c>，n01–n99 范围）。</para>
    ///
    /// <para>两条异常路径不混：</para>
    /// <list type="bullet">
    ///   <item><see cref="ArgumentException"/> / <see cref="InvalidOperationException"/>——
    ///         <c>Add*</c> 即时校验失败（字段空白 / 节点不存在 / BranchLabel 错配 / commit 后再修改）；
    ///         T10 的 AITool handler 转包为 ToolException 回 LLM 让其重试。</item>
    ///   <item><see cref="CircuitCompilationException"/>——<see cref="Commit"/> 整体校验失败
    ///         （≥1 ReturnNode / 连通性 / 无环 / Branch 出度）；由 T14 主脑捕获并回退。</item>
    /// </list>
    /// </summary>
    public sealed class NeuralCircuitBuilder
    {
        private readonly string _sourceRequest;
        private readonly List<CircuitNode> _nodes = new List<CircuitNode>();
        private readonly List<CircuitEdge> _edges = new List<CircuitEdge>();
        private readonly Dictionary<string, CircuitNode> _nodeIndex = new Dictionary<string, CircuitNode>(StringComparer.Ordinal);
        private int _nextId = 1;

        /// <summary>回路 Id——构造期由调用方传入（通常 <c>Guid.NewGuid().ToString()</c>）；
        /// Commit 后透传给 <see cref="NeuralCircuit.CircuitId"/>。</summary>
        public string CircuitId { get; }

        /// <summary>Commit 产物——Commit 成功后写入，未 commit / commit 失败保持 <c>null</c>。</summary>
        public NeuralCircuit? Compiled { get; private set; }

        public NeuralCircuitBuilder(string circuitId, string sourceRequest)
        {
            if (string.IsNullOrWhiteSpace(circuitId))
                throw new ArgumentException("NeuralCircuitBuilder.CircuitId 不能为空。", nameof(circuitId));
            if (string.IsNullOrWhiteSpace(sourceRequest))
                throw new ArgumentException("NeuralCircuitBuilder.SourceRequest 不能为空。", nameof(sourceRequest));

            CircuitId = circuitId;
            _sourceRequest = sourceRequest;
        }

        /// <summary>添加 CallBrain 节点——返回新节点 Id（首次调用即 StartNodeId）。</summary>
        public string AddCallBrain(string label, string targetBrainId, string intent, string? structuredInputJson)
        {
            EnsureMutable();
            // 字段非空由 CallBrainNode 构造器兜底校验，这里直接构造可获得统一异常信息。
            var nodeId = AllocateNodeId();
            var node = new CallBrainNode(nodeId, label, targetBrainId, intent, structuredInputJson);
            _nodes.Add(node);
            _nodeIndex.Add(nodeId, node);
            return nodeId;
        }

        /// <summary>添加 Branch 节点——返回新节点 Id。</summary>
        public string AddBranch(string label, string conditionExpression)
        {
            EnsureMutable();
            var nodeId = AllocateNodeId();
            var node = new BranchNode(nodeId, label, conditionExpression);
            _nodes.Add(node);
            _nodeIndex.Add(nodeId, node);
            return nodeId;
        }

        /// <summary>添加 Return 节点——返回新节点 Id。</summary>
        public string AddReturn(string label, string summaryTemplate)
        {
            EnsureMutable();
            var nodeId = AllocateNodeId();
            var node = new ReturnNode(nodeId, label, summaryTemplate);
            _nodes.Add(node);
            _nodeIndex.Add(nodeId, node);
            return nodeId;
        }

        /// <summary>添加边——即时校验：两端节点均已声明；BranchLabel 与源节点类型对齐
        /// （源 = BranchNode 必填、源 ≠ BranchNode 必为 null）。</summary>
        public void AddEdge(string fromNodeId, string toNodeId, string? branchLabel)
        {
            EnsureMutable();
            if (string.IsNullOrWhiteSpace(fromNodeId))
                throw new ArgumentException("AddEdge.FromNodeId 不能为空。", nameof(fromNodeId));
            if (string.IsNullOrWhiteSpace(toNodeId))
                throw new ArgumentException("AddEdge.ToNodeId 不能为空。", nameof(toNodeId));

            if (!_nodeIndex.TryGetValue(fromNodeId, out var fromNode))
                throw new InvalidOperationException($"AddEdge 源节点 '{fromNodeId}' 尚未声明，先调用对应 Add* 创建节点。");
            if (!_nodeIndex.ContainsKey(toNodeId))
                throw new InvalidOperationException($"AddEdge 目标节点 '{toNodeId}' 尚未声明，先调用对应 Add* 创建节点。");

            var fromIsBranch = fromNode is BranchNode;
            if (fromIsBranch && string.IsNullOrWhiteSpace(branchLabel))
                throw new InvalidOperationException(
                    $"AddEdge 源节点 '{fromNodeId}' 是 BranchNode，BranchLabel 必填。");
            if (!fromIsBranch && branchLabel != null)
                throw new InvalidOperationException(
                    $"AddEdge 源节点 '{fromNodeId}' 非 BranchNode，BranchLabel 必须为 null。");

            _edges.Add(new CircuitEdge(fromNodeId, toNodeId, branchLabel));
        }

        /// <summary>
        /// 冻结成 <see cref="NeuralCircuit"/>——按顺序执行 4 项整体校验：
        /// <list type="number">
        ///   <item>≥1 个 <see cref="ReturnNode"/>。</item>
        ///   <item>StartNodeId 出发可达每个 <see cref="ReturnNode"/>（BFS）。</item>
        ///   <item>无环（DFS white/gray/black backedge 检测）。</item>
        ///   <item>每个 <see cref="BranchNode"/> 出边数 ≥2 且每条出边 BranchLabel 非空。</item>
        /// </list>
        /// 任一项失败抛 <see cref="CircuitCompilationException"/>。成功后写入
        /// <see cref="Compiled"/> 并返回；其后 <c>Add*</c> 一律抛 <see cref="InvalidOperationException"/>。
        ///
        /// <para>StartNodeId 取第一个 <c>Add*</c> 创建的节点；空 Builder 直接抛
        /// 「图未声明任何节点」。</para>
        /// </summary>
        public NeuralCircuit Commit()
        {
            EnsureMutable();
            if (_nodes.Count == 0)
                throw new CircuitCompilationException("图未声明任何节点");

            // 1) ≥1 ReturnNode
            var returnNodes = new List<ReturnNode>();
            foreach (var node in _nodes)
            {
                if (node is ReturnNode rn) returnNodes.Add(rn);
            }
            if (returnNodes.Count == 0)
                throw new CircuitCompilationException("图未声明终止节点 ReturnNode");

            var startNodeId = _nodes[0].NodeId;
            var adjacency = BuildAdjacency();

            // 2) 连通性 BFS：StartNodeId 出发到每个 ReturnNode 必可达
            var reachable = BfsReachable(startNodeId, adjacency);
            foreach (var rn in returnNodes)
            {
                if (!reachable.Contains(rn.NodeId))
                    throw new CircuitCompilationException(
                        $"ReturnNode '{rn.NodeId}' 从 StartNode '{startNodeId}' 不可达");
            }

            // 3) 无环 DFS（white=0/gray=1/black=2）
            DetectCycle(startNodeId, adjacency);

            // 4) BranchNode 出度 ≥2 + 每条出边 BranchLabel 非空
            foreach (var node in _nodes)
            {
                if (node is BranchNode bn)
                {
                    if (!adjacency.TryGetValue(bn.NodeId, out var outs) || outs.Count < 2)
                        throw new CircuitCompilationException(
                            $"BranchNode '{bn.NodeId}' 至少需要 2 条出边");
                }
            }
            foreach (var edge in _edges)
            {
                if (_nodeIndex[edge.FromNodeId] is BranchNode && string.IsNullOrWhiteSpace(edge.BranchLabel))
                {
                    throw new CircuitCompilationException(
                        $"BranchNode '{edge.FromNodeId}' 的出边必须填 BranchLabel");
                }
            }

            var compiled = new NeuralCircuit(
                CircuitId,
                _sourceRequest,
                startNodeId,
                _nodes,
                _edges,
                DateTimeOffset.UtcNow);
            Compiled = compiled;
            return compiled;
        }

        private void EnsureMutable()
        {
            if (Compiled != null)
                throw new InvalidOperationException("Builder 已 commit，不可再修改。");
        }

        private string AllocateNodeId() => $"n{_nextId++:D2}";

        private Dictionary<string, List<string>> BuildAdjacency()
        {
            var adj = new Dictionary<string, List<string>>(StringComparer.Ordinal);
            foreach (var node in _nodes)
                adj[node.NodeId] = new List<string>();
            foreach (var edge in _edges)
                adj[edge.FromNodeId].Add(edge.ToNodeId);
            return adj;
        }

        private static HashSet<string> BfsReachable(string startNodeId, Dictionary<string, List<string>> adjacency)
        {
            var visited = new HashSet<string>(StringComparer.Ordinal) { startNodeId };
            var queue = new Queue<string>();
            queue.Enqueue(startNodeId);
            while (queue.Count > 0)
            {
                var cur = queue.Dequeue();
                if (!adjacency.TryGetValue(cur, out var outs)) continue;
                foreach (var next in outs)
                {
                    if (visited.Add(next)) queue.Enqueue(next);
                }
            }
            return visited;
        }

        private static void DetectCycle(string startNodeId, Dictionary<string, List<string>> adjacency)
        {
            // 0 = white (unvisited), 1 = gray (on stack), 2 = black (done)
            var color = new Dictionary<string, int>(StringComparer.Ordinal);
            foreach (var nodeId in adjacency.Keys)
                color[nodeId] = 0;

            // 从所有节点起跑，以覆盖入口外的孤岛子图（孤岛会被连通性检查拦截，
            // 但环检测覆盖更全更稳，避免「孤岛环」漏检）。
            foreach (var nodeId in adjacency.Keys)
            {
                if (color[nodeId] == 0)
                    DfsVisit(nodeId, adjacency, color);
            }
        }

        private static void DfsVisit(string nodeId, Dictionary<string, List<string>> adjacency, Dictionary<string, int> color)
        {
            color[nodeId] = 1;
            if (adjacency.TryGetValue(nodeId, out var outs))
            {
                foreach (var next in outs)
                {
                    if (color[next] == 1)
                        throw new CircuitCompilationException(
                            $"图存在环路，节点 '{next}' 形成回边（来自 '{nodeId}'）");
                    if (color[next] == 0)
                        DfsVisit(next, adjacency, color);
                }
            }
            color[nodeId] = 2;
        }
    }
}
