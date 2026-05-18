# Task C 多轮对话提示词

目标：创建 `src/orchestration/task-monitor.ts`，实现 `TaskMonitor` 类。

关键幻觉陷阱：
- `EventBus.on()` 返回 `() => void` 取消订阅函数，`stop()` 必须调用它
- `StageCompletedEvent` 只有 `stageIndex`，不含任务结果
- `successRate` 分母为 0 时返回 0，不是 NaN
- `task:failed` 事件的 `error` 是 `string`，不是 `TaskResult`

---

## Turn 1（理解 EventBus 接口）

请详细分析 `packages/core/src/types/events.ts` 和 `packages/core/src/orchestration/event-bus.ts`：

1. `EventBus` 接口定义了哪些方法？每个方法的完整签名（参数类型、返回值类型）
2. `SimpleEventBus.on()` 方法的**返回值类型**是什么？返回值的用途是什么？
3. `SimpleEventBus.off()` 方法的作用，和 `on()` 返回值的关系
4. `emit()` 方法的行为：是同步还是异步？是否等待所有 listener 完成？
5. 如果在 `on()` 之后不调用返回的函数，会出现什么问题？（内存泄漏？监听器永远存活？）

---

## Turn 2（理解事件结构）

现在仔细分析 `packages/core/src/types/events.ts` 中的事件结构：

1. `TaskStartedEvent` 的完整字段列表（包括继承自 `BaseEvent` 的字段）
2. `TaskCompletedEvent` 的完整字段列表——`result` 字段的类型是什么？
3. `TaskFailedEvent` 的完整字段列表——`error` 字段的类型是什么（string 还是 Error 还是 TaskResult）？
4. `StageCompletedEvent` 的完整字段列表——它包含任务结果吗？包含 taskIds 吗？
5. 如果我想统计"已完成的 stage 数量"，我可以从 `StageCompletedEvent` 中直接获取已完成任务的数量吗？为什么？
6. `SystemEvent` 联合类型包含哪些事件类型？

---

## Turn 3（实现）

请创建 `packages/core/src/orchestration/task-monitor.ts`，实现以下功能：

**导出 `MonitorStats` 接口**，包含：
- `startedCount: number` —— 收到 `task:started` 事件的次数
- `completedCount: number` —— 收到 `task:completed` 事件的次数
- `failedCount: number` —— 收到 `task:failed` 事件的次数
- `stagesCompleted: number` —— 收到 `stage:completed` 事件的次数
- `successRate: number` —— `completedCount / (completedCount + failedCount)`；当两者均为 0 时返回 **0**（不是 NaN）

**导出 `TaskMonitor` 类**：
- 构造器：`constructor(eventBus: EventBus)`
- `start(): void` —— 订阅上面 4 种事件，**必须保存 `on()` 返回的取消订阅函数**
- `stop(): void` —— 调用所有取消订阅函数，停止监听
- `getStats(): MonitorStats` —— 返回当前统计数据的快照

实现注意事项：
1. `on()` 返回取消订阅函数，`start()` 中必须将其保存到实例字段
2. `stop()` 必须调用保存的取消订阅函数（不是手动调用 `off()`）
3. `stage:completed` 事件只有 `stageIndex`，不要尝试从中读取任务信息
4. `successRate` 的分母保护：`completedCount + failedCount === 0` 时返回 `0`
