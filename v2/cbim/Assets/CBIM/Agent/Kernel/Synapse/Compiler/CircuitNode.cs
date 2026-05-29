using System;

namespace CBIM.AgentSystem.Kernel.Synapse.Compiler
{
    /// <summary>
    /// 回路节点抽象基类——所有具体节点（<see cref="CallBrainNode"/> / <see cref="BranchNode"/> /
    /// <see cref="ReturnNode"/> / <see cref="CallToolNode"/>）的根。
    ///
    /// <para>C5 铁律：节点类型扩展走开闭原则——新增节点类型只增 <see cref="CircuitNode"/> 子类 +
    /// 增 <c>__circuit_add_xxx</c> AITool；<see cref="NeuralCircuit"/> / Builder / Orchestrator
    /// 主路径不改。基类持有所有节点共享的两个字段（<see cref="NodeId"/> + <see cref="Label"/>），
    /// 子类只补充自身语义字段。</para>
    /// </summary>
    public abstract class CircuitNode
    {
        /// <summary>节点 Id——Builder 编译期按 <c>n01</c> / <c>n02</c> 顺序分配；本构造器只校验非空。</summary>
        public string NodeId { get; }

        /// <summary>人类可读简述——出现在审计 / 可视化 / LLM 自我描述。</summary>
        public string Label { get; }

        protected CircuitNode(string nodeId, string label)
        {
            if (string.IsNullOrWhiteSpace(nodeId))
                throw new ArgumentException("CircuitNode.NodeId 不能为空。", nameof(nodeId));
            if (string.IsNullOrWhiteSpace(label))
                throw new ArgumentException("CircuitNode.Label 不能为空。", nameof(label));

            NodeId = nodeId;
            Label = label;
        }
    }
}
