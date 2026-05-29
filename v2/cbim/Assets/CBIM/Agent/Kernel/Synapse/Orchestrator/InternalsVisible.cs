using System.Runtime.CompilerServices;

// 暴露 Orchestrator 子模块的 internal 类型 (ConditionEvaluator / BrainCallExecutor /
// BranchExecutor / ReturnExecutor / CircuitToWorkflowCompiler / NullPrefrontalCallback)
// 给同源测试 asmdef，便于直接构造 Executor 走 MAF 装配 / 求值路径单元测试。
//
// CBIM.Agent.Tests / CBIM.Agent.Brain.Tests 是同源测试程序集——本仓库内的 T15 测试切片均落于此两者。
// 生产程序集（CBIM 自身）不受影响：internal 修饰对外部程序集仍保持封闭。
[assembly: InternalsVisibleTo("CBIM.Agent.Brain.Tests")]
[assembly: InternalsVisibleTo("CBIM.Agent.Tests")]
