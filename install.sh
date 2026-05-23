#!/usr/bin/env bash
# CBIM bootstrap installer.
# Run from your project root:
#   curl -sSL https://raw.githubusercontent.com/nan023062/cbim/master/install.sh | bash
# Or after `git clone`:
#   bash install.sh
#
# Effect (idempotent):
#   - clones cbim master into a tempdir
#   - replaces <project>/.cbim/kernel/ with v1/src/kernel/ (flat layout)
#   - runs `python3 -m engine init` to (re)populate .cbim/, .claude/, CLAUDE.md, .gitignore
# Preserved across re-runs: .cbim/memory/, .cbim/scheduler/, .cbim/config.json, .dna/.
# Not supported on native Windows; use WSL.

set -euo pipefail

REPO_URL="https://github.com/nan023062/cbim"
PROJECT_ROOT="$(pwd)"

log() { printf '[CBIM] %s\n' "$*" >&2; }
die() { printf '[CBIM] error: %s\n' "$*" >&2; exit 1; }

# --- 1. dependency probe ---
command -v git >/dev/null 2>&1 || die "git not found on PATH"

PYTHON_BIN=""
if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  if python -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' >/dev/null 2>&1; then
    PYTHON_BIN="python"
  fi
fi
[ -n "$PYTHON_BIN" ] || die "python3 (>= 3.10) not found on PATH"

# --- 2. tempdir clone ---
TMPDIR_CBIM="$(mktemp -d 2>/dev/null || mktemp -d -t cbim)"
trap 'rm -rf "$TMPDIR_CBIM"' EXIT

log "cloning $REPO_URL ..."
git clone --depth 1 "$REPO_URL" "$TMPDIR_CBIM/cbim" >/dev/null 2>&1 \
  || die "git clone failed"

SRC_KERNEL="$TMPDIR_CBIM/cbim/v1/src/kernel"
[ -d "$SRC_KERNEL" ] || die "kernel source missing in clone: $SRC_KERNEL"

# --- 3. replace kernel (flat copy, no cbim_kernel/ wrapper) ---
DST_KERNEL="$PROJECT_ROOT/.cbim/kernel"
log "installing kernel into $DST_KERNEL ..."
rm -rf "$DST_KERNEL"
mkdir -p "$DST_KERNEL"
# trailing /. copies contents of kernel/, not the directory itself
cp -R "$SRC_KERNEL/." "$DST_KERNEL/"

# --- 4. run engine init ---
log "running engine init ..."
log "(first install builds a managed venv at .cbim/.venv/ and downloads"
log " the ~10 MB \`mcp\` SDK into it — may take a few seconds)"
cd "$PROJECT_ROOT"
PYTHONPATH="$DST_KERNEL" "$PYTHON_BIN" -m engine init

# --- 5. done ---
log "installed. Restart Claude Code so the SessionStart hook fires."
