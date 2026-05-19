/**
 * Benchmark Task D: EventBus 增强
 *
 * 实现目标：扩展 SimpleEventBus（orchestration/event-bus.ts）三项新能力
 *
 * ─── Turn 1: 监听器优先级 ────────────────────────────────────────────────────────
 * on() 支持第三个可选参数 { priority?: 'high' | 'normal' | 'low' }
 * emit 时按优先级顺序调用监听器（high → normal → low）
 * 同级优先级按注册顺序执行；不指定时默认为 'normal'
 *
 * ─── Turn 2: 事件历史记录 ────────────────────────────────────────────────────────
 * 新增 getHistory(type?: string, limit?: number): SystemEvent[] 方法
 * emit 的每个事件自动写入内部缓冲区（上限 50 条）
 * 支持按类型过滤；limit 返回最新的 N 条；新实例返回空数组
 *
 * ─── Turn 3: 通配符订阅 ──────────────────────────────────────────────────────────
 * on('task:*', listener) 接收所有以 'task:' 开头的事件
 * 精确订阅与通配符订阅可以共存，同一事件两者都收到
 * on() 返回的 unsubscribe 函数对通配符订阅同样有效
 *
 * 关键陷阱：
 *   1. 优先级排序在每次 emit 时生效，高优先级监听器先被调用/等待
 *   2. 历史缓冲区有上限，getHistory(undefined, limit) 返回最新的 N 条
 *   3. 通配符只匹配"命名空间前缀"：'task:*' 不匹配 'stage:completed'
 *
 * 基线状态：15/15 FAIL（相关方法/功能尚未实现）
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { SimpleEventBus } from '../orchestration/event-bus.js';
import type { SystemEvent, TaskStartedEvent, TaskCompletedEvent, TaskFailedEvent } from '../types/events.js';

// ─── 工具函数 ─────────────────────────────────────────────────────────────────

function makeStarted(taskId = 't1'): TaskStartedEvent {
  return { id: `e-s-${taskId}`, type: 'task:started', timestamp: Date.now(), taskId, agentId: 'agent-1' };
}

function makeCompleted(taskId = 't1'): TaskCompletedEvent {
  return { id: `e-c-${taskId}`, type: 'task:completed', timestamp: Date.now(), taskId, result: { success: true, output: '' } };
}

function makeFailed(taskId = 't1'): TaskFailedEvent {
  return { id: `e-f-${taskId}`, type: 'task:failed', timestamp: Date.now(), taskId, error: 'boom' };
}

// ─── Turn 1: 监听器优先级 ─────────────────────────────────────────────────────

describe('EventBus — 监听器优先级', () => {
  let bus: SimpleEventBus;
  beforeEach(() => { bus = new SimpleEventBus(); });

  it('high 优先级监听器先于 normal 执行', async () => {
    const order: string[] = [];
    bus.on('task:started', () => { order.push('normal'); });
    bus.on('task:started', () => { order.push('high'); }, { priority: 'high' });
    await bus.emit(makeStarted());
    expect(order[0]).toBe('high');
    expect(order[1]).toBe('normal');
  });

  it('normal 优先级监听器先于 low 执行', async () => {
    const order: string[] = [];
    bus.on('task:started', () => { order.push('low'); }, { priority: 'low' });
    bus.on('task:started', () => { order.push('normal'); });
    await bus.emit(makeStarted());
    expect(order[0]).toBe('normal');
    expect(order[1]).toBe('low');
  });

  it('三级优先级顺序：high → normal → low', async () => {
    const order: string[] = [];
    bus.on('task:started', () => { order.push('low'); }, { priority: 'low' });
    bus.on('task:started', () => { order.push('normal'); });
    bus.on('task:started', () => { order.push('high'); }, { priority: 'high' });
    await bus.emit(makeStarted());
    expect(order).toEqual(['high', 'normal', 'low']);
  });

  it('相同优先级按注册顺序执行', async () => {
    const order: string[] = [];
    bus.on('task:started', () => { order.push('first'); });
    bus.on('task:started', () => { order.push('second'); });
    await bus.emit(makeStarted());
    expect(order).toEqual(['first', 'second']);
  });

  it('不指定 priority 默认为 normal，高于 low 低于 high', async () => {
    const order: string[] = [];
    bus.on('task:started', () => { order.push('low'); }, { priority: 'low' });
    bus.on('task:started', () => { order.push('default'); });
    bus.on('task:started', () => { order.push('high'); }, { priority: 'high' });
    await bus.emit(makeStarted());
    expect(order).toEqual(['high', 'default', 'low']);
  });
});

// ─── Turn 2: 事件历史记录 ─────────────────────────────────────────────────────

describe('EventBus — 事件历史记录', () => {
  let bus: SimpleEventBus;
  beforeEach(() => { bus = new SimpleEventBus(); });

  it('新实例 getHistory() 返回空数组', () => {
    expect(bus.getHistory()).toEqual([]);
  });

  it('getHistory() 返回所有已发送事件，按时间顺序排列', async () => {
    await bus.emit(makeStarted('t1'));
    await bus.emit(makeCompleted('t2'));
    const h = bus.getHistory();
    expect(h.length).toBe(2);
    expect(h[0].type).toBe('task:started');
    expect(h[1].type).toBe('task:completed');
  });

  it('getHistory(type) 按事件类型过滤，只返回匹配的事件', async () => {
    await bus.emit(makeStarted('t1'));
    await bus.emit(makeCompleted('t2'));
    await bus.emit(makeFailed('t3'));
    const started = bus.getHistory('task:started');
    expect(started.length).toBe(1);
    expect(started[0].type).toBe('task:started');
  });

  it('getHistory(undefined, limit) 最多返回最新的 N 条', async () => {
    for (let i = 0; i < 5; i++) await bus.emit(makeStarted(`t${i}`));
    const h = bus.getHistory(undefined, 3);
    expect(h.length).toBe(3);
  });

  it('getHistory(type, limit) 支持类型过滤与数量限制组合', async () => {
    for (let i = 0; i < 3; i++) await bus.emit(makeStarted(`t${i}`));
    await bus.emit(makeCompleted('tx'));
    const h = bus.getHistory('task:started', 2);
    expect(h.length).toBe(2);
    expect(h.every(e => e.type === 'task:started')).toBe(true);
  });
});

// ─── Turn 3: 通配符订阅 ───────────────────────────────────────────────────────

describe('EventBus — 通配符订阅', () => {
  let bus: SimpleEventBus;
  beforeEach(() => { bus = new SimpleEventBus(); });

  it('"task:*" 能接收 task:started 事件', async () => {
    const received: SystemEvent[] = [];
    (bus as any).on('task:*', (e: SystemEvent) => { received.push(e); });
    await bus.emit(makeStarted('t1'));
    expect(received.length).toBe(1);
    expect(received[0].type).toBe('task:started');
  });

  it('"task:*" 同时接收 task:completed 和 task:failed', async () => {
    const received: SystemEvent[] = [];
    (bus as any).on('task:*', (e: SystemEvent) => { received.push(e); });
    await bus.emit(makeCompleted('t1'));
    await bus.emit(makeFailed('t2'));
    expect(received.length).toBe(2);
  });

  it('"task:*" 不接收 stage:completed（命名空间不匹配）', async () => {
    const received: SystemEvent[] = [];
    (bus as any).on('task:*', (e: SystemEvent) => { received.push(e); });
    await bus.emit({ id: 'e1', type: 'stage:completed', timestamp: Date.now(), stageIndex: 0 });
    expect(received.length).toBe(0);
  });

  it('通配符订阅返回的 unsubscribe 函数可取消订阅', async () => {
    const received: SystemEvent[] = [];
    const unsub = (bus as any).on('task:*', (e: SystemEvent) => { received.push(e); });
    unsub();
    await bus.emit(makeStarted('t1'));
    expect(received.length).toBe(0);
  });

  it('精确订阅和通配符订阅共存，同一事件两者都收到', async () => {
    const exact: SystemEvent[] = [];
    const wildcard: SystemEvent[] = [];
    bus.on('task:started', (e) => { exact.push(e); });
    (bus as any).on('task:*', (e: SystemEvent) => { wildcard.push(e); });
    await bus.emit(makeStarted('t1'));
    expect(exact.length).toBe(1);
    expect(wildcard.length).toBe(1);
  });
});
