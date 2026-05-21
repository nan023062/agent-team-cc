/**
 * Benchmark Task E: Scheduler 调度策略扩展
 *
 * 实现目标：为 Scheduler（orchestration/scheduler.ts）增加三项调度策略
 *
 * ─── Turn 1: 每任务独立超时（timeoutMs）────────────────────────────────────────
 * TaskDefinition 新增可选字段 timeoutMs?: number
 * 设置后该值优先于 SchedulerConfig.taskTimeoutMs 生效
 * 超时后任务自动失败，TaskResult.error 包含 "timeout"（大小写不敏感）
 *
 * ─── Turn 2: 指数退避重试（retryBackoff）────────────────────────────────────────
 * SchedulerConfig 新增 retryBackoff?: 'none' | 'exponential'，默认 'none'
 * SchedulerConfig 新增 retryBaseDelayMs?: number，默认 1000
 * 'exponential'：第 n 次重试等待 (2^(n-1)) * retryBaseDelayMs ms
 *   → attempt 1: 1×base, attempt 2: 2×base, attempt 3: 4×base
 * Scheduler 暴露 calcRetryDelay(attempt: number): number 方法供验证
 *
 * ─── Turn 3: 优先级调度（priority ordering）────────────────────────────────────
 * 同一 stage 内的任务，在 maxConcurrency 限制下按优先级排序进入执行队列
 * 顺序：critical > high > normal > low
 * maxConcurrency=1 时执行顺序严格遵循优先级
 * 不同 stage 之间仍然串行，优先级不跨 stage 生效
 *
 * 关键陷阱：
 *   1. timeoutMs 只影响单个任务，不修改全局配置
 *   2. calcRetryDelay(0) 返回 0（首次执行无延迟，attempt 从 1 开始计重试次数）
 *   3. 优先级排序只决定同 stage 内的启动顺序，stage 边界仍然严格串行
 *
 * 基线状态：12/12 FAIL（相关功能尚未实现）
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Scheduler } from '../orchestration/scheduler.js';
import { SimpleEventBus } from '../orchestration/event-bus.js';
import type { ExecutionPlan, TaskDefinition, TaskStage } from '../types/task.js';
import type { AgentManager } from '../agent/agent-manager.js';
import type { ModuleManager } from '../module/module-manager.js';

// ─── 工具函数 ─────────────────────────────────────────────────────────────────

function makeTask(
  id: string,
  extra: { priority?: TaskDefinition['priority']; dependencies?: string[]; timeoutMs?: number } = {}
): TaskDefinition {
  return {
    id,
    description: `Task ${id}`,
    agentId: 'programmer',
    moduleContext: [],
    dependencies: extra.dependencies ?? [],
    priority: extra.priority ?? 'normal',
    createdAt: Date.now(),
    ...(extra.timeoutMs !== undefined ? { timeoutMs: extra.timeoutMs } : {}),
  } as TaskDefinition;
}

function makePlan(tasks: TaskDefinition[], stageGroups?: string[][]): ExecutionPlan {
  const groups = stageGroups ?? [tasks.map(t => t.id)];
  const stages: TaskStage[] = groups.map((ids, i) => ({ stageIndex: i, taskIds: ids }));
  return { id: `plan-${Date.now()}`, tasks, stages, createdAt: Date.now() };
}

type AgentImpl = (task: TaskDefinition) => Promise<{ success: boolean; output: string; error?: string }>;

function makeScheduler(
  agentImpl: AgentImpl = async () => ({ success: true, output: 'done' }),
  config: {
    maxConcurrency?: number;
    taskTimeoutMs?: number;
    maxRetries?: number;
    retryBackoff?: 'none' | 'exponential';
    retryBaseDelayMs?: number;
  } = {}
) {
  const mockAgentManager = {
    listAll: vi.fn().mockReturnValue([]),
    getRegistry: vi.fn().mockReturnValue(undefined),
    spawnSubagent: vi.fn().mockImplementation(agentImpl),
  } as unknown as AgentManager;

  const mockModuleManager = {
    listModules: vi.fn().mockReturnValue([]),
    getModuleKnowledge: vi.fn().mockResolvedValue(null),
  } as unknown as ModuleManager;

  const bus = new SimpleEventBus();
  const scheduler = new Scheduler(mockAgentManager, mockModuleManager, bus, {
    maxConcurrency: config.maxConcurrency ?? 5,
    taskTimeoutMs: config.taskTimeoutMs ?? 30_000,
    maxRetries: config.maxRetries ?? 0,
    ...(config.retryBackoff !== undefined ? { retryBackoff: config.retryBackoff } : {}),
    ...(config.retryBaseDelayMs !== undefined ? { retryBaseDelayMs: config.retryBaseDelayMs } : {}),
  });
  return { scheduler, bus };
}

// ─── Turn 1: 每任务独立超时 ───────────────────────────────────────────────────

describe('Scheduler — 每任务独立超时（timeoutMs）', () => {
  it('任务 timeoutMs 超时后 result.success=false', async () => {
    const { scheduler } = makeScheduler(
      async () => { await new Promise(r => setTimeout(r, 300)); return { success: true, output: '' }; },
      { taskTimeoutMs: 30_000 }
    );
    const plan = makePlan([makeTask('slow', { timeoutMs: 50 })]);
    const results = await scheduler.executePlan(plan);
    expect(results[0].success).toBe(false);
  }, 3000);

  it('任务超时后 error 包含 "timeout"（大小写不敏感）', async () => {
    const { scheduler } = makeScheduler(
      async () => { await new Promise(r => setTimeout(r, 300)); return { success: true, output: '' }; },
      { taskTimeoutMs: 30_000 }
    );
    const plan = makePlan([makeTask('slow', { timeoutMs: 50 })]);
    const results = await scheduler.executePlan(plan);
    expect(results[0].error?.toLowerCase()).toContain('timeout');
  }, 3000);

  it('任务在 timeoutMs 内完成则正常返回 success=true', async () => {
    const { scheduler } = makeScheduler(
      async () => ({ success: true, output: 'fast' }),
      {}
    );
    const plan = makePlan([makeTask('fast', { timeoutMs: 5000 })]);
    const results = await scheduler.executePlan(plan);
    expect(results[0].success).toBe(true);
  });

  it('不设置 task.timeoutMs 时回落到全局 taskTimeoutMs', async () => {
    const { scheduler } = makeScheduler(
      async () => ({ success: true, output: 'ok' }),
      { taskTimeoutMs: 5000 }
    );
    const plan = makePlan([makeTask('no-override')]);
    const results = await scheduler.executePlan(plan);
    expect(results[0].success).toBe(true);
  });
});

// ─── Turn 2: 指数退避重试 ─────────────────────────────────────────────────────

describe('Scheduler — 指数退避重试（retryBackoff）', () => {
  it('retryBackoff 未设置时 calcRetryDelay 始终返回 0', () => {
    const { scheduler } = makeScheduler(undefined, {});
    expect((scheduler as any).calcRetryDelay(1)).toBe(0);
    expect((scheduler as any).calcRetryDelay(2)).toBe(0);
  });

  it('retryBackoff="none" 时 calcRetryDelay 始终返回 0', () => {
    const { scheduler } = makeScheduler(undefined, { retryBackoff: 'none' });
    expect((scheduler as any).calcRetryDelay(0)).toBe(0);
    expect((scheduler as any).calcRetryDelay(1)).toBe(0);
    expect((scheduler as any).calcRetryDelay(3)).toBe(0);
  });

  it('retryBackoff="exponential" 时 calcRetryDelay(0) 返回 0（首次执行无延迟）', () => {
    const { scheduler } = makeScheduler(undefined, { retryBackoff: 'exponential', retryBaseDelayMs: 1000 });
    expect((scheduler as any).calcRetryDelay(0)).toBe(0);
  });

  it('retryBackoff="exponential" 时延迟按 1x/2x/4x base 指数增长', () => {
    const { scheduler } = makeScheduler(undefined, { retryBackoff: 'exponential', retryBaseDelayMs: 1000 });
    expect((scheduler as any).calcRetryDelay(1)).toBe(1000);
    expect((scheduler as any).calcRetryDelay(2)).toBe(2000);
    expect((scheduler as any).calcRetryDelay(3)).toBe(4000);
  });
});

// ─── Turn 3: 优先级调度 ───────────────────────────────────────────────────────

describe('Scheduler — 优先级调度（priority ordering）', () => {
  it('maxConcurrency=1 时 critical 任务在 low 任务之前执行', async () => {
    const order: string[] = [];
    const { scheduler } = makeScheduler(
      async (task: TaskDefinition) => { order.push(task.id); return { success: true, output: '' }; },
      { maxConcurrency: 1 }
    );
    const tasks = [
      makeTask('low-1', { priority: 'low' }),
      makeTask('critical-1', { priority: 'critical' }),
    ];
    await scheduler.executePlan(makePlan(tasks));
    expect(order.indexOf('critical-1')).toBeLessThan(order.indexOf('low-1'));
  });

  it('maxConcurrency=1 时四级优先级严格按 critical>high>normal>low 执行', async () => {
    const order: string[] = [];
    const { scheduler } = makeScheduler(
      async (task: TaskDefinition) => { order.push(task.id); return { success: true, output: '' }; },
      { maxConcurrency: 1 }
    );
    const tasks = [
      makeTask('low-t', { priority: 'low' }),
      makeTask('normal-t', { priority: 'normal' }),
      makeTask('high-t', { priority: 'high' }),
      makeTask('critical-t', { priority: 'critical' }),
    ];
    await scheduler.executePlan(makePlan(tasks));
    expect(order[0]).toBe('critical-t');
    expect(order[1]).toBe('high-t');
    expect(order[2]).toBe('normal-t');
    expect(order[3]).toBe('low-t');
  });

  it('不同 stage 之间仍然串行，优先级不跨 stage 影响执行顺序', async () => {
    const stageOrder: number[] = [];
    const bus = new SimpleEventBus();
    bus.on('stage:completed', (e) => { stageOrder.push(e.stageIndex); });

    const mockAM = {
      listAll: vi.fn().mockReturnValue([]),
      getRegistry: vi.fn().mockReturnValue(undefined),
      spawnSubagent: vi.fn().mockResolvedValue({ success: true, output: '' }),
    } as unknown as AgentManager;
    const mockMM = {
      listModules: vi.fn().mockReturnValue([]),
      getModuleKnowledge: vi.fn().mockResolvedValue(null),
    } as unknown as ModuleManager;

    const scheduler = new Scheduler(mockAM, mockMM, bus, { maxConcurrency: 1 });
    const plan = makePlan(
      [makeTask('s0', { priority: 'low' }), makeTask('s1', { priority: 'critical' })],
      [['s0'], ['s1']]
    );
    await scheduler.executePlan(plan);
    expect(stageOrder).toEqual([0, 1]);
  });

  it('相同优先级任务的执行结果都包含在最终 results 中', async () => {
    const { scheduler } = makeScheduler(
      async () => ({ success: true, output: 'ok' }),
      { maxConcurrency: 1 }
    );
    const tasks = [
      makeTask('n-a', { priority: 'normal' }),
      makeTask('n-b', { priority: 'normal' }),
      makeTask('n-c', { priority: 'normal' }),
    ];
    const results = await scheduler.executePlan(makePlan(tasks));
    expect(results.length).toBe(3);
    expect(results.every(r => r.success)).toBe(true);
  });
});
