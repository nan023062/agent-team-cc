/**
 * Benchmark Task A: Scheduler.dryRun()
 *
 * 实现目标：在 Scheduler 类上添加 dryRun(plan: ExecutionPlan): DryRunReport 方法。
 * 不实际执行任务，仅静态分析执行计划并返回报告。
 *
 * DryRunReport 结构：
 *   stageCount: number       —— plan.stages.length
 *   taskCount: number        —— plan.tasks.length
 *   totalAttempts: number    —— taskCount × (config.maxRetries + 1)
 *   detectedIssues: string[] —— 检测到的结构性问题（如依赖任务不在计划中）
 *
 * 关键陷阱：
 *   DEFAULT_SCHEDULER_CONFIG.maxRetries = 1
 *   → TaskRunner.withRetry(): for (let attempt = 0; attempt <= maxRetries; attempt++)
 *   → attempt 取 0 和 1，共 2 次执行
 *   → 3 个任务的 totalAttempts = 6（不是 3）
 */

import { describe, it, expect, vi } from 'vitest';
import { Scheduler } from '../orchestration/scheduler.js';
import { SimpleEventBus } from '../orchestration/event-bus.js';
import type { ExecutionPlan, TaskDefinition, TaskStage } from '../types/task.js';
import type { AgentManager } from '../agent/agent-manager.js';
import type { ModuleManager } from '../module/module-manager.js';

// ─── 工具函数 ──────────────────────────────────────────────────────────────────

function makeTask(id: string, dependencies: string[] = []): TaskDefinition {
  return {
    id,
    description: `Task ${id}`,
    agentId: 'programmer',
    moduleContext: [],
    dependencies,
    priority: 'normal',
    createdAt: Date.now(),
  };
}

function makePlan(tasks: TaskDefinition[], stages: TaskStage[]): ExecutionPlan {
  return {
    id: `plan-bench-${Date.now()}`,
    tasks,
    stages,
    createdAt: Date.now(),
  };
}

function makeScheduler(config: { maxRetries?: number; maxConcurrency?: number } = {}) {
  const mockAgentManager = {
    listAll: vi.fn().mockReturnValue([]),
    getRegistry: vi.fn().mockReturnValue(undefined),
    spawnSubagent: vi.fn().mockResolvedValue({
      success: true,
      output: 'dry-run: not executed',
      completedAt: Date.now(),
    }),
  } as unknown as AgentManager;

  const mockModuleManager = {
    listModules: vi.fn().mockReturnValue([]),
    getModuleKnowledge: vi.fn().mockResolvedValue(null),
  } as unknown as ModuleManager;

  const eventBus = new SimpleEventBus();
  return new Scheduler(mockAgentManager, mockModuleManager, eventBus, {
    maxConcurrency: 5,
    taskTimeoutMs: 30_000,
    ...config,
  });
}

// ─── 测试套件 ──────────────────────────────────────────────────────────────────

describe('Scheduler.dryRun()', () => {
  it('dryRun 方法存在于 Scheduler 实例上', () => {
    const scheduler = makeScheduler();
    expect(typeof (scheduler as any).dryRun).toBe('function');
  });

  it('空计划 → stageCount=0, taskCount=0, totalAttempts=0, detectedIssues=[]', () => {
    const scheduler = makeScheduler();
    const plan = makePlan([], []);
    const report = (scheduler as any).dryRun(plan);

    expect(report.stageCount).toBe(0);
    expect(report.taskCount).toBe(0);
    expect(report.totalAttempts).toBe(0);
    expect(report.detectedIssues).toEqual([]);
  });

  it('3 个任务 + maxRetries=1（默认）→ totalAttempts=6', () => {
    // 关键陷阱：maxRetries=1 等于 withRetry() 中 attempt 跑 0 和 1，共 2 次
    // 3 个任务 × 2 次执行 = 6，而不是 3
    const scheduler = makeScheduler({ maxRetries: 1 });
    const tasks = [makeTask('A'), makeTask('B'), makeTask('C')];
    const plan = makePlan(tasks, [{ stageIndex: 0, taskIds: ['A', 'B', 'C'] }]);

    const report = (scheduler as any).dryRun(plan);

    expect(report.taskCount).toBe(3);
    expect(report.totalAttempts).toBe(6); // 3 × (1 + 1)
  });

  it('2 个任务 + maxRetries=0 → totalAttempts=2（每任务只执行一次）', () => {
    const scheduler = makeScheduler({ maxRetries: 0 });
    const tasks = [makeTask('X'), makeTask('Y')];
    const plan = makePlan(tasks, [{ stageIndex: 0, taskIds: ['X', 'Y'] }]);

    const report = (scheduler as any).dryRun(plan);

    expect(report.taskCount).toBe(2);
    expect(report.totalAttempts).toBe(2); // 2 × (0 + 1)
  });

  it('检测到缺失的依赖任务，detectedIssues 包含缺失 ID', () => {
    const scheduler = makeScheduler();
    // task-B 声明依赖 task-A，但 task-A 不在 plan.tasks 中
    const tasks = [makeTask('task-B', ['task-A'])];
    const plan = makePlan(tasks, [{ stageIndex: 0, taskIds: ['task-B'] }]);

    const report = (scheduler as any).dryRun(plan);

    expect(report.detectedIssues.length).toBeGreaterThan(0);
    // 报告中应提及缺失的依赖 ID
    const issues: string[] = report.detectedIssues;
    expect(issues.some((msg) => msg.includes('task-A'))).toBe(true);
  });

  it('依赖完整的正常计划 → detectedIssues 为空', () => {
    const scheduler = makeScheduler();
    const tasks = [makeTask('A'), makeTask('B', ['A'])];
    const plan = makePlan(tasks, [
      { stageIndex: 0, taskIds: ['A'] },
      { stageIndex: 1, taskIds: ['B'] },
    ]);

    const report = (scheduler as any).dryRun(plan);

    expect(report.stageCount).toBe(2);
    expect(report.taskCount).toBe(2);
    expect(report.detectedIssues).toEqual([]);
  });
});
