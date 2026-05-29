using System;

namespace CBIM.AgentSystem.Kernel.Synapse.Compiler
{
    /// <summary>
    /// CallTool 节点——直接调一个 SystemTool / Mcp / Skill 工具（不走 LLM）。
    ///
    /// <para>v1 占位类型（Compiler/.dna Non-Goals）：v1 仅实装 CallBrain + Branch + Return 三节点。
    /// 本类型类型签名先到位（保证 C5 节点扩展开闭原则、保证 <see cref="CircuitNode"/> 派生家族完整），
    /// 但 <c>NeuralCircuitBuilder</c>（T9）不暴露 <c>AddCallTool</c> 入口、<c>CompilerToolFactory</c>（T10）
    /// 不挂 <c>__circuit_add_call_tool</c> AITool——LLM 在 v1 拿不到生成本节点的工具表面。</para>
    ///
    /// <para>SystemTool 落地后（C5 扩展窗口），新增切片仅加 Builder.AddCallTool + AIFunction，
    /// 不动本类型签名。</para>
    /// </summary>
    public sealed class CallToolNode : CircuitNode
    {
        /// <summary>工具名——如 <c>system.read_file</c> / <c>mcp.cbim.dna_list</c>。</summary>
        public string ToolName { get; }

        /// <summary>JSON 序列化后的参数——透传给工具调度层；空对象用 <c>"{}"</c>。</summary>
        public string ArgsJson { get; }

        public CallToolNode(string nodeId, string label, string toolName, string argsJson)
            : base(nodeId, label)
        {
            if (string.IsNullOrWhiteSpace(toolName))
                throw new ArgumentException("CallToolNode.ToolName 不能为空。", nameof(toolName));
            if (string.IsNullOrWhiteSpace(argsJson))
                throw new ArgumentException("CallToolNode.ArgsJson 不能为空（空参数请传 \"{}\"）。", nameof(argsJson));

            ToolName = toolName;
            ArgsJson = argsJson;
        }
    }
}
