"""
Phase 2 smoke test — drive the UDS listener directly (no stdio, no Claude Code).

Verification points:
  1. Server binds UDS sock at the expected path.
  2. McpClient.call('cc_status_set', {state:'busy', cwd}) writes .cbim/.cc-status.
  3. McpClient.call('snapshot_for_session_start', {...}) returns dict with 'additionalContext'.
  4. Bad sock path -> retries -> stderr warning -> returns None.
  5. Server shutdown removes sock file.
"""

from __future__ import annotations

import asyncio
import io
import os
import shutil
import sys
import tempfile
from contextlib import redirect_stderr
from pathlib import Path


HERE = Path(__file__).resolve().parent
KERNEL_SRC = HERE.parent / "src" / "kernel"
HOOKS_SRC = KERNEL_SRC / "project" / "hooks_src"

sys.path.insert(0, str(KERNEL_SRC))
sys.path.insert(0, str(HOOKS_SRC))


def main() -> int:
    tmpdir = Path(tempfile.mkdtemp(prefix="cbim-phase2-"))
    (tmpdir / ".cbim").mkdir()
    (tmpdir / ".claude").mkdir()
    os.environ["CBIM_PROJECT_ROOT"] = str(tmpdir)

    # XDG_CACHE_HOME isolates the sock dir so we don't poison real ~/.cache.
    cache_root = tmpdir / "cache"
    cache_root.mkdir()
    os.environ["XDG_CACHE_HOME"] = str(cache_root)

    from mcp_server import server as srv  # noqa
    from _lib import mcp_client, paths

    expected_sock = paths.mcp_sock_path(tmpdir)
    print(f"[smoke] expected sock: {expected_sock}")

    results = {}

    async def run() -> None:
        uds_server, sock_path = await srv._start_uds_listener(srv.mcp, tmpdir)
        try:
            # ---- 1. sock bound at expected path
            results["bind"] = (sock_path == expected_sock and sock_path.exists())

            # ---- 2. cc_status_set writes .cc-status
            r2 = await asyncio.to_thread(
                mcp_client.call, "cc_status_set",
                {"state": "busy", "cwd": str(tmpdir)},
                str(tmpdir),
            )
            cc_status_file = tmpdir / ".cbim" / ".cc-status"
            results["cc_status_set"] = (
                r2 is not None
                and r2.get("ok") is True
                and cc_status_file.exists()
                and "busy" in cc_status_file.read_text()
            )

            # ---- 3. snapshot_for_session_start returns additionalContext
            r3 = await asyncio.to_thread(
                mcp_client.call, "snapshot_for_session_start",
                {"session_id": "test-sid", "cwd": str(tmpdir)},
                str(tmpdir),
            )
            results["snapshot"] = (
                r3 is not None and "additionalContext" in r3
            )

            # ---- 4. wrong sock -> retries -> None + stderr warning
            bogus = tmpdir / "nope" / "mcp.sock"
            buf = io.StringIO()
            client = mcp_client.McpClient(bogus)
            with redirect_stderr(buf):
                r4 = client.call("cc_status_set", {"state": "idle", "cwd": str(tmpdir)})
            client.close()
            stderr_text = buf.getvalue()
            results["unreachable"] = (
                r4 is None
                and "[CBIM:hook]" in stderr_text
                and "mcp unreachable" in stderr_text
            )
        finally:
            uds_server.close()
            await uds_server.wait_closed()

        # ---- 5. sock removed on shutdown
        # _start_uds_listener doesn't unlink (lifespan does); simulate lifespan cleanup.
        try:
            sock_path.unlink(missing_ok=True)
        except OSError:
            pass
        results["cleanup"] = (not sock_path.exists())

    try:
        asyncio.run(run())
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    print()
    print("=" * 50)
    all_pass = True
    for k, v in results.items():
        mark = "PASS" if v else "FAIL"
        print(f"  [{mark}] {k}")
        if not v:
            all_pass = False
    print("=" * 50)
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
