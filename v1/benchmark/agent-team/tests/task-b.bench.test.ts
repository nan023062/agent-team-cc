/**
 * Benchmark Task B: PermissionGuard 新增 temp zone
 *
 * 实现目标：
 *   1. types/permission.ts — PathZone 添加 'temp'
 *   2. types/permission.ts — DEFAULT_PERMISSION_MATRIX 为所有角色添加 temp zone 规则
 *   3. permission-guard.ts — DEFAULT_PERMISSION_MATRIX 也添加 temp zone 规则
 *   4. permission-guard.ts — classifyPath() 识别 /tmp/ 开头路径 → 'temp'
 *
 * temp zone 权限规则（所有角色）：read + write，无 execute
 *
 * 关键陷阱：
 *   - /tmp-backup/config.json → 'project'（不以 /tmp/ 含斜杠开头，不属于 temp）
 *     classifyPath 必须用 startsWith('/tmp/') 而非 startsWith('/tmp')
 *   - temp zone 不允许 execute，即使是 secretary / worker / programmer
 *   - 必须同时修改两个文件中的 DEFAULT_PERMISSION_MATRIX（types/permission.ts 和
 *     agent/permission-guard.ts）；仅修改其中一个会导致类型或运行时不一致
 *
 * 基线状态：8 FAIL / 8 PASS（temp zone 未实现时，/tmp/ 路径归入 project zone）
 *
 * 基线通过分析：
 *   classifyPath 6 用例：3 FAIL（/tmp → project≠temp）, 3 PASS（现有 zone 不受影响）
 *   check 8 用例：4 FAIL, 4 PASS（/tmp 在无 temp zone 时归 project zone，
 *     部分角色的 project 权限恰好与 temp 权限一致则 PASS，不一致则 FAIL）
 *   createGuard 2 用例：1 FAIL, 1 PASS
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
  // 基线：3 FAIL + 3 PASS

  describe('classifyPath() - temp 分类', () => {
    // FAIL: /tmp 当前归 project，期望 temp
    it('/tmp/scratch.txt → temp', () => {
      expect(guard.classifyPath('/tmp/scratch.txt')).toBe('temp');
    });

    // FAIL: /tmp 当前归 project，期望 temp
    it('/tmp → temp', () => {
      expect(guard.classifyPath('/tmp')).toBe('temp');
    });

    // FAIL: /tmp 当前归 project，期望 temp
    it('/tmp/subdir/deep/file.json → temp', () => {
      expect(guard.classifyPath('/tmp/subdir/deep/file.json')).toBe('temp');
    });

    // PASS: /tmp-backup/ 不以 /tmp/ 开头，不属于 temp zone
    // 关键边界：classifyPath 必须用 startsWith('/tmp/') 而非 startsWith('/tmp')
    // 若误用后者，/tmp-backup/config.json 会被错误归入 temp
    it('/tmp-backup/config.json → project（不以 /tmp/ 开头）', () => {
      expect(guard.classifyPath('/tmp-backup/config.json')).toBe('project');
    });

    // PASS: workspace 分类不受 temp 影响
    it('/workspace/x.md → workspace（不受 temp 影响）', () => {
      expect(guard.classifyPath('/workspace/x.md')).toBe('workspace');
    });

    // PASS: project 分类不受 temp 影响
    it('/project/src/main.ts → project（不受 temp 影响）', () => {
      expect(guard.classifyPath('/project/src/main.ts')).toBe('project');
    });
  });

  // ─── check() - temp zone 权限 ────────────────────────────────────────────────
  // 基线：4 FAIL + 4 PASS
  //
  // 无 temp zone 时，/tmp → project zone
  // project zone 权限：
  //   auditor:     read            → read PASS, write FAIL
  //   worker:      read,write,exec → write PASS, exec→denied FAIL
  //   secretary:   read,write,exec → write PASS, exec→denied FAIL
  //   architect:   read            → read PASS
  //   hr:          read            → write FAIL

  describe('check() - temp zone 访问控制', () => {
    // PASS: /tmp → project, auditor read project → allowed
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

    // FAIL: /tmp → project, auditor write project → denied, 但期望 allowed
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

    // PASS: /tmp → project, worker write project → allowed
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

    // PASS: /tmp → project, secretary write project → allowed
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

    // FAIL: /tmp → project, worker execute project → allowed, 但期望 denied
    it('worker execute /tmp/script.sh → denied（temp zone 无 execute 权限）', () => {
      const r = guard.check({
        role: 'worker',
        agentId: 'wrk',
        operation: 'execute',
        targetPath: '/tmp/script.sh',
        toolName: 'bash',
      });
      expect(r.allowed).toBe(false);
    });

    // FAIL: /tmp → project, secretary execute project → allowed, 但期望 denied
    it('secretary execute /tmp/run.sh → denied（temp zone 无 execute 权限）', () => {
      const r = guard.check({
        role: 'secretary',
        agentId: 'sec',
        operation: 'execute',
        targetPath: '/tmp/run.sh',
        toolName: 'bash',
      });
      expect(r.allowed).toBe(false);
    });

    // PASS: /tmp → project, architect read project → allowed
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

    // FAIL: /tmp → project, hr write project → denied, 但期望 allowed
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
  // 基线：1 FAIL + 1 PASS

  describe('createGuard() - temp zone 钩子', () => {
    // PASS: /tmp → project, worker write project → allowed → 放行（返回 undefined）
    it('worker 用 write_file 写 /tmp → 放行', async () => {
      const hook = guard.createGuard('worker', 'wrk-1');
      const result = await hook({
        toolCall: { name: 'write_file' },
        args: { path: '/tmp/generated.ts' },
      });
      expect(result).toBeUndefined();
    });

    // FAIL: /tmp → project, auditor write project → denied → 阻断,
    // 但期望放行（temp zone auditor 可 write）
    it('auditor 用 write_file 写 /tmp → 放行（temp zone 允许 write）', async () => {
      const hook = guard.createGuard('auditor', 'aud-1');
      const result = await hook({
        toolCall: { name: 'write_file' },
        args: { path: '/tmp/analysis-result.md' },
      });
      expect(result).toBeUndefined();
    });
  });
});
