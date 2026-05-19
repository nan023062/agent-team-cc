# Task F 提示词 v3（Agent 资源管控）

---

## Turn 1

我需要对每个 agent 的并发任务数做限制。新建一个资源管控类，提供 setAgentLimits 方法设置单个 agent 允许的最大并发任务数，提供 call 方法执行具体操作——超出并发限制时自动排队，不丢弃，等前面的任务完成后依次执行。

---

## Turn 2

在并发限制的基础上，再加速率限制：每个 agent 每秒最多调用几次。通过 setAgentLimits 设置 rateLimitPerSecond，超出速率的调用自动延迟到下一个时间窗口执行，不丢弃。

---

## Turn 3

需要能查看每个 agent 的使用统计。getStats 传入 agentId 返回该 agent 的统计数据，不传参数返回所有 agent 的统计汇总。统计字段包括：总调用次数（totalCalls）、当前活跃任务数（activeTasks）、历史峰值并发数（peakConcurrency）。
