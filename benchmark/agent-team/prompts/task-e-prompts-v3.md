# Task E 提示词 v3（Scheduler 调度策略扩展）

---

## Turn 1

调度器现在所有任务共用一个全局超时时间。我需要让每个任务能单独设置自己的超时时间，任务自己的超时优先于全局配置生效。超时后任务自动失败，错误信息里要包含 "timeout"（大小写不限）。

---

## Turn 2

重试时现在没有等待间隔，我需要支持指数退避策略。调度配置增加 retryBackoff 选项（none 或 exponential）和 retryBaseDelayMs 基础延迟时间。exponential 模式下第 n 次重试等待 (2^(n-1)) × base 毫秒——也就是第1次等1倍，第2次等2倍，第3次等4倍。同时暴露一个 calcRetryDelay(attempt) 方法方便验证计算结果，首次执行（attempt=0）返回 0。

---

## Turn 3

同一批次内的任务需要按优先级顺序启动。支持 critical、high、normal、low 四档，maxConcurrency 限制下优先级高的任务先进入执行队列。不同批次之间还是严格串行，优先级不跨批次生效。
