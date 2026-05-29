using System;
using System.Collections.Generic;
using System.Linq;
using CBIM.AgentSystem.Brain;
using CBIM.AgentSystem.Kernel.Synapse;
using CBIM.AgentSystem.Kernel.Synapse.Compiler;
using Microsoft.Agents.AI.Workflows;

namespace CBIM.AgentSystem.Kernel.Synapse.Orchestrator
{
    /// <summary>
    /// 将 CBIM <see cref="NeuralCircuit"/> IR 翻译为 Microsoft Agents Framework
    /// <see cref="Workflow"/> 的内部静态翻译器——本子模块只做「装配」，不做「执行」。
    ///
    /// <para>O1 铁律：不重造 MAF。本类只装配 <see cref="WorkflowBuilder"/> + <see cref="Executor"/>，
    /// 把图验证 / SuperStep 调度 / Checkpoint 全部留给 MAF。</para>
    /// <para>O5 铁律：Compiler ⊥ Orchestrator。本类位于 Orchestrator 命名空间下、internal，
    /// 仅向上 <c>using</c> Compiler 的 IR 数据类型；Compiler 不感知本类存在。</para>
    /// <para>K6 铁律：本类不引 <c>SynapseToolFactory</c>、不引 <c>CompilerToolFactory</c>——
    /// 三 leaf 互不引用，只透过 IR 数据类型间接交换信息。</para>
    /// </summary>
    internal static class CircuitToWorkflowCompiler
    {
        /// <summary>
        /// 编译一个 <see cref="NeuralCircuit"/> 为 MAF <see cref="Workflow"/> 实例。
        ///
        /// <para>算法步骤：</para>
        /// <list type="number">
        ///   <item>按 <see cref="NeuralCircuit.StartNodeId"/> 装配 start executor，构造 <see cref="WorkflowBuilder"/>。</item>
        ///   <item>遍历其余节点装 executor + <see cref="WorkflowBuilder.BindExecutor"/>。</item>
        ///   <item>遍历 <see cref="NeuralCircuit.Edges"/>，<see cref="CircuitEdge.BranchLabel"/> 为 null 时走无条件
        ///     <see cref="WorkflowBuilder.AddEdge{T}(ExecutorBinding,ExecutorBinding,Func{T,bool},bool)"/>；
        ///     非 null 时附加 condition lambda <c>msg =&gt; msg.BranchLabel == edge.BranchLabel</c>，
        ///     由 MAF 路由器自动选择匹配的出边。</item>
        ///   <item>所有 <see cref="ReturnNode"/> 标记为 <see cref="WorkflowBuilder.WithOutputFrom"/>——
        ///     <see cref="ReturnExecutor"/> 内部调 <c>YieldOutputAsync</c> 后，T13 的 RunAsync 通过
        ///     <c>WorkflowOutputEvent</c> 收到最终 summary。</item>
        ///   <item>调 <see cref="WorkflowBuilder.Build"/> 让 MAF 做最终结构校验（含 orphan 检查）。</item>
        /// </list>
        ///
        /// <para>失败语义：</para>
        /// <list type="bullet">
        ///   <item><see cref="CallBrainNode.TargetBrainId"/> 不在 <paramref name="brainPalette"/> 中：
        ///     抛 <see cref="CircuitExecutionException"/>（O3 fail-fast；palette 缺失视同节点失败）。</item>
        ///   <item><see cref="CallToolNode"/> 出现：抛 <see cref="NotSupportedException"/>——v1 范围内
        ///     T11 Executor 包未实装；与 Compiler v1 Non-Goals 一致。</item>
        ///   <item>未知 <see cref="CircuitNode"/> 派生类：抛 <see cref="NotSupportedException"/>——C5 扩展开闭原则下
        ///     新增节点类型必须同时给本 switch 加一支，否则 fail-fast。</item>
        ///   <item><see cref="NeuralCircuit.StartNodeId"/> 不在 <see cref="NeuralCircuit.Nodes"/> 中：
        ///     抛 <see cref="CircuitExecutionException"/>（理论上由 <c>NeuralCircuitBuilder.Commit</c> 保证，
        ///     本层兜底）。</item>
        /// </list>
        /// </summary>
        /// <param name="circuit">编译产物——不可变 IR；本方法不做就地修改。</param>
        /// <param name="brainPalette">可调脑区集合——由调用方（T13 <c>CBIMOrchestrator.RunAsync</c>）
        ///   从 <c>AgentInstance.Brains</c> 取。所有 <see cref="CallBrainNode.TargetBrainId"/> 必须能在此找到。</param>
        /// <param name="callback">主脑回调——透传给 <see cref="BrainCallExecutor"/> 用于
        ///   <c>ReportProgress</c>；debug 路径可传 <c>NullPrefrontalCallback.Instance</c>（T13 定义）。</param>
        /// <returns>已 Build 通过 orphan 校验的 <see cref="Workflow"/> 实例，可直接交给
        ///   <c>InProcessExecution</c> 执行。</returns>
        public static Workflow Compile(
            NeuralCircuit circuit,
            IReadOnlyList<BrainBase> brainPalette,
            IPrefrontalCallback callback)
        {
            if (circuit == null)
                throw new ArgumentNullException(nameof(circuit));
            if (brainPalette == null)
                throw new ArgumentNullException(nameof(brainPalette));
            if (callback == null)
                throw new ArgumentNullException(nameof(callback));

            // 1) 定位 start node 实例——本层兜底，正常应由 Builder.Commit 保证。
            var startNode = circuit.Nodes.FirstOrDefault(n => n.NodeId == circuit.StartNodeId);
            if (startNode == null)
            {
                throw new CircuitExecutionException(
                    circuit.StartNodeId,
                    $"StartNodeId='{circuit.StartNodeId}' 不在 NeuralCircuit.Nodes 中。");
            }

            // 2) 装 start executor + 建 builder。
            var startExecutor = BuildExecutor(startNode, brainPalette, callback);
            var builder = new WorkflowBuilder(startExecutor);

            // 3) 建 nodeId → Executor 映射；start 已入。
            var executorMap = new Dictionary<string, Executor>(StringComparer.Ordinal)
            {
                [circuit.StartNodeId] = startExecutor,
            };

            foreach (var node in circuit.Nodes)
            {
                if (node.NodeId == circuit.StartNodeId)
                    continue;

                var executor = BuildExecutor(node, brainPalette, callback);
                builder.BindExecutor(executor);
                executorMap[node.NodeId] = executor;
            }

            // 4) 装配边。BranchLabel 非 null 时附 condition lambda。
            foreach (var edge in circuit.Edges)
            {
                if (!executorMap.TryGetValue(edge.FromNodeId, out var fromExecutor))
                {
                    throw new CircuitExecutionException(
                        edge.FromNodeId,
                        $"CircuitEdge.FromNodeId='{edge.FromNodeId}' 不在节点表中。");
                }
                if (!executorMap.TryGetValue(edge.ToNodeId, out var toExecutor))
                {
                    throw new CircuitExecutionException(
                        edge.ToNodeId,
                        $"CircuitEdge.ToNodeId='{edge.ToNodeId}' 不在节点表中。");
                }

                if (edge.BranchLabel == null)
                {
                    // 显式 label: null + idempotent: false 绑到 3-arg 最长重载，
                    // 否则与 (source,target,condition,idempotent) 重载二义性。
                    builder.AddEdge<CircuitMessage>(
                        fromExecutor,
                        toExecutor,
                        condition: null,
                        label: null,
                        idempotent: false);
                }
                else
                {
                    // 闭包捕获：局部变量化以免后续迭代覆盖（C# 8 foreach 已每轮新变量，仍显式做以增强可读）。
                    var expectedLabel = edge.BranchLabel;
                    builder.AddEdge<CircuitMessage>(
                        fromExecutor,
                        toExecutor,
                        condition: msg => msg != null && msg.BranchLabel == expectedLabel,
                        label: null,
                        idempotent: false);
                }
            }

            // 5) 所有 ReturnNode 标为 output executor——其 YieldOutputAsync 才会冒到 WorkflowOutputEvent。
            foreach (var node in circuit.Nodes)
            {
                if (node is ReturnNode)
                {
                    builder.WithOutputFrom(executorMap[node.NodeId]);
                }
            }

            // 6) 让 MAF 做最终结构校验（含 orphan / unbound）。
            return builder.Build(validateOrphans: true);
        }

