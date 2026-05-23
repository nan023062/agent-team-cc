#!/usr/bin/env bash
# Workflow tests — one-shot runner.
#
# Runs all 8 cases through pytest, persists per-case session logs, and
# generates `results/report-NNN.md` (auto-numbered).
#
# Usage (from anywhere; this script resolves the repo root itself):
#   ANTHROPIC_API_KEY=sk-... ./v1/tests/workflow/run-bench.sh
#
# Cost: ~$1-$10 per full run, 3-10 minutes wall time.

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
if [ ! -x "$REPO_ROOT/.venv/bin/pytest" ]; then
  echo "[bench] error: .venv/bin/pytest not found at $REPO_ROOT/.venv/bin/pytest" >&2
  exit 1
fi

# 2. Allocate next report-NNN slot
RESULTS_DIR="$SCRIPT_DIR/results"
mkdir -p "$RESULTS_DIR"
EXISTING=$(ls "$RESULTS_DIR" 2>/dev/null | grep -cE '^report-[0-9]{3}\.md$' || true)
NEXT_N=$(printf '%03d' "$((EXISTING + 1))")
REPORT_MD="$RESULTS_DIR/report-${NEXT_N}.md"
ARTIFACT_DIR="$RESULTS_DIR/report-${NEXT_N}"
LOGS_DIR="$ARTIFACT_DIR/logs"
mkdir -p "$LOGS_DIR"

# 3. Run pytest, tee raw output
RAW_OUTPUT="$ARTIFACT_DIR/pytest-output.txt"
TS_START="$(date '+%Y-%m-%d %H:%M:%S')"
GIT_COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
GIT_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"

echo "[bench] running 8 cases → $REPORT_MD"
echo "[bench] (this may take 3-10 minutes and cost \$1-\$10 in API)"
BENCH_LOGS_DIR="$LOGS_DIR" "$REPO_ROOT/.venv/bin/pytest" \
  "$SCRIPT_DIR" -m workflow -v -s 2>&1 | tee "$RAW_OUTPUT"
PYTEST_EXIT=${PIPESTATUS[0]}
TS_END="$(date '+%Y-%m-%d %H:%M:%S')"

# 4. Build the markdown report via framework.reporter
"$REPO_ROOT/.venv/bin/python" -m v1.tests.workflow.framework.reporter \
  --raw-output "$RAW_OUTPUT" \
  --logs-dir "$LOGS_DIR" \
  --output "$REPORT_MD" \
  --ts-start "$TS_START" \
  --ts-end "$TS_END" \
  --git-commit "$GIT_COMMIT" \
  --git-branch "$GIT_BRANCH" \
  --pytest-exit "$PYTEST_EXIT" \
  --report-id "$NEXT_N"

echo ""
echo "[bench] report : $REPORT_MD"
echo "[bench] logs   : $LOGS_DIR"
exit "$PYTEST_EXIT"
