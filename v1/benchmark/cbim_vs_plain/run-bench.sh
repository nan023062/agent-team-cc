#!/usr/bin/env bash
# CBIM vs Plain benchmark — one-shot runner.
#
# Runs each task in plain mode and CBIM-installed mode against fresh copies of
# fixture/, then writes results/report-NNN.md with a side-by-side data table.
#
# Usage (from anywhere; this script resolves the repo root itself):
#   ANTHROPIC_API_KEY=sk-... ./v1/benchmark/cbim_vs_plain/run-bench.sh
#
# Cost: ~$5-$20 per full run, ~5-15 minutes wall time.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO_ROOT"

# 1. Preflight
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "[bench] error: ANTHROPIC_API_KEY not set" >&2
  exit 1
fi
if ! command -v claude >/dev/null 2>&1; then
  echo "[bench] error: claude CLI not on PATH" >&2
  exit 1
fi
if [ ! -x "$REPO_ROOT/.venv/bin/python" ]; then
  echo "[bench] error: .venv/bin/python not found at $REPO_ROOT/.venv/bin/python" >&2
  exit 1
fi

# 2. Allocate next report-NNN slot
RESULTS_DIR="$SCRIPT_DIR/results"
mkdir -p "$RESULTS_DIR"
EXISTING=$(ls "$RESULTS_DIR" 2>/dev/null | grep -cE '^report-[0-9]{3}\.md$' || true)
NEXT_N=$(printf '%03d' "$((EXISTING + 1))")
REPORT_MD="$RESULTS_DIR/report-${NEXT_N}.md"
LOGS_DIR="$RESULTS_DIR/report-${NEXT_N}"
mkdir -p "$LOGS_DIR"

TS_START="$(date '+%Y-%m-%d %H:%M:%S')"
TASK_COUNT=$(ls "$SCRIPT_DIR/tasks"/task_*.py 2>/dev/null | wc -l | tr -d ' ')
echo "[bench] running ${TASK_COUNT} task(s) x 2 modes = $((TASK_COUNT * 2)) claude calls"
echo "[bench] (estimated 5-15 min, ~\$5-\$20 in API cost)"

"$REPO_ROOT/.venv/bin/python" -m v1.benchmark.cbim_vs_plain.runner_cli \
  --fixture   "$SCRIPT_DIR/fixture" \
  --tasks-dir "$SCRIPT_DIR/tasks" \
  --logs-dir  "$LOGS_DIR" \
  --report    "$REPORT_MD" \
  --ts-start  "$TS_START"
EXIT=$?

echo ""
echo "[bench] report : $REPORT_MD"
echo "[bench] logs   : $LOGS_DIR"
exit "$EXIT"
