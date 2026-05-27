namespace CBIM.Workspace
{
    /// <summary>
    /// 模块负责人（ModuleOwners）——业务维度的人事编制。
    /// 类比真实团队工单制度：每个 module 像一个项目，有第一负责人（开发）+ 第二负责人（审计）。
    ///
    /// 设计原则：
    ///   - **可空**：整个 Owners 字段在 ModuleDescription 上是可空的；Primary/Secondary 各自也可空
    ///   - **渐进约束**：理想状态明确指定 owner，落地阶段允许"待定"逐步补齐
    ///   - **未指定 → LLM 自动匹配 + 用户强提示警告**
    ///     具体行为在派发器（dispatcher）层实现：
    ///       1. 读 task 涉及的 module
    ///       2. 检查每个 module 的 Owners
    ///       3. 缺失部分 → LLM 读所有 AgentDescription 判断最适合的 agent
    ///       4. 同时 emit 警告："Module 'xxx' 未指定负责人，本次使用 LLM 自动匹配的 'yyy'。
    ///          建议在 ModuleDescription 显式设置 Owners 以提升可预测性。"
    ///       5. 该次 task 的 Session 日志记录"auto_matched_owner=true" 供审计
    ///
    /// 字段引用：Primary / Secondary 都是 AgentDescription.Id 字符串引用，
    /// 不持 AgentDescription 实例——避免循环依赖，也允许 forward reference
    /// （引用一个尚未存在的 agent id，派发时再校验）。
    ///
    /// 派发覆盖：
    ///   task.Who 明指 agent 时优先 task.Who，owner 仅作为"默认派发对象"。
    ///   覆盖会 emit info 日志，不阻塞执行。
    /// </summary>
    public sealed class ModuleOwners
    {
        /// <summary>
        /// 第一负责人（开发负责人）。引用 AgentDescription.Id。
        /// 可为 null/空——表示开发负责人由 LLM 自动匹配（带警告）。
        /// </summary>
        public string Primary { get; }

        /// <summary>
        /// 第二负责人（审计负责人）。引用 AgentDescription.Id。
        /// 可为 null/空——表示审计负责人由 LLM 自动匹配（带警告）。
        /// 通常与 Primary 是不同类型的 agent（如 Primary=gameplay-programmer，Secondary=architect）。
        /// </summary>
        public string Secondary { get; }

        public ModuleOwners(string primary = null, string secondary = null)
        {
            // 不强制非空——允许两者都缺省（整个 ModuleOwners 等同于 null 占位）。
            // 派发器看到空字段会 fallback 到 LLM 匹配 + 警告。
            Primary = primary;
            Secondary = secondary;
        }

        /// <summary>是否显式指定了 Primary（开发负责人）。</summary>
        public bool HasPrimary => !string.IsNullOrWhiteSpace(Primary);

        /// <summary>是否显式指定了 Secondary（审计负责人）。</summary>
        public bool HasSecondary => !string.IsNullOrWhiteSpace(Secondary);

        public override string ToString() =>
            $"Owners(primary={Primary ?? "<auto>"}, secondary={Secondary ?? "<auto>"})";
    }
}
