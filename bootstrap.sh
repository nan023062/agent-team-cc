#!/usr/bin/env bash
# cbim-bootstrap — one-line installer for CBIM (https://github.com/nan023062/cbim)
# Downloads a release tarball, extracts it, and runs v1/src/install.py.
# Example: curl -fsSL https://raw.githubusercontent.com/nan023062/cbim/master/bootstrap.sh | bash

set -euo pipefail

PREFIX="[cbim-bootstrap]"
REPO="nan023062/cbim"

# ---------- helpers ----------
die() {
  # die <exit_code> <message>
  local code="$1"; shift
  printf '%s ERROR: %s\n' "$PREFIX" "$*" >&2
  exit "$code"
}

log() {
  if [ "${CBIM_BOOTSTRAP_QUIET:-0}" = "1" ]; then
    return 0
  fi
  printf '%s %s\n' "$PREFIX" "$*"
}

# ---------- preflight ----------
command -v python3 >/dev/null 2>&1 || die 10 \
  "python3 not found in PATH. Install Python 3.10+ from https://www.python.org/downloads/ and retry."

command -v curl >/dev/null 2>&1 || die 10 \
  "curl not found in PATH. Install curl and retry."

command -v tar >/dev/null 2>&1 || die 10 \
  "tar not found in PATH. Install tar and retry."

# Python >= 3.10 check
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' >/dev/null 2>&1; then
  PYVER="$(python3 --version 2>&1 || true)"
  die 11 "Python 3.10+ required, found: ${PYVER}. Upgrade Python and retry."
fi

# Disk space check (>= 200MB free in mktemp parent)
TMPPARENT="${TMPDIR:-/tmp}"
# df -k returns 1K blocks; the 4th column on POSIX is "Available". macOS/Linux both compatible.
AVAIL_KB="$(df -k "$TMPPARENT" 2>/dev/null | awk 'NR==2 {print $4}' | tr -d '[:space:]')"
if [ -z "${AVAIL_KB:-}" ] || ! [ "$AVAIL_KB" -eq "$AVAIL_KB" ] 2>/dev/null; then
  die 30 "Could not determine free disk space at ${TMPPARENT}. Free space then retry."
fi
if [ "$AVAIL_KB" -lt 204800 ]; then
  die 30 "Insufficient disk space at ${TMPPARENT}: $((AVAIL_KB/1024))MB free, need >= 200MB. Free space then retry."
fi

# ---------- decide ref ----------
if [ -n "${CBIM_REF:-}" ]; then
  REF="${CBIM_REF}"
elif [ -n "${CBIM_VERSION:-}" ]; then
  REF="tags/v${CBIM_VERSION}"
else
  log "resolving latest release from github.com/${REPO} ..."
  API_URL="https://api.github.com/repos/${REPO}/releases/latest"
  API_JSON="$(curl -fsSL "$API_URL" 2>/dev/null || true)"
  if [ -z "$API_JSON" ]; then
    die 20 "Failed to fetch latest release from ${API_URL}. Check network, or pin with CBIM_VERSION=x.y.z and retry."
  fi
  TAG="$(printf '%s' "$API_JSON" | grep -o '"tag_name"[[:space:]]*:[[:space:]]*"[^"]*"' | head -n1 | sed -E 's/.*"tag_name"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/')"
  if [ -z "$TAG" ]; then
    die 20 "Could not parse tag_name from GitHub API response. Pin with CBIM_VERSION=x.y.z and retry."
  fi
  REF="tags/${TAG}"
fi

# ---------- tmpdir + trap ----------
TMPDIR_BS="$(mktemp -d -t cbim-bootstrap-XXXXXX)"
cleanup() {
  if [ "${CBIM_KEEP_TMPDIR:-0}" = "1" ]; then
    printf '%s tmpdir kept at: %s\n' "$PREFIX" "$TMPDIR_BS" >&2
    return 0
  fi
  rm -rf "$TMPDIR_BS"
}
trap cleanup EXIT INT TERM

# ---------- download ----------
TARBALL_URL="https://codeload.github.com/${REPO}/tar.gz/refs/${REF}"
log "downloading ref=${REF} ..."
if ! curl -fsSL "$TARBALL_URL" -o "$TMPDIR_BS/cbim.tar.gz"; then
  die 20 "Failed to download tarball from ${TARBALL_URL}. Check network / ref name and retry."
fi

# ---------- extract ----------
log "extracting ..."
if ! tar -xzf "$TMPDIR_BS/cbim.tar.gz" -C "$TMPDIR_BS"; then
  die 20 "Failed to extract tarball. Re-run; if it persists report at https://github.com/${REPO}/issues."
fi

# Find extracted top-level directory (cbim-*)
EXTRACT_DIR=""
for d in "$TMPDIR_BS"/cbim-*; do
  if [ -d "$d" ]; then
    EXTRACT_DIR="$d"
    break
  fi
done
if [ -z "$EXTRACT_DIR" ]; then
  die 20 "Extracted tarball does not contain expected cbim-* directory."
fi

INSTALLER="$EXTRACT_DIR/v1/src/install.py"
if [ ! -f "$INSTALLER" ]; then
  die 20 "Installer not found at ${INSTALLER}. The downloaded ref=${REF} may be incompatible with this bootstrap."
fi

# ---------- dry run ----------
if [ "${CBIM_BOOTSTRAP_DRY_RUN:-0}" = "1" ]; then
  log "DRY RUN: would exec python3 ${INSTALLER}"
  exit 0
fi

# ---------- run installer ----------
log "running install.py ..."
cd "$EXTRACT_DIR/v1/src"
# Run as child (not exec) so the EXIT trap cleans up TMPDIR_BS afterwards.
# Pass through install.py's exit code verbatim.
set +e
python3 install.py
RC=$?
set -e
exit "$RC"
