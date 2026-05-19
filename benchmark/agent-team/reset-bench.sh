#!/usr/bin/env bash
# reset-bench.sh — 重置 agent-team benchmark 到基线状态
#
# 用法（从任意位置运行）：
#   bash /path/to/reset-bench.sh /path/to/target-project [--save-run]
#   BENCH_TARGET_DIR=/path/to/target-project bash /path/to/reset-bench.sh [--save-run]
#
# 执行内容：
#   1. 可选地将当前测试结果保存到 cbim/benchmark/agent-team/results/
#   2. git 恢复 agent-team 被测文件到原始状态
#   3. 删除产出文件（TaskMonitor/AgentResourceManager）
#   4. 部署最新测试文件（benchmark/tests/ → target/__tests__/）
#   5. 验证基线（v3: 53 fail | 8 pass）

set -euo pipefail

# ─── 路径推导 ──────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CBIM_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
RESULTS_DIR="$CBIM_DIR/benchmark/agent-team/results"

# ─── TARGET_DIR 解析 ───────────────────────────────────────────────────────────
SAVE_RUN=false

if [[ "${1:-}" != "--save-run" && -n "${1:-}" ]]; then
  TARGET_DIR="$1"
  shift
else
  TARGET_DIR="${BENCH_TARGET_DIR:-}"
fi

if [[ "${1:-}" == "--save-run" ]]; then
  SAVE_RUN=true
fi

if [[ -z "${TARGET_DIR:-}" ]]; then
  echo "Usage:"
  echo "  bash $0 /path/to/target-project [--save-run]"
  echo "  BENCH_TARGET_DIR=/path/to/target-project bash $0 [--save-run]"
  exit 1
fi

# ─── 启动验证 ──────────────────────────────────────────────────────────────────
if [[ ! -d "$TARGET_DIR" ]]; then
  echo "Error: TARGET_DIR does not exist: $TARGET_DIR"
  exit 1
fi

if [[ ! -d "$TARGET_DIR/.git" ]]; then
  echo "Error: TARGET_DIR is not a git repository: $TARGET_DIR"
  exit 1
fi

if [[ ! -d "$TARGET_DIR/packages/core/src" ]]; then
  echo "Error: TARGET_DIR does not contain packages/core/src/: $TARGET_DIR"
  exit 1
fi

# ─── 可选：保存本次结果 ─────────────────────────────────────────────────────────
if [[ "$SAVE_RUN" == true ]]; then
  mkdir -p "$RESULTS_DIR"
  TIMESTAMP=$(date +%Y%m%d_%H%M%S)
  LOG_FILE="$RESULTS_DIR/run_${TIMESTAMP}.log"

  echo "Saving current test results to $LOG_FILE ..."
  cd "$TARGET_DIR"
  npx vitest run \
    packages/core/src/__tests__/task-a.bench.test.ts \
    packages/core/src/__tests__/task-b.bench.test.ts \
    packages/core/src/__tests__/task-c.bench.test.ts \
    packages/core/src/__tests__/task-d.bench.test.ts \
    packages/core/src/__tests__/task-e.bench.test.ts \
    packages/core/src/__tests__/task-f.bench.test.ts \
    2>&1 | tee "$LOG_FILE" || true
  echo ""
  echo "Results saved to: $LOG_FILE"
fi

# ─── 还原被测文件 ───────────────────────────────────────────────────────────────
cd "$TARGET_DIR"

echo ""
echo "=== Resetting agent-team benchmark files ==="

git checkout HEAD -- packages/core/src/orchestration/scheduler.ts
echo "  ✓ scheduler.ts restored"

git checkout HEAD -- packages/core/src/agent/permission-guard.ts
git checkout HEAD -- packages/core/src/types/permission.ts
echo "  ✓ permission-guard.ts restored"
echo "  ✓ types/permission.ts restored"

git checkout HEAD -- packages/core/src/orchestration/event-bus.ts
echo "  ✓ event-bus.ts restored"

if git ls-files --error-unmatch packages/core/src/types/task.ts &>/dev/null 2>&1; then
  git checkout HEAD -- packages/core/src/types/task.ts
  echo "  ✓ types/task.ts restored"
fi

if [[ -f "packages/core/src/orchestration/task-monitor.ts" ]]; then
  rm "packages/core/src/orchestration/task-monitor.ts"
  echo "  ✓ task-monitor.ts deleted"
else
  echo "  - task-monitor.ts not found (already clean)"
fi

if [[ -f "packages/core/src/agent/agent-resource-manager.ts" ]]; then
  rm "packages/core/src/agent/agent-resource-manager.ts"
  echo "  ✓ agent-resource-manager.ts deleted"
else
  echo "  - agent-resource-manager.ts not found (already clean)"
fi

# ─── 部署测试文件 ─────────────────────────────────────────────────────────────────
TESTS_SRC="$CBIM_DIR/benchmark/agent-team/tests"
TESTS_DST="$TARGET_DIR/packages/core/src/__tests__"

echo ""
echo "=== Deploying benchmark test files ==="

for task in a b c d e f; do
  cp "$TESTS_SRC/task-${task}.bench.test.ts" "$TESTS_DST/task-${task}.bench.test.ts"
  echo "  ✓ task-${task}.bench.test.ts deployed"
done

# ─── 验证基线 ───────────────────────────────────────────────────────────────────
echo ""
echo "=== Verifying baseline ==="

RESULT=$(npx vitest run \
  packages/core/src/__tests__/task-a.bench.test.ts \
  packages/core/src/__tests__/task-b.bench.test.ts \
  packages/core/src/__tests__/task-c.bench.test.ts \
  packages/core/src/__tests__/task-d.bench.test.ts \
  packages/core/src/__tests__/task-e.bench.test.ts \
  packages/core/src/__tests__/task-f.bench.test.ts \
  2>&1 || true)

echo "$RESULT" | tail -5

FAILED=$(echo "$RESULT" | grep -E '^\s+Tests\s+' | grep -o '[0-9]* failed' | grep -o '[0-9]*' || echo "?")
PASSED=$(echo "$RESULT" | grep -E '^\s+Tests\s+' | grep -o '[0-9]* passed' | grep -o '[0-9]*' || echo "?")

echo ""
# v3 baseline: A+B+C=14fail/8pass, D=12fail/3pass, E=8fail/4pass, F=0(file error)
# Total: 34 fail | 15 pass (49 counted tests; F's 12 tests don't count until class exists)
if [[ "$FAILED" == "34" && "$PASSED" == "15" ]]; then
  echo "✅ Baseline verified: ${FAILED} failed | ${PASSED} passed"
else
  echo "⚠️  Baseline mismatch: ${FAILED} failed | ${PASSED} passed (expected 34 failed | 15 passed)"
  echo "   Run: cd $TARGET_DIR && git status"
fi

echo ""
echo "══════════════════════════════════════════════════════════"
echo "  Ready. Open a new Claude Code session to start testing. "
echo "══════════════════════════════════════════════════════════"
echo ""
echo "Prompts: $CBIM_DIR/benchmark/agent-team/prompts/"
echo "Results: $RESULTS_DIR/"
