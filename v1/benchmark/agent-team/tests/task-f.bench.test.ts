/**
 * Benchmark Task F: Agent 资源管控
 *
 * 实现目标：新建 AgentResourceManager（agent/agent-resource-manager.ts）实现三项资源管控
 *
 * ─── Turn 1: 并发限制（maxConcurrentTasks）────────────────────────────────────
 * setAgentLimits(agentId, { maxConcurrentTasks: number }) 设置单 agent 最大并发任务数
 * call(agentId, fn) 执行 fn，超过限制时排队等待（不丢弃）
 * 超出并发限制的任务等待前面任务完成后才开始执行
 *
 * ─── Turn 2: 速率限制（rateLimitPerSecond）──────────────────────────────────
 * setAgentLimits(agentId, { rateLimitPerSecond: number }) 设置每秒最大调用次数
 * 超出速率的调用被延迟（不丢弃），在下一时间窗口执行
 *
 * ─── Turn 3: 使用统计（getStats）──────────────────────────────────────────────
 * getStats(agentId: string): AgentUsageStats 返回指定 agent 的统计
 * getStats(): Record<string, AgentUsageStats> 返回所有 agent 的统计
 * AgentUsageStats: { totalCalls: number, activeTasks: number, peakConcurrency: number }
 *
 * 关键陷阱：
 *   1. call() 排队不丢弃——超限任务必须最终执行完成
 *   2. peakConcurrency 记录历史峰值并发数，不是当前值
 *   3. getStats() 不传参返回 Record<string, AgentUsageStats>，传参返回单个 AgentUsageStats
 *
 * 基线状态：12/12 FAIL（AgentResourceManager 尚未实现）
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { AgentResourceManager } from '../agent/agent-resource-manager.js';
import type { AgentUsageStats } from '../agent/agent-resource-manager.js';

// ─── Turn 1: 并发限制 ─────────────────────────────────────────────────────────

describe('AgentResourceManager — 并发限制（maxConcurrentTasks）', () => {
  let rm: AgentResourceManager;
  beforeEach(() => { rm = new AgentResourceManager(); });

  it('maxConcurrentTasks=1：第二个任务等第一个完成后才开始', async () => {
    rm.setAgentLimits('agent-1', { maxConcurrentTasks: 1 });
    const order: string[] = [];
    let resolveFirst!: () => void;
    const firstDone = new Promise<void>(r => { resolveFirst = r; });

    const p1 = rm.call('agent-1', async () => {
      order.push('start-1');
      await firstDone;
      order.push('end-1');
    });
    await new Promise(r => setTimeout(r, 10));
    const p2 = rm.call('agent-1', async () => { order.push('start-2'); });
    resolveFirst();
    await Promise.all([p1, p2]);

    expect(order.indexOf('end-1')).toBeLessThan(order.indexOf('start-2'));
  }, 2000);

  it('maxConcurrentTasks=2：前两个并发执行，第三个排队等待', async () => {
    rm.setAgentLimits('agent-1', { maxConcurrentTasks: 2 });
    const started: string[] = [];
    const resolvers: Array<() => void> = [];

    const tasks = [1, 2, 3].map(i =>
      rm.call('agent-1', async () => {
        started.push(`t${i}`);
        await new Promise<void>(r => { resolvers.push(r); });
      })
    );
    await new Promise(r => setTimeout(r, 20));

    expect(started.length).toBe(2);
    expect(started).toContain('t1');
    expect(started).toContain('t2');

    resolvers.forEach(r => r()); // 释放 t1/t2，t3 进入执行并推入新 resolver
    await new Promise(r => setTimeout(r, 10)); // 等 t3 启动
    resolvers.forEach(r => r()); // 释放 t3
    await Promise.all(tasks);
  }, 2000);

  it('未设限制时多个任务可以同时执行', async () => {
    const concurrent: number[] = [];
    let peak = 0;
    let active = 0;
    const tasks = [1, 2, 3].map(() =>
      rm.call('agent-1', async () => {
        active++;
        peak = Math.max(peak, active);
        await new Promise(r => setTimeout(r, 20));
        active--;
      })
    );
    await Promise.all(tasks);
    expect(peak).toBeGreaterThanOrEqual(2);
  }, 2000);

  it('排队任务在前置任务完成后最终都会执行', async () => {
    rm.setAgentLimits('agent-1', { maxConcurrentTasks: 1 });
    const completed: number[] = [];
    await Promise.all([1, 2, 3].map(i =>
      rm.call('agent-1', async () => { completed.push(i); })
    ));
    expect(completed.length).toBe(3);
  }, 3000);
});

// ─── Turn 2: 速率限制 ─────────────────────────────────────────────────────────

describe('AgentResourceManager — 速率限制（rateLimitPerSecond）', () => {
  let rm: AgentResourceManager;
  beforeEach(() => { rm = new AgentResourceManager(); });

  it('rateLimitPerSecond=2：前两次调用在同一秒内完成', async () => {
    rm.setAgentLimits('agent-1', { rateLimitPerSecond: 2 });
    const timestamps: number[] = [];
    const p1 = rm.call('agent-1', async () => { timestamps.push(Date.now()); });
    const p2 = rm.call('agent-1', async () => { timestamps.push(Date.now()); });
    await Promise.all([p1, p2]);
    expect(timestamps[1] - timestamps[0]).toBeLessThan(500);
  }, 3000);

  it('rateLimitPerSecond=2：第3次调用被延迟到下一时间窗口（≥900ms）', async () => {
    rm.setAgentLimits('agent-1', { rateLimitPerSecond: 2 });
    const timestamps: number[] = [];
    await Promise.all([1, 2, 3].map(() =>
      rm.call('agent-1', async () => { timestamps.push(Date.now()); })
    ));
    expect(timestamps[2] - timestamps[0]).toBeGreaterThanOrEqual(900);
  }, 4000);

  it('速率限制的调用不丢弃，最终都会执行', async () => {
    rm.setAgentLimits('agent-1', { rateLimitPerSecond: 2 });
    const results: number[] = [];
    await Promise.all([1, 2, 3].map(i =>
      rm.call('agent-1', async () => { results.push(i); })
    ));
    expect(results.length).toBe(3);
  }, 4000);

  it('不同 agent 的速率限制互相独立', async () => {
    rm.setAgentLimits('agent-a', { rateLimitPerSecond: 1 });
    rm.setAgentLimits('agent-b', { rateLimitPerSecond: 1 });
    const doneA: number[] = [];
    const doneB: number[] = [];
    const pA = rm.call('agent-a', async () => { doneA.push(1); });
    const pB = rm.call('agent-b', async () => { doneB.push(1); });
    await Promise.all([pA, pB]);
    expect(doneA.length).toBe(1);
    expect(doneB.length).toBe(1);
  }, 2000);
});

// ─── Turn 3: 使用统计 ─────────────────────────────────────────────────────────

describe('AgentResourceManager — 使用统计（getStats）', () => {
  let rm: AgentResourceManager;
  beforeEach(() => { rm = new AgentResourceManager(); });

  it('getStats(agentId) 返回 totalCalls 等于实际调用次数', async () => {
    await rm.call('agent-1', async () => {});
    await rm.call('agent-1', async () => {});
    const stats = rm.getStats('agent-1') as AgentUsageStats;
    expect(stats.totalCalls).toBe(2);
  });

  it('getStats(agentId) 返回 activeTasks=0（任务完成后）', async () => {
    await rm.call('agent-1', async () => {});
    const stats = rm.getStats('agent-1') as AgentUsageStats;
    expect(stats.activeTasks).toBe(0);
  });

  it('getStats(agentId) peakConcurrency 记录历史峰值', async () => {
    rm.setAgentLimits('agent-1', { maxConcurrentTasks: 3 });
    let resolve1!: () => void, resolve2!: () => void;
    const p1 = rm.call('agent-1', async () => { await new Promise<void>(r => { resolve1 = r; }); });
    const p2 = rm.call('agent-1', async () => { await new Promise<void>(r => { resolve2 = r; }); });
    await new Promise(r => setTimeout(r, 10));
    resolve1();
    resolve2();
    await Promise.all([p1, p2]);
    const stats = rm.getStats('agent-1') as AgentUsageStats;
    expect(stats.peakConcurrency).toBeGreaterThanOrEqual(2);
  }, 2000);

  it('getStats() 不传参返回所有 agent 的 Record', async () => {
    await rm.call('agent-1', async () => {});
    await rm.call('agent-2', async () => {});
    const all = rm.getStats() as Record<string, AgentUsageStats>;
    expect(all['agent-1']?.totalCalls).toBe(1);
    expect(all['agent-2']?.totalCalls).toBe(1);
  });
});