        /// <summary>
        /// CircuitNode 派生类 → MAF Executor 装配——switch on 类型保持 C5 扩展开闭原则：
        /// 新增节点类型必须同时给本 switch 加一支，否则 fail-fast。
        /// </summary>
        private static Executor BuildExecutor(
            CircuitNode node,
            IReadOnlyList<BrainBase> brainPalette,
            IPrefrontalCallback callback)
        {
            switch (node)
            {
                case CallBrainNode callBrain:
                {
                    BrainBase? brain = null;
                    for (int i = 0; i < brainPalette.Count; i++)
                    {
                        var candidate = brainPalette[i];
                        if (candidate != null && string.Equals(candidate.BrainId, callBrain.TargetBrainId, StringComparison.Ordinal))
                        {
                            brain = candidate;
                            break;
                        }
                    }
                    if (brain == null)
                    {
                        var paletteIds = string.Join(",", brainPalette.Where(b => b != null).Select(b => b.BrainId));
                        throw new CircuitExecutionException(
                            callBrain.NodeId,
                            $"CallBrainNode.TargetBrainId='{callBrain.TargetBrainId}' 不在 BrainPalette 中 (palette: [{paletteIds}])。");
                    }
                    return new BrainCallExecutor(callBrain.NodeId, callBrain, brain, callback);
                }

                case BranchNode branch:
                    return new BranchExecutor(branch.NodeId, branch);

                case ReturnNode ret:
                    return new ReturnExecutor(ret.NodeId, ret);

                case CallToolNode _:
                    throw new NotSupportedException(
                        $"CallToolNode (NodeId='{node.NodeId}') v1 不支持执行——T11 Executor 包未实装。");

                default:
                    throw new NotSupportedException(
                        $"未知 CircuitNode 派生类型 '{node.GetType().Name}' (NodeId='{node.NodeId}')——C5 扩展开闭原则要求新增节点类型同时给 CircuitToWorkflowCompiler.BuildExecutor switch 加一支。");
            }
        }
    }
}
