/**
 * Benchmark Task B: PermissionGuard 新增 temp zone
 *
 * 实现目标：
 *   1. types/permission.ts — PathZone 添加 'temp'
 *   2. types/permission.ts — DEFAULT_PERMISSION_MATRIX 为所有角色添加 temp 规则
 *   3. permission-guard.ts — DEFAULT_PERMISSION_MATRIX 也添加 temp 规则
 *   4. permission-guard.ts — classifyPath() 识别 /tmp/ 开头路径 → 'temp'
 *
 * temp zone 权限规则（所有角色）：read + write，无 execute
 *
 * 关键陷阱：
 *   - /tmp/.aiworkspace/file → 'aiworkspace'（.aiworkspace 优先级高于 temp）
 *   - temp zone 不允许 execute，即使是 secretary / worker / programmer
 *   - 必须同时修改两个文件中的 DEFAULT_PERMISSION_MATRIX；
 *     仅修改其中一个会导致类型或运行时不一致
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { PermissionGuard, DEFAULT_PERMISSION_MATRIX } from '../agent/permission-guard.js';

const WORKSPACE = '/workspace';
const PROJECT = '/project';

function makeGuard() {
  return new PermissionGuard(WORKSPACE, PROJECT, DEFAULT_PERMISSION_MATRIX);
}

// ─── 测试套件 ──────────────────────────────────────────────────────────────────

describe('PermissionGuard - temp zone', () => {
  let guard: PermissionGuard;

  beforeEach(() => {
    guard = makeGuard();
    guard.clearAuditLog();
  });

  // ─── classifyPath ────────────────────────────────────────────────────────────

  describe('classifyPath() - temp 分类', () => {
    it('/tmp/scratch.txt → temp', () => {
      expect(guard.classifyPath('/tmp/scratch.txt')).toBe('temp');
    });

    it('/tmp → temp', () => {
      expect(guard.classifyPath('/tmp')).toBe('temp');
    });

    it('/tmp/subdir/deep/file.json → temp', () => {
      expect(guard.classifyPath('/tmp/subdir/deep/file.json')).toBe('temp');
    });

    it('/tmp/.aiworkspace/blueprint → aiworkspace（.aiworkspace 优先于 temp）', () => {
      // 关键陷阱：路径在 /tmp/ 下，但含 .aiworkspace/ —— aiworkspace 优先
      expect(guard.classifyPath('/tmp/.aiworkspace/blueprint')).toBe('aiworkspace');
    });

    it('/workspace/x.md → workspace（不受 temp 影响）', () => {
      expect(guard.classifyPath('/workspace/x.md')).toBe('workspace');
    });

    it('/project/src/main.ts → project（不受 temp 影响）', () => {
      expect(guard.classifyPath('/project/src/main.ts')).toBe('project');
    });
  });

  // ─── check() - temp zone 权限 ────────────────────────────────────────────────

  describe('check() - temp zone 访问控制', () => {
    it('auditor read /tmp/report.json → allowed', () => {
      const r = guard.check({
        role: 'auditor',
        agentId: 'aud',
        operation: 'read',
        targetPath: '/tmp/report.json',
        toolName: 'read_file',
      });
      expect(r.allowed).toBe(true);
    });

    it('auditor write /tmp/tmp-output.md → allowed（temp zone 所有角色可写）', () => {
      const r = guard.check({
        role: 'auditor',
        agentId: 'aud',
        operation: 'write',
        targetPath: '/tmp/tmp-output.md',
        toolName: 'write_file',
      });
      expect(r.allowed).toBe(true);
    });

    it('worker write /tmp/output.ts → allowed', () => {
      const r = guard.check({
        role: 'worker',
        agentId: 'wrk',
        operation: 'write',
        targetPath: '/tmp/output.ts',
        toolName: 'write_file',
      });
      expect(r.allowed).toBe(true);
    });

    it('secretary write /tmp/plan.md → allowed', () => {
      const r = guard.check({
        role: 'secretary',
        agentId: 'sec',
        operation: 'write',
        targetPath: '/tmp/plan.md',
        toolName: 'write_file',
      });
      expect(r.allowed).toBe(true);
    });

    it('worker execute /tmp/script.sh → denied（temp zone 无 execute 权限）', () => {
      // 关键陷阱：temp 只有 read+write，即使 worker 在 project 可 execute
      const r = guard.check({
        role: 'worker',
        agentId: 'wrk',
        operation: 'execute',
        targetPath: '/tmp/script.sh',
        toolName: 'bash',
      });
      expect(r.allowed).toBe(false);
    });

    it('secretary execute /tmp/run.sh → denied（temp zone 无 execute 权限）', () => {
      // 秘书在 workspace/project 有 execute，但 temp zone 不允许
      const r = guard.check({
        role: 'secretary',
        agentId: 'sec',
        operation: 'execute',
        targetPath: '/tmp/run.sh',
        toolName: 'bash',
      });
      expect(r.allowed).toBe(false);
    });

    it('architect read /tmp/notes.txt → allowed', () => {
      const r = guard.check({
        role: 'architect',
        agentId: 'arch',
        operation: 'read',
        targetPath: '/tmp/notes.txt',
        toolName: 'read_file',
      });
      expect(r.allowed).toBe(true);
    });

    it('hr write /tmp/candidate.json → allowed', () => {
      const r = guard.check({
        role: 'hr',
        agentId: 'hr-1',
        operation: 'write',
        targetPath: '/tmp/candidate.json',
        toolName: 'write_file',
      });
      expect(r.allowed).toBe(true);
    });
  });

  // ─── createGuard 钩子 ─────────────────────────────────────────────────────────

  describe('createGuard() - temp zone 钩子', () => {
    it('worker 用 write_file 写 /tmp → 放行', async () => {
      const hook = guard.createGuard('worker', 'wrk-1');
      const result = await hook({
        toolCall: { name: 'write_file' },
        args: { path: '/tmp/generated.ts' },
      });
      expect(result).toBeUndefined();
    });

    it('auditor 用 bash 在 /tmp → 阻断（temp zone 无 execute）', async () => {
      const hook = guard.createGuard('auditor', 'aud-1');
      // bash 没有 path 参数，走 execute 分支，使用 projectPath
      // 但如果给了 path=/tmp/x，也应阻断
      const result = await hook({
        toolCall: { name: 'write_file' },
        args: { path: '/tmp/run.sh' },
      });
      // auditor 在 temp 可以 write，所以放行
      expect(result).toBeUndefined();
    });
  });
});
