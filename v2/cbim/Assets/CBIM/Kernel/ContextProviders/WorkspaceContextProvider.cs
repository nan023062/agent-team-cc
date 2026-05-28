using System;
using System.Collections.Generic;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.AI;
using CBIM.Kernel.TaskScheduler;
using CBIM.Workspace;

namespace CBIM.Kernel.ContextProviders
{
    /// <summary>
    /// Workspace 维度 ContextProvider 工厂。
    ///
    /// 数据源：构造期注入的 <see cref="Workspace"/>。
    /// For(task) 产出一个轻量子类，调用时按 task.Where 逐 Id 调
    /// Workspace.GetDescription，拼"模块定位 + Workflows 概要"片段。
    ///
    /// 本切片只做骨架字符串拼接：
    ///   - Metadata.Location 一行（Local 时为路径，Remote 时为 endpoint）
    ///   - 每个 Workflow 一行：Id + Description
    ///   - 未读 .dna/module.md 正文，也不解析 contract.md（留给后续切片）
    /// 不做 token 预算 / 截断——交给 Microsoft 合并策略。
    /// </summary>
    public sealed class WorkspaceContextProvider : IWorkspaceContextProvider
    {
        private readonly Workspace _workspace;

        public WorkspaceContextProvider(Workspace workspace)
        {
            _workspace = workspace ?? throw new ArgumentNullException(nameof(workspace));
        }

        public AIContextProvider For(CbimTask task)
        {
            if (task is null) throw new ArgumentNullException(nameof(task));
            return new Provider(_workspace, task);
        }

        private sealed class Provider : AIContextProvider
        {
            private readonly Workspace _workspace;
            private readonly CbimTask  _task;

            public Provider(Workspace workspace, CbimTask task)
            {
                _workspace = workspace;
                _task = task;
            }

            protected override ValueTask<AIContext> ProvideAIContextAsync(
                InvokingContext context, CancellationToken cancellationToken = default)
            {
                string text = BuildInstructions();
                return new ValueTask<AIContext>(new AIContext { Instructions = text });
            }

            private string BuildInstructions()
            {
                var moduleIds = _task.Where;
                if (moduleIds is null || moduleIds.Count == 0)
                {
                    return "[CBIM Workspace] 当前任务无模块上下文 (task.Where 为空)。";
                }

                var sb = new StringBuilder();
                sb.AppendLine("[CBIM Workspace] 当前任务作用域模块：");

                foreach (var id in moduleIds)
                {
                    var desc = _workspace.GetDescription(id);
                    if (desc is null)
                    {
                        sb.Append("- ").Append(id).AppendLine(" (未注册)");
                        continue;
                    }

                    sb.Append("- ").Append(desc.Id).Append(" / ").Append(desc.Name).AppendLine();
                    sb.Append("    Metadata: ").Append(desc.Metadata.Kind).Append(" @ ")
                      .AppendLine(desc.Metadata.Location);

                    if (desc.Workflows.Count > 0)
                    {
                        sb.AppendLine("    Workflows:");
                        foreach (var wf in desc.Workflows)
                        {
                            sb.Append("      - ").Append(wf.Id).Append(": ")
                              .AppendLine(wf.Description);
                        }
                    }
                }

                return sb.ToString();
            }
        }
    }
}
