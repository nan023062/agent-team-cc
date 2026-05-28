namespace CBIM.AgentSystem.Brain
{
    /// <summary>
    /// 外部 AI 引擎种类——<see cref="ExternalMotorCortexDescriptor"/> 通过本枚举声明
    /// 自己桥接的是哪种外部 agent 引擎。
    /// 本轮（v1）仅首发 <see cref="ClaudeCode"/>；其他成员预留待后续切片接入。
    /// </summary>
    public enum ExternalEngineKind
    {
        /// <summary>Anthropic Claude Code CLI（首发桥接目标）。</summary>
        ClaudeCode,

        /// <summary>Cursor IDE agent（预留）。</summary>
        Cursor,

        /// <summary>Cline VS Code 扩展（预留）。</summary>
        Cline,

        /// <summary>Aider CLI（预留）。</summary>
        Aider,

        /// <summary>OpenAI Codex CLI（预留）。</summary>
        Codex,

        /// <summary>自定义引擎（预留 · 由调用方提供 Adapter）。</summary>
        Custom
    }
}
