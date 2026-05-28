using System;
using System.Collections.Generic;
using CBIM.Skills;
using CBIM.Mcp;
using CBIM.Tools;

namespace CBIM.AgentSystem
{
    /// <summary>
    /// Agent 描述（AgentDescription）——CBIM 能力维度的核心对象。
    /// 一份 AgentDescription 对应一种 agent 类型（不是实例），声明：
    ///   - 它是谁（Id / Name / Soul / Identity）
    ///   - 它会什么手艺（Skills）
    ///   - 它要装哪些内置工具家族（SystemTools）
    ///   - 它需要哪些 MCP 服务（McpList）
    ///
    /// 任务开始时，AgentSystem.OpenInstance 按一份 AgentDescription 装配出
    /// 一个 Microsoft.Agents.AI.AIAgent 实例：
    ///   - Soul        → ChatClientAgentOptions.Instructions（系统提示词 / 人设）
    ///   - Identity    → ChatClientAgentOptions.Description（身份描述）
    ///   - Name        → ChatClientAgentOptions.Name
    ///   - Skills      → 通过 AgentSkillsProvider 注入
    ///   - SystemTools → 通过 StandardToolsService 实例化为 AIFunction 集合
    ///   - McpList     → 由 McpAdapter 启动 server 进程后包装为 AIFunction
    ///
    /// 三类工具同维度并列：SystemTools（CBIM 内置）/ McpList（外接 MCP）/
    /// 未来的 CLI 包装（subprocess）——agent 自己挑专精所需。
    ///
    /// CBIM 设计原则：agent 保持专精。若一份 AgentDescription 的
    /// Skills / SystemTools / McpList 广度过大，触发"裂变规则"——拆为多个专精 agent。
    /// </summary>
    public sealed class AgentDescription
    {
        /// <summary>Agent 唯一 ID。kebab-case。例："unity-programmer" / "backend-programmer" / "blender-artist"。</summary>
        public string Id { get; }

        /// <summary>Agent 名（人类可读）。例："Unity 程序员"。</summary>
        public string Name { get; }

        /// <summary>
        /// 灵魂（Soul）——agent 的人格 / 行为准则 / 系统提示词。
        /// 装配时直接写入 ChatClientAgentOptions.Instructions，LLM 每次调用都看见。
        /// 这是 agent 之间最关键的差异化点。
        /// </summary>
        public string Soul { get; }

        /// <summary>
        /// 身份（Identity）——agent 的角色定位简介。
        /// 装配时写入 ChatClientAgentOptions.Description，
        /// 主要用于多 agent 协作场景下其他 agent 识别"对方是谁"。
        /// </summary>
        public string Identity { get; }

        /// <summary>技能列表。可为空（agent 只靠 Soul + 工具也能工作）。</summary>
        public IReadOnlyList<SkillDescriptor> Skills { get; }

        /// <summary>系统工具家族列表（CBIM 内置）。可为空。例：[Files, Search]。</summary>
        public IReadOnlyList<ToolDescriptor> SystemTools { get; }

        /// <summary>MCP 服务列表。可为空（agent 不一定需要外接 MCP）。</summary>
        public IReadOnlyList<McpDescriptor> McpList { get; }

        public AgentDescription(
            string id,
            string name,
            string soul,
            string identity,
            IReadOnlyList<SkillDescriptor> skills = null,
            IReadOnlyList<ToolDescriptor> systemTools = null,
            IReadOnlyList<McpDescriptor> mcpList = null)
        {
            if (string.IsNullOrWhiteSpace(id))
                throw new ArgumentException("AgentDescription.Id 不能为空", nameof(id));
            if (string.IsNullOrWhiteSpace(name))
                throw new ArgumentException("AgentDescription.Name 不能为空", nameof(name));
            if (string.IsNullOrWhiteSpace(soul))
                throw new ArgumentException("AgentDescription.Soul 不能为空——agent 必须有人设", nameof(soul));
            if (string.IsNullOrWhiteSpace(identity))
                throw new ArgumentException("AgentDescription.Identity 不能为空", nameof(identity));

            Id = id;
            Name = name;
            Soul = soul;
            Identity = identity;
            Skills = skills ?? Array.Empty<SkillDescriptor>();
            SystemTools = systemTools ?? Array.Empty<ToolDescriptor>();
            McpList = mcpList ?? Array.Empty<McpDescriptor>();
        }

        public override string ToString() =>
            $"AgentDescription({Id}, skills={Skills.Count}, sysTools={SystemTools.Count}, mcp={McpList.Count})";
    }
}
