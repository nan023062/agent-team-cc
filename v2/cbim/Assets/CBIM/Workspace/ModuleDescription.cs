using System;
using System.Collections.Generic;
using CBIM.Mcp;
using CBIM.Skills;
using CBIM.Tools;

namespace CBIM.Workspace
{
    /// <summary>
    /// 模块描述（ModuleDescription）——CBIM 业务维度的核心对象。
    /// 一份 ModuleDescription 对应一种业务工作区类型（不是实例），声明：
    ///   - 它是什么业务（Id / Name）
    ///   - 它的业务知识在哪（Metadata）
    ///   - 它支持哪些业务流程（Workflows = SkillDescriptor 在业务语境下的别名）
    ///   - 它有哪些业务专属工具（Tools，可选）
    ///   - 它的业务操作接入点（McpList，类型与 Agent 的 McpList 同抽象）
    ///   - 它的负责人编制（Owners，可选，缺省 LLM 匹配）
    ///
    /// 与 AgentSystem.AgentDescription 完全对称：
    ///   AgentDescription（能力单位）= Soul + Skills + SystemTools + McpList
    ///   ModuleDescription（业务区）  = Metadata + Workflows + Tools + McpList + Owners
    ///
    /// 三大基础能力抽象（Tool / Skill / Mcp）跨维度共享：
    ///   - 都定义在 CBIM/Tools, CBIM/Skills, CBIM/Mcp 顶层模块
    ///   - 能力侧用：AgentDescription.SystemTools / Skills / McpList
    ///   - 业务侧用：ModuleDescription.Tools     / Workflows / McpList
    ///
    /// 关键设计原则：
    ///   1. Metadata 是纯知识载体（文档 / spec），不夹带操作协议
    ///   2. Workflow 是业务流程**语义声明**，本质就是 SkillDescriptor，业务语境下叫"工作流"
    ///   3. McpList 是业务的**操作接入点**——和 Agent.McpList 同抽象同类型
    ///   4. Tools 是业务专属的内置工具（如 CDN 业务可绑专门的 CDN AIFunction 包装）
    ///
    /// 任务装配时：
    ///   Task = Agent + ModuleList(ModuleDescription[]) + Requirement
    ///   ContextProviders 读 ModuleDescription.Metadata 注入 agent 上下文（业务知识）
    ///   AgentSystem.OpenInstance 合并：
    ///     Agent.SystemTools + Module.Tools（去重）→ ChatOptions.Tools 一部分
    ///     Agent.Skills + Module.Workflows → ContextProvider 注入
    ///     Agent.McpList + Module.McpList → McpRuntime 启动所有 server，收集工具
    ///   Kernel 根据 Workflow.Id 找对应 FlowGraph 执行
    ///
    /// CDN 业务模块示例：
    ///   new ModuleDescription(
    ///     id: "cdn-storage-prod",
    ///     name: "生产 CDN 存储",
    ///     metadata: new LocalModuleMetadata(".dna/module.md"),
    ///     workflows: [upload, download, query],
    ///     mcpList: [
    ///       new HttpMcpDescriptor("cdn-mcp", "CDN MCP", "操作 CDN",
    ///         endpoint: "https://cdn.example.com/mcp",
    ///         authToken: "...")
    ///     ],
    ///     owners: new ModuleOwners(
    ///       primary: "cdn-admin-agent",
    ///       secondary: "security-auditor"));
    /// </summary>
    public sealed class ModuleDescription
    {
        /// <summary>Module 唯一 ID。kebab-case。例："my-game-combat" / "cdn-storage-prod"。</summary>
        public string Id { get; }

        /// <summary>Module 名（人类可读）。例："战斗系统"。</summary>
        public string Name { get; }

        /// <summary>
        /// 业务知识 DNA（纯知识载体）。
        /// LocalModuleMetadata：本地 .dna/module.md 文档；
        /// RemoteModuleMetadata：远端业务文档 / spec endpoint。
        /// </summary>
        public ModuleMetadata Metadata { get; }

        /// <summary>
        /// 业务流程列表（本质是 SkillDescriptor，业务语境下叫"工作流"）。可为空。
        /// 与 AgentDescription.Skills 同抽象，体现"能力 vs 业务"对偶。
        /// </summary>
        public IReadOnlyList<SkillDescriptor> Workflows { get; }

        /// <summary>
        /// 业务专属内置工具列表。可为空。
        /// 与 AgentDescription.SystemTools 同抽象——一些业务需要专属的内置 AIFunction 家族。
        /// </summary>
        public IReadOnlyList<ToolDescriptor> Tools { get; }

        /// <summary>
        /// 业务操作接入点 MCP 列表。可为空。
        /// 类型与 AgentDescription.McpList 完全相同，体现 McpDescriptor 跨维度共享。
        /// 装配时与 Agent 的 McpList 合并去重后由 McpRuntime 启动并注入 ChatOptions.Tools。
        /// </summary>
        public IReadOnlyList<McpDescriptor> McpList { get; }

        /// <summary>
        /// 模块负责人（开发 + 审计）。可为 null——表示整个 module 未指定 owner。
        /// null 或字段缺失时，派发器走 LLM 自动匹配 + 强提示警告。
        /// 详细 fallback 规则见 ModuleOwners 类注释。
        /// </summary>
        public ModuleOwners Owners { get; }

        public ModuleDescription(
            string id,
            string name,
            ModuleMetadata metadata,
            IReadOnlyList<SkillDescriptor> workflows = null,
            IReadOnlyList<ToolDescriptor> tools = null,
            IReadOnlyList<McpDescriptor> mcpList = null,
            ModuleOwners owners = null)
        {
            if (string.IsNullOrWhiteSpace(id))
                throw new ArgumentException("ModuleDescription.Id 不能为空", nameof(id));
            if (string.IsNullOrWhiteSpace(name))
                throw new ArgumentException("ModuleDescription.Name 不能为空", nameof(name));
            if (metadata == null)
                throw new ArgumentNullException(nameof(metadata), "ModuleDescription.Metadata 不能为空——business module 必须有业务知识载体");

            Id = id;
            Name = name;
            Metadata = metadata;
            Workflows = workflows ?? Array.Empty<SkillDescriptor>();
            Tools = tools ?? Array.Empty<ToolDescriptor>();
            McpList = mcpList ?? Array.Empty<McpDescriptor>();
            Owners = owners;
        }

        public override string ToString() =>
            $"ModuleDescription({Id}, meta={Metadata.Kind}, workflows={Workflows.Count}, tools={Tools.Count}, mcp={McpList.Count}, owners={(Owners?.ToString() ?? "<unassigned>")})";
    }
}
