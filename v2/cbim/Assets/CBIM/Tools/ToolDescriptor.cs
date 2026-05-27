using System;

namespace CBIM.Tools
{
    /// <summary>
    /// 工具描述符（ToolDescriptor）——CBIM 三大基础能力之一（Tool / Skill / Mcp），
    /// 引用一组 CBIM 内置工具家族（如 Files / Search）。
    /// Tool 是所有能力的最小单位——Skill 和 Mcp 都基于 Tool 接口。
    ///
    /// agent 和 module 都可声明各自的 ToolDescriptor 列表：
    ///   AgentDescription.SystemTools  → 能力侧工具
    ///   ModuleDescription.Tools       → 业务侧工具
    ///
    /// 装配机制（"声明即注册即可用"）：
    ///   AgentSystem.OpenInstance 看到此声明
    ///     → StandardToolsService.CreateFamily(FamilyName, sandbox)
    ///     → 返回该家族的 AIFunction 集合（进程内 C# 方法）
    ///     → 直接挂到 ChatClientAgentOptions.ChatOptions.Tools
    ///   无 IPC、无子进程、无握手协议。装配开销 ≈ 0。
    ///
    /// 与 McpDescriptor 的本质区别：
    ///   ToolDescriptor   = 注册声明  → 进程内直接拿 AIFunction 集合
    ///   McpDescriptor = 注册声明 + 启动 MCP server 进程 + MCP 协议握手
    ///                  + 调 server 的 tools/list 发现工具 + 包装为 AIFunction
    ///
    /// 沙盒路径不存在此对象里——由 AgentSystem.OpenInstance 在装配时按 task 上下文动态生成。
    /// </summary>
    public sealed class ToolDescriptor
    {
        /// <summary>
        /// 工具家族名。必须与 StandardToolsService.ListFamilies() 返回的某项匹配。
        /// 当前可选：Files / Search（未来扩展 Web / Bash 等）。
        /// </summary>
        public string FamilyName { get; }

        /// <summary>该家族在本 agent 上下文中的用途简述。可为空（用家族默认描述）。</summary>
        public string Description { get; }

        public ToolDescriptor(string familyName, string description = null)
        {
            if (string.IsNullOrWhiteSpace(familyName))
                throw new ArgumentException("ToolDescriptor.FamilyName 不能为空", nameof(familyName));

            FamilyName = familyName;
            Description = description ?? string.Empty;
        }

        public override string ToString() => $"ToolDescriptor({FamilyName})";
    }
}
