#!/usr/bin/env bash
# reset-bench.sh — 重置 agent-team benchmark 到基线状态
#
# 用法（从任意位置运行）：
#   bash /path/to/cbim/benchmark/agent-team/reset-bench.sh [--save-run]
#
# 执行内容：
#   1. 可选地将当前测试结果保存到 cbim/benchmark/agent-team/results/
#   2. git 恢复 agent-team 被测文件到原始状态
#   3. 删除 TaskMonitor（Task C 的产出文件）
#   4. 验证基线（14 fail | 8 pass）

set -euo pipefail

# ─── 路径配置 ──────────────────────────────────────────────────────────────────
AGENT_TEAM_DIR="/c/Workspace/agent-team"
CBIM_DIR="/c/Workspace/cbim"
RESULTS_DIR="$CBIM_DIR/benchmark/agent-team/results"

# ─── 可选：保存本次结果 ─────────────────────────────────────────────────────────
if [[ "${1:-}" == "--save-run" ]]; then
  mkdir -p "$RESULTS_DIR"
  TIMESTAMP=$(date +%Y%m%d_%H%M%S)
  LOG_FILE="$RESULTS_DIR/run_${TIMESTAMP}.log"

  echo "Saving current test results to $LOG_FILE ..."
  cd "$AGENT_TEAM_DIR"
  npx vitest run \
    packages/core/src/__tests__/task-a.bench.test.ts \
    packages/core/src/__tests__/task-b.bench.test.ts \
    packages/core/src/__tests__/task-c.bench.test.ts \
    2>&1 | tee "$LOG_FILE" || true
  echo ""
  echo "Results saved to: $LOG_FILE"
fi

# ─── 还原被测文件 ───────────────────────────────────────────────────────────────
cd "$AGENT_TEAM_DIR"

echo ""
echo "=== Resetting agent-team benchmark files ==="

git checkout HEAD -- packages/core/src/orchestration/scheduler.ts
echo "  ✓ scheduler.ts restored"

git checkout HEAD -- packages/core/src/agent/permission-guard.ts
git checkout HEAD -- packages/core/src/types/permission.ts
echo "  ✓ permission-guard.ts restored"
echo "  ✓ types/permission.ts restored"

if [[ -f "packages/core/src/orchestration/task-monitor.ts" ]]; then
  rm "packages/core/src/orchestration/task-monitor.ts"
  echo "  ✓ task-monitor.ts deleted"
else
  echo "  - task-monitor.ts not found (already clean)"
fi

# ─── 验证基线 ───────────────────────────────────────────────────────────────────
echo ""
echo "=== Verifying baseline ==="

RESULT=$(npx vitest run \
  packages/core/src/__tests__/task-a.bench.test.ts \
  packages/core/src/__tests__/task-b.bench.test.ts \
  packages/core/src/__tests__/task-c.bench.test.ts \
  2>&1 || true)

echo "$RESULT" | tail -5

FAILED=$(echo "$RESULT" | grep -oP '\d+(?= failed)' || echo "?")
PASSED=$(echo "$RESULT" | grep -oP '\d+(?= passed)' || echo "?")

echo ""
if [[ "$FAILED" == "14" && "$PASSED" == "8" ]]; then
  echo "✅ Baseline verified: ${FAILED} failed | ${PASSED} passed"
else
  echo "⚠️  Baseline mismatch: ${FAILED} failed | ${PASSED} passed (expected 14 failed | 8 passed)"
  echo "   Run: cd $AGENT_TEAM_DIR && git status"
fi

echo ""
echo "══════════════════════════════════════════════════════════"
echo "  Ready. Open a new Claude Code session to start testing. "
echo "══════════════════════════════════════════════════════════"
echo ""
echo "Prompts: $CBIM_DIR/benchmark/agent-team/prompts/"
echo "Results: $RESULTS_DIR/"
