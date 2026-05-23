"""
Phase 3a smoke test - drive the 7 new hook scripts as real subprocesses.

For each hook:
  - Start the UDS listener (no stdio loop).
  - Spawn `python3 cbim_<event>.py` with a minimal event JSON on stdin.
  - Verify exit code = 0.
  - Verify no `[CBIM:hook] mcp unreachable` warning on stderr.
  - For SessionStart: verify stdout has a valid `hookSpecificOutput.additionalContext`.
  - For cc_status_set callers: verify `.cbim/.cc-status` content.

Then re-run one hook against a deliberately wrong sock path to verify the
B-plan: exit 0 + stderr warn + no side effects.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
KERNEL_SRC = HERE.parent / "src" / "kernel"
HOOKS_SRC = KERNEL_SRC / "project" / "hooks_src"

sys.path.insert(0, str(KERNEL_SRC))
sys.path.insert(0, str(HOOKS_SRC))


HOOKS = [
    "cbim_session_start",
    "cbim_stop",
    "cbim_session_end",
    "cbim_user_prompt_submit",
    "cbim_pre_tool_use",
    "cbim_post_tool_use",
    "cbim_auto_preview",
]


def _make_event(hook: str, cwd: str, transcript: str) -> dict:
    base = {"cwd": cwd, "session_id": "smoke-sid"}
    if hook == "cbim_session_start":
        return {**base}
    if hook == "cbim_stop":
        return {**base, "transcript_path": transcript}
    if hook == "cbim_session_end":
        return {**base, "transcript_path": transcript, "reason": "exit"}
    if hook == "cbim_user_prompt_submit":
        return {**base, "transcript_path": transcript, "prompt": "hello from smoke"}
    if hook == "cbim_pre_tool_use":
        return {
            **base,
            "transcript_path": transcript,
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/x"},
        }
    if hook == "cbim_post_tool_use":
        return {
            **base,
            "transcript_path": transcript,
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/x"},
            "tool_response": {"ok": True, "content": "..."},
        }
    if hook == "cbim_auto_preview":
        return {**base}
    raise ValueError(hook)


def _run_hook(hook: str, event: dict, env_overrides: dict | None = None) -> tuple[int, str, str]:
    script = HOOKS_SRC / f"{hook}.py"
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    proc = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(event).encode("utf-8"),
        capture_output=True,
        env=env,
        timeout=20,
    )
    return proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr.decode("utf-8", "replace")


async def _serve(tmpdir: Path, results: dict) -> None:
    from mcp_server import server as srv
    from _lib import paths

    expected_sock = paths.mcp_sock_path(tmpdir)
    uds_server, sock_path = await srv._start_uds_listener(srv.mcp, tmpdir)
    results["_sock_bound"] = (sock_path == expected_sock and sock_path.exists())

    transcript = tmpdir / "transcript.jsonl"
    transcript.write_text("", encoding="utf-8")

    # Forward XDG_CACHE_HOME to the subprocesses so they resolve the same sock.
    sub_env = {"XDG_CACHE_HOME": os.environ["XDG_CACHE_HOME"]}

    try:
        for hook in HOOKS:
            event = _make_event(hook, str(tmpdir), str(transcript))
            # Run subprocess in a thread so the UDS listener keeps serving.
            code, out, err = await asyncio.to_thread(_run_hook, hook, event, sub_env)

            ok_exit = (code == 0)
            no_unreachable = ("mcp unreachable" not in err)
            results[f"{hook}.exit_zero"] = ok_exit
            results[f"{hook}.no_unreachable"] = no_unreachable

            if hook == "cbim_session_start":
                try:
                    payload = json.loads(out.strip()) if out.strip() else {}
                    hso = payload.get("hookSpecificOutput", {}) or {}
                    results["cbim_session_start.has_additional_context"] = (
                        hso.get("hookEventName") == "SessionStart"
                        and "additionalContext" in hso
                    )
                except json.JSONDecodeError:
                    # Empty stdout is allowed when additionalContext is empty;
                    # treat as pass only when there is no content to emit.
                    results["cbim_session_start.has_additional_context"] = (out.strip() == "")

            if hook == "cbim_user_prompt_submit":
                cc = tmpdir / ".cbim" / ".cc-status"
                results["cbim_user_prompt_submit.cc_status_busy"] = (
                    cc.exists() and "busy" in cc.read_text(encoding="utf-8")
                )

            if hook == "cbim_stop":
                cc = tmpdir / ".cbim" / ".cc-status"
                results["cbim_stop.cc_status_idle"] = (
                    cc.exists() and "idle" in cc.read_text(encoding="utf-8")
                )

        # --- B-plan: bogus sock path -> exit 0 + stderr warn + no side effects
        cc = tmpdir / ".cbim" / ".cc-status"
        marker = "before-bogus"
        cc.write_text(marker, encoding="utf-8")

        bogus_cache = tmpdir / "bogus_cache"
        bogus_cache.mkdir(exist_ok=True)
        bogus_env = {"XDG_CACHE_HOME": str(bogus_cache)}
        event = _make_event("cbim_user_prompt_submit", str(tmpdir), str(transcript))
        code, out, err = await asyncio.to_thread(_run_hook, "cbim_user_prompt_submit", event, bogus_env)

        results["bogus_sock.exit_zero"] = (code == 0)
        results["bogus_sock.warn_emitted"] = ("mcp unreachable" in err and "[CBIM:hook]" in err)
        results["bogus_sock.no_side_effect"] = (cc.read_text(encoding="utf-8") == marker)

    finally:
        uds_server.close()
        try:
            await uds_server.wait_closed()
        except Exception:
            pass
        try:
            sock_path.unlink(missing_ok=True)
        except OSError:
            pass


def main() -> int:
    tmpdir = Path(tempfile.mkdtemp(prefix="cbim-phase3a-"))
    (tmpdir / ".cbim").mkdir()
    (tmpdir / ".claude").mkdir()
    os.environ["CBIM_PROJECT_ROOT"] = str(tmpdir)

    cache_root = tmpdir / "cache"
    cache_root.mkdir()
    os.environ["XDG_CACHE_HOME"] = str(cache_root)

    results: dict = {}
    try:
        asyncio.run(_serve(tmpdir, results))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    print()
    print("=" * 60)
    all_pass = True
    for k in sorted(results):
        v = results[k]
        mark = "PASS" if v else "FAIL"
        print(f"  [{mark}] {k}")
        if not v:
            all_pass = False
    print("=" * 60)
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
