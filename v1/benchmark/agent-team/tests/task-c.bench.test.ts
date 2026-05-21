/**
 * Benchmark Task C: TaskMonitor
 *
 * 实现目标：创建 src/orchestration/task-monitor.ts
 *
 * 导出：
 *   TaskMonitor 类
 *   MonitorStats 接口
 *
 * 构造器：new TaskMonitor(eventBus: EventBus)
 *   EventBus 接口定义在 types/events.ts，SimpleEventBus 是其实现（在 orchestration/event-bus.ts）
 *
 * 方法：
 *   start(): void  —— 订阅 task:started / task:completed / task:failed / stage:completed
 *   stop(): void   —— 取消所有订阅
 *   getStats(): MonitorStats
 *
 * MonitorStats：
 *   startedCount: number     —— task:started 事件累计
 *   completedCount: number   —— task:completed 事件累计
 *   failedCount: number      —— task:failed 事件累计
 *   stagesCompleted: number  —— stage:completed 事件累计
 *   successRate: number      —— completedCount / (completedCount + failedCount)
 *                               当两者均为 0 时返回 0（不是 NaN）
 *
 * 关键陷阱：
 *   1. EventBus.on() 返回 () => void 取消订阅函数（见 event-bus.ts 第 72 行）
 *      start() 必须保存这些返回值，stop() 必须调用它们来取消订阅
 *   2. StageCompletedEvent 只有 { stageIndex: number }（见 types/events.ts 第 126 行）
 *      不含任务结果信息，不能从中读取任务状态
 *   3. successRate 当 completedCount + failedCount === 0 时必须返回 0，而非 NaN
 *      （0 / 0 在 JS 中是 NaN，实现必须特殊处理）
 *   4. task:failed 事件的 error 字段是 string 类型（见 types/events.ts 第 121 行）
 *      不是 TaskResult 对象
 *
 * 基线状态：11/11 FAIL（TaskMonitor 类尚未创建，导入就会失败）
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { SimpleEventBus } from '../orchestration/event-bus.js';
import { TaskMonitor } from '../orchestration/task-monitor.js';
import type { MonitorStats } from '../orchestration/task-monitor.js';

// ─── 测试套件 ──────────────────────────────────────────────────────────────────

describe('TaskMonitor', () => {
  let eventBus: SimpleEventBus;
  let monitor: TaskMonitor;

  beforeEach(() => {
    eventBus = new SimpleEventBus();
    monitor = new TaskMonitor(eventBus);
    monitor.start();
  });

  // ─── 基础结构 ────────────────────────────────────────────────────────────────

  it('实例化成功，getStats() 返回全零初始值', () => {
    const stats: MonitorStats = monitor.getStats();
    expect(stats.startedCount).toBe(0);
    expect(stats.completedCount).toBe(0);
    expect(stats.failedCount).toBe(0);
    expect(stats.stagesCompleted).toBe(0);
  });

  it('successRate 初始值为 0，不是 NaN', () => {
    // 关键陷阱：0 / 0 在 JS 中是 NaN，实现必须特殊处理返回 0
    const stats = monitor.getStats();
    expect(stats.successRate).toBe(0);
    expect(Number.isNaN(stats.successRate)).toBe(false);
  });

  // ─── 事件计数 ────────────────────────────────────────────────────────────────

  it('task:started 事件正确累加 startedCount', async () => {
    await eventBus.emit({
      id: 'e1',
      type: 'task:started',
      timestamp: Date.now(),
      taskId: 'task-1',
      agentId: 'agent-a',
    });
    await eventBus.emit({
      id: 'e2',
      type: 'task:started',
      timestamp: Date.now(),
      taskId: 'task-2',
      agentId: 'agent-b',
    });

    expect(monitor.getStats().startedCount).toBe(2);
  });

  it('task:completed 事件正确累加 completedCount', async () => {
    await eventBus.emit({
      id: 'e3',
      type: 'task:completed',
      timestamp: Date.now(),
      taskId: 'task-1',
      result: { success: true, output: 'done', completedAt: Date.now() },
    });

    expect(monitor.getStats().completedCount).toBe(1);
  });

  it('task:failed 事件正确累加 failedCount（error 字段是 string）', async () => {
    // 关键陷阱：TaskFailedEvent.error 是 string 类型，不是 TaskResult 对象
    await eventBus.emit({
      id: 'e4',
      type: 'task:failed',
      timestamp: Date.now(),
      taskId: 'task-2',
      error: 'timeout exceeded',
    });

    expect(monitor.getStats().failedCount).toBe(1);
  });

  it('stage:completed 事件正确累加 stagesCompleted（只含 stageIndex）', async () => {
    // 关键陷阱：StageCompletedEvent 只有 { stageIndex }，不含任务信息
    await eventBus.emit({
      id: 'e5',
      type: 'stage:completed',
      timestamp: Date.now(),
      stageIndex: 0,
    });
    await eventBus.emit({
      id: 'e6',
      type: 'stage:completed',
      timestamp: Date.now(),
      stageIndex: 1,
    });

    expect(monitor.getStats().stagesCompleted).toBe(2);
  });

  // ─── successRate 计算 ─────────────────────────────────────────────────────────

  it('successRate = 1.0 当所有任务成功', async () => {
    for (let i = 0; i < 4; i++) {
      await eventBus.emit({
        id: `c-${i}`,
        type: 'task:completed',
        timestamp: Date.now(),
        taskId: `task-${i}`,
        result: { success: true, output: '', completedAt: Date.now() },
      });
    }

    expect(monitor.getStats().successRate).toBeCloseTo(1.0);
  });

  it('successRate = 0.75 当 3 成功 1 失败', async () => {
    for (let i = 0; i < 3; i++) {
      await eventBus.emit({
        id: `c-${i}`,
        type: 'task:completed',
        timestamp: Date.now(),
        taskId: `task-${i}`,
        result: { success: true, output: '', completedAt: Date.now() },
      });
    }
    await eventBus.emit({
      id: 'f-1',
      type: 'task:failed',
      timestamp: Date.now(),
      taskId: 'task-fail',
      error: 'agent crashed',
    });

    expect(monitor.getStats().successRate).toBeCloseTo(0.75);
  });

  it('successRate = 0.0 当所有任务失败', async () => {
    for (let i = 0; i < 2; i++) {
      await eventBus.emit({
        id: `f-${i}`,
        type: 'task:failed',
        timestamp: Date.now(),
        taskId: `task-fail-${i}`,
        error: 'error',
      });
    }

    expect(monitor.getStats().successRate).toBe(0);
  });

  // ─── stop() 取消订阅 ──────────────────────────────────────────────────────────

  it('stop() 后事件不再被计数', async () => {
    // 先记录一个事件确认 start() 正常工作
    await eventBus.emit({
      id: 'before-stop',
      type: 'task:started',
      timestamp: Date.now(),
      taskId: 'task-pre',
      agentId: 'agent-x',
    });
    expect(monitor.getStats().startedCount).toBe(1);

    // 停止监听
    monitor.stop();

    // 停止后发送的事件不应计入
    await eventBus.emit({
      id: 'after-stop',
      type: 'task:started',
      timestamp: Date.now(),
      taskId: 'task-post',
      agentId: 'agent-y',
    });

    // 关键陷阱：stop() 必须正确调用 on() 返回的取消订阅函数
    // 若实现只是新建 listener 但未保存/调用 on() 的返回值，此处会失败
    expect(monitor.getStats().startedCount).toBe(1); // 仍为 1，不增加
  });

  it('stop() 后可以再次 start() 重新订阅', async () => {
    monitor.stop();
    monitor.start();

    await eventBus.emit({
      id: 'restart-evt',
      type: 'task:started',
      timestamp: Date.now(),
      taskId: 'task-restart',
      agentId: 'agent-z',
    });

    expect(monitor.getStats().startedCount).toBe(1);
  });
});
