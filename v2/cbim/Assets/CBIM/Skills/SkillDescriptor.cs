using System;

namespace CBIM.Skills
{
    /// <summary>
    /// 技能（Skill）——能力维度的扩展抽象之一。
    /// 一个 agent 的 skills 列表声明它会哪些手艺（语义级声明，不挂工具）。
    /// 装配 AIAgent 时通过 AgentSkillsProvider 注入到 Microsoft.Agents.AI 框架。
    ///
    /// 在 CBIM 能力维度三大扩展抽象中的位置（平级）：
    ///   Skill        ← 这里（语义技能，可带 SKILL.md 内容）
    ///   ToolDescriptor   ← Tools/Standard/（内置 AIFunction 家族引用）
    ///   McpDescriptor ← Mcp/（外接 MCP server 描述符）
    ///
    /// 三者都给 agent 扩展用，归属同维度同层级，仅形态不同。
    /// </summary>
    public sealed class SkillDescriptor
    {
        /// <summary>技能唯一 ID。kebab-case，全局唯一。</summary>
        public string Id { get; }

        /// <summary>技能名（人类可读）。</summary>
        public string Name { get; }

        /// <summary>一句话描述：这个技能做什么。LLM 看到此描述判断何时调用。</summary>
        public string Description { get; }

        /// <summary>技能正文（SKILL.md 风格内容，含使用指引 / 示例 / 注意事项）。可为空。</summary>
        public string Content { get; }

        public SkillDescriptor(string id, string name, string description, string content = null)
        {
            if (string.IsNullOrWhiteSpace(id))
                throw new ArgumentException("Skill.Id 不能为空", nameof(id));
            if (string.IsNullOrWhiteSpace(name))
                throw new ArgumentException("Skill.Name 不能为空", nameof(name));
            if (string.IsNullOrWhiteSpace(description))
                throw new ArgumentException("Skill.Description 不能为空", nameof(description));

            Id = id;
            Name = name;
            Description = description;
            Content = content ?? string.Empty;
        }

        public override string ToString() => $"SkillDescriptor({Id})";
    }
}
