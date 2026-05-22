#!/usr/bin/env python3
"""cbim-bootstrap (Python) — one-line installer for CBIM.

Equivalent to bootstrap.sh, for Windows / no-bash environments.
Example: curl -fsSL https://raw.githubusercontent.com/nan023062/cbim/master/bootstrap.py | python3
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request

PREFIX = "[cbim-bootstrap]"
REPO = "nan023062/cbim"


def _quiet() -> bool:
    return os.environ.get("CBIM_BOOTSTRAP_QUIET", "0") == "1"


def log(msg: str) -> None:
    if _quiet():
        return
    print(f"{PREFIX} {msg}", flush=True)


def die(code: int, msg: str) -> "None":
    print(f"{PREFIX} ERROR: {msg}", file=sys.stderr, flush=True)
    sys.exit(code)


def preflight() -> None:
    # python3 (we're already running it; check version)
    if sys.version_info < (3, 10):
        die(
            11,
            f"Python 3.10+ required, found: {sys.version.split()[0]}. Upgrade Python and retry.",
        )

    if shutil.which("curl") is None:
        die(10, "curl not found in PATH. Install curl and retry.")
    if shutil.which("tar") is None:
        # tar isn't strictly required (we use tarfile), but kept for parity with bootstrap.sh contract.
        die(10, "tar not found in PATH. Install tar and retry.")

    tmpparent = tempfile.gettempdir()
    try:
        usage = shutil.disk_usage(tmpparent)
    except OSError as e:
        die(30, f"Could not determine free disk space at {tmpparent}: {e}. Free space then retry.")
    free_mb = usage.free // (1024 * 1024)
    if free_mb < 200:
        die(
            30,
            f"Insufficient disk space at {tmpparent}: {free_mb}MB free, need >= 200MB. Free space then retry.",
        )


def resolve_ref() -> str:
    ref_env = os.environ.get("CBIM_REF", "").strip()
    if ref_env:
        return ref_env

    ver_env = os.environ.get("CBIM_VERSION", "").strip()
    if ver_env:
        return f"tags/v{ver_env}"

    log(f"resolving latest release from github.com/{REPO} ...")
    api_url = f"https://api.github.com/repos/{REPO}/releases/latest"
    try:
        req = urllib.request.Request(api_url, headers={"Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        die(
            20,
            f"Failed to fetch latest release from {api_url}: {e}. "
            "Check network, or pin with CBIM_VERSION=x.y.z and retry.",
        )

    tag = None
    try:
        payload = json.loads(data.decode("utf-8"))
        tag = payload.get("tag_name")
    except (ValueError, UnicodeDecodeError):
        # Fall back to regex if JSON shape is unexpected.
        m = re.search(rb'"tag_name"\s*:\s*"([^"]+)"', data)
        if m:
            tag = m.group(1).decode("utf-8")

    if not tag:
        die(20, "Could not parse tag_name from GitHub API response. Pin with CBIM_VERSION=x.y.z and retry.")
    return f"tags/{tag}"


def download(ref: str, dest: str) -> None:
    url = f"https://codeload.github.com/{REPO}/tar.gz/refs/{ref}"
    log(f"downloading ref={ref} ...")
    try:
        with urllib.request.urlopen(url, timeout=120) as resp, open(dest, "wb") as f:
            shutil.copyfileobj(resp, f)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        die(20, f"Failed to download tarball from {url}: {e}. Check network / ref name and retry.")


def extract(tarball: str, tmpdir: str) -> str:
    log("extracting ...")
    try:
        with tarfile.open(tarball, "r:gz") as tf:
            # filter="data" requires Python 3.12+; fall back to plain extractall on older versions.
            try:
                tf.extractall(tmpdir, filter="data")  # type: ignore[call-arg]
            except TypeError:
                tf.extractall(tmpdir)
    except (tarfile.TarError, OSError) as e:
        die(20, f"Failed to extract tarball: {e}. Re-run; if it persists report at https://github.com/{REPO}/issues.")

    for name in os.listdir(tmpdir):
        if name.startswith("cbim-") and os.path.isdir(os.path.join(tmpdir, name)):
            return os.path.join(tmpdir, name)
    die(20, "Extracted tarball does not contain expected cbim-* directory.")
    return ""  # unreachable, for type-checkers


def main() -> None:
    preflight()
    ref = resolve_ref()

    tmpdir = tempfile.mkdtemp(prefix="cbim-bootstrap-")
    keep = os.environ.get("CBIM_KEEP_TMPDIR", "0") == "1"

    def cleanup() -> None:
        if keep:
            print(f"{PREFIX} tmpdir kept at: {tmpdir}", file=sys.stderr, flush=True)
            return
        shutil.rmtree(tmpdir, ignore_errors=True)

    try:
        tarball = os.path.join(tmpdir, "cbim.tar.gz")
        download(ref, tarball)
        extract_dir = extract(tarball, tmpdir)

        installer = os.path.join(extract_dir, "v1", "src", "install.py")
        if not os.path.isfile(installer):
            die(20, f"Installer not found at {installer}. The downloaded ref={ref} may be incompatible with this bootstrap.")

        if os.environ.get("CBIM_BOOTSTRAP_DRY_RUN", "0") == "1":
            log(f"DRY RUN: would exec python3 {installer}")
            return

        log("running install.py ...")
        proc = subprocess.run(
            [sys.executable, "install.py"],
            cwd=os.path.join(extract_dir, "v1", "src"),
        )
        sys.exit(proc.returncode)
    finally:
        cleanup()


if __name__ == "__main__":
    main()
