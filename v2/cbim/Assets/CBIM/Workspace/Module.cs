using System;

namespace CBIM.Workspace
{
    /// <summary>
    /// Module 实例——一份 ModuleDescription 在某次 Task 中被激活后的运行态对象。
    ///
    /// 类比："一个办公位"：
    ///   WorkspaceRoot              = 办公位位置（哪间办公室哪张桌子）
    ///   Description.Metadata       = 工作资料 + 操作说明（贴在墙上的规章）
    ///   Description.Workflows      = 工作流程（标准作业流程清单）
    ///   Description.Tools          = 办公设备（打印机 / 扫描仪 / 专用屏）
    ///   Description.McpList        = 接入业务系统（连企业 ERP / CDN 控制台）
    ///   ActivatedByTaskId          = 这次工单是什么
    ///
    /// 与 AgentSystem.Agent（人）对偶——人 + 办公位 = 一次任务的完整场景。
    /// 区别：人是主动的（有大脑会思考），办公位是被动的（提供资源等人来用）。
    /// 所以 Module 远轻量——纯激活记录，无运行态资源、无 Dispose。
    ///
    /// 静态 vs 运行时（描述符 / 实例对偶）：
    ///   ModuleDescription = 静态类型声明（这是哪种业务办公位）
    ///   Module    = 运行时激活记录（这一次任务用到了它，办公位根路径在哪）
    ///
    /// 与 Agent 完全对偶（都有 InstanceId / Description / ActivatedByTaskId / 创建时间戳），
    /// 但 Module 远轻量——业务模块本身是"静态资产"，激活时主要是绑定路径上下文，
    /// 不像 Agent 那样需要装配 AIAgent + 启 MCP server。
    ///
    /// 生命周期：
    ///   - 由 Workspace.OpenInstance(descriptionId, workspaceRoot, taskId) 创建
    ///   - Task 期内伴随 Agent 共生
    ///   - Task 结束即销毁——不存盘（路径上下文是临时的）
    ///   - 如需持久化激活历史，写到 Agent.Session 日志即可
    /// </summary>
    public sealed class Module
    {
        /// <summary>实例唯一 ID（Guid 字符串）。</summary>
        public string InstanceId { get; }

        /// <summary>静态描述符。运行时不变。</summary>
        public ModuleDescription Description { get; }

        /// <summary>
        /// 工作区根路径（已解析的绝对路径）。
        /// 对应 task.Where 中本 module 的实例化目录——agent 操作此 module 时的沙盒根。
        ///
        /// 例：
        ///   ModuleDescription.Id = "my-game-combat"
        ///   WorkspaceRoot       = "D:/Projects/MyGame/Assets/Modules/Combat"
        /// </summary>
        public string WorkspaceRoot { get; }

        /// <summary>激活时间戳。</summary>
        public DateTimeOffset ActivatedAt { get; }

        /// <summary>触发本次激活的 Task ID。</summary>
        public string ActivatedByTaskId { get; }

        public Module(
            string instanceId,
            ModuleDescription description,
            string workspaceRoot,
            string activatedByTaskId = null)
        {
            if (string.IsNullOrWhiteSpace(instanceId))
                throw new ArgumentException("Module.InstanceId 不能为空", nameof(instanceId));
            if (description == null)
                throw new ArgumentNullException(nameof(description));
            if (string.IsNullOrWhiteSpace(workspaceRoot))
                throw new ArgumentException("Module.WorkspaceRoot 不能为空——必须传已解析的绝对路径", nameof(workspaceRoot));

            InstanceId = instanceId;
            Description = description;
            WorkspaceRoot = workspaceRoot;
            ActivatedAt = DateTimeOffset.UtcNow;
            ActivatedByTaskId = activatedByTaskId;
        }

        public override string ToString()
        {
            var idShort = InstanceId.Length > 8 ? InstanceId.Substring(0, 8) : InstanceId;
            return $"Module({idShort}.., desc={Description.Id}, root={WorkspaceRoot}, task={ActivatedByTaskId ?? "<none>"})";
        }
    }
}
