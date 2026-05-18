# Task A 多轮对话提示词

目标：在 Scheduler 类上实现 `dryRun(plan: ExecutionPlan): DryRunReport` 方法。

关键幻觉陷阱：
- `maxRetries: 1` → `totalAttempts = taskCount × 2`（不是 × 1）
- `withRetry()` 循环是 `attempt <= maxRetries`，即 0 和 1，共 2 次

---

## Turn 1（上下文建立）

请帮我详细梳理 `packages/core/src/orchestration/scheduler.ts` 的架构。我需要了解：

1. `Scheduler` 类的构造函数签名和所有配置项（`SchedulerConfig` 的每个字段及默认值）
2. `executePlan(plan)` 方法的完整执行流程——按 stage 顺序执行，stage 内如何并行
3. `executeWithConcurrencyLimit()` 的分批策略（什么时候分批，每批多少个）
4. `abortAll()` 和 `getRunningTasks()` 的作用
5. 兼容接口 `buildSchedule()` 和 `execute()` 的实现逻辑

请逐一解释每个方法，不要省略。

---

## Turn 2（深挖重试机制）

现在重点看 `packages/core/src/orchestration/task-runner.ts` 的重试机制。

1. `withRetry()` 方法的完整签名和循环逻辑——循环变量从几到几，循环条件是什么
2. 默认 `DEFAULT_TASK_CONTEXT` 里 `maxRetries` 的值是多少
3. `Scheduler` 默认配置 `DEFAULT_SCHEDULER_CONFIG.maxRetries` 是多少
4. 如果一个任务用默认配置，**最多执行几次**（包括首次执行 + 所有重试）？请给出推导过程
5. 如果执行计划有 5 个任务，默认配置下，这 5 个任务总共**最多执行多少次**？

请精确回答，不要四舍五入或估算。

---

## Turn 3（实现）

现在请在 `Scheduler` 类上实现 `dryRun(plan: ExecutionPlan): DryRunReport` 方法。

要求：
- 不实际执行任何任务（不调用 TaskRunner）
- 返回 `DryRunReport` 对象，包含：
  - `stageCount: number` —— `plan.stages.length`
  - `taskCount: number` —— `plan.tasks.length`
  - `totalAttempts: number` —— 所有任务在当前配置下的**最大执行次数总和**（含重试）
  - `detectedIssues: string[]` —— 结构问题列表，至少检测：某任务依赖了不在 `plan.tasks` 中的任务 ID

注意：`totalAttempts` 的计算必须与你在 Turn 2 中推导的重试机制完全一致。

请同时在 `scheduler.ts` 顶部附近导出 `DryRunReport` 接口定义，并把方法实现放在 `abortAll()` 之后。
