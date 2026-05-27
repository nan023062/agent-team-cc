using System;
using System.Collections.Generic;

namespace CBIM.Workspace
{
    /// <summary>
    /// Workspace 服务（业务维度门面）——CBIM 业务侧的总入口。
    ///
    /// 类比：办公室管理员 + 工位调度。
    ///   - 静态侧：管理"公司有哪些办公位"（ModuleDescription 注册表）
    ///   - 动态侧：派工时"激活某个工位给本任务用"（OpenInstance）和"用完释放"（CloseInstance）
    ///
    /// 与 AgentSystem 完全对偶：
    ///   AgentSystem  = 管"人"   ：AgentDescription 注册 + Agent 装配/释放
    ///   Workspace    = 管"工位"：ModuleDescription 注册 + Module 激活/释放
    ///
    /// 区别在重量：
    ///   Agent  重（要装配 AIAgent + 启 MCP + 维护 Session）
    ///   Module 轻（纯激活记录 + 沙盒根路径绑定）
    /// 所以 Workspace.OpenInstance 是同步方法（无需 IO），不像 AgentSystem.OpenInstanceAsync。
    ///
    /// 职责（清晰边界）：
    ///   1. 维护 ModuleDescription 注册表（构造时注入，查找按 Id）
    ///   2. 激活 Module：绑定 workspaceRoot + 记 activatedByTaskId
    ///   3. 跟踪活动实例（ListActiveInstances）
    ///   4. 释放实例时清理本地状态（无外部资源需关）
    ///
    /// 不做的事（其他模块的责任）：
    ///   - Dna 内容读取 → 由 Kernel/ContextProviders.WorkspaceContextProvider 按需读
    ///   - Module 的 Tools/Mcp 实例化 → 由 AgentSystem.OpenInstance 在装配 Agent 时合并
    ///   - Owners 解析（开发/审计派给谁）→ 由派发器（未来 TaskRunner）按 fallback 规则处理
    /// </summary>
    public sealed class Workspace
    {
        private readonly Dictionary<string, ModuleDescription> _descriptions;
        private readonly Dictionary<string, Module> _activeInstances;
        private readonly object _instancesLock = new object();

        /// <summary>
        /// 构造 Workspace。
        /// </summary>
        /// <param name="descriptions">已知的 ModuleDescription 集合（按 Id 索引）。</param>
        public Workspace(IEnumerable<ModuleDescription> descriptions)
        {
            if (descriptions == null) throw new ArgumentNullException(nameof(descriptions));

            _descriptions = new Dictionary<string, ModuleDescription>();
            foreach (var d in descriptions)
            {
                if (_descriptions.ContainsKey(d.Id))
                    throw new ArgumentException($"ModuleDescription.Id 重复：{d.Id}", nameof(descriptions));
                _descriptions[d.Id] = d;
            }

            _activeInstances = new Dictionary<string, Module>();
        }

        // ===== 静态侧：ModuleDescription 注册表 =====

        /// <summary>列出全部已注册的 ModuleDescription。</summary>
        public IReadOnlyList<ModuleDescription> ListDescriptions()
        {
            return new List<ModuleDescription>(_descriptions.Values);
        }

        /// <summary>按 Id 找 ModuleDescription。找不到返 null。</summary>
        public ModuleDescription GetDescription(string id)
        {
            if (string.IsNullOrWhiteSpace(id)) return null;
            return _descriptions.TryGetValue(id, out var d) ? d : null;
        }

        /// <summary>判断指定 Id 的 ModuleDescription 是否已注册。</summary>
        public bool ContainsDescription(string id) =>
            !string.IsNullOrWhiteSpace(id) && _descriptions.ContainsKey(id);

        // ===== 动态侧：Module 生命周期 =====

        /// <summary>
        /// 激活一个 Module：把 ModuleDescription 绑定到具体工作区根路径。
        ///
        /// 不做任何 IO 操作——纯数据组装。
        /// 如需读 Dna 内容、扫描文件，由 ContextProvider 按需进行（不在激活时做）。
        /// </summary>
        /// <param name="descriptionId">要激活的 ModuleDescription Id。</param>
        /// <param name="workspaceRoot">本次激活的绝对工作区根路径（沙盒根）。</param>
        /// <param name="activatedByTaskId">触发本次激活的 Task Id（可空）。</param>
        public Module OpenInstance(
            string descriptionId,
            string workspaceRoot,
            string activatedByTaskId = null)
        {
            var desc = GetDescription(descriptionId);
            if (desc == null)
                throw new ArgumentException($"未找到 ModuleDescription: {descriptionId}", nameof(descriptionId));

            if (string.IsNullOrWhiteSpace(workspaceRoot))
                throw new ArgumentException("workspaceRoot 不能为空", nameof(workspaceRoot));

            var instanceId = Guid.NewGuid().ToString();
            var instance = new Module(
                instanceId: instanceId,
                description: desc,
                workspaceRoot: workspaceRoot,
                activatedByTaskId: activatedByTaskId);

            lock (_instancesLock)
            {
                _activeInstances[instanceId] = instance;
            }

            return instance;
        }

        /// <summary>
        /// 关闭一个 Module：从活动表移除。
        /// 不持外部资源，仅本地状态清理。
        /// </summary>
        public void CloseInstance(Module instance)
        {
            if (instance == null) return;
            lock (_instancesLock)
            {
                _activeInstances.Remove(instance.InstanceId);
            }
        }

        /// <summary>列出当前活动中的 Module。</summary>
        public IReadOnlyList<Module> ListActiveInstances()
        {
            lock (_instancesLock)
            {
                return new List<Module>(_activeInstances.Values);
            }
        }

        /// <summary>按 InstanceId 查活动实例。找不到返 null。</summary>
        public Module GetActiveInstance(string instanceId)
        {
            if (string.IsNullOrWhiteSpace(instanceId)) return null;
            lock (_instancesLock)
            {
                return _activeInstances.TryGetValue(instanceId, out var i) ? i : null;
            }
        }
    }
}
