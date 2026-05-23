"""
Phase 6 smoke test — verify the in-process hook bridges.

For each of the seven `cbim_*.py` hooks installed under `.claude/hooks/`,
feed a minimal event JSON on stdin and assert:
  1. exit code == 0
  2. expected side-effect file appears under `.cbim/`
  3. stderr contains no `[CBIM:hook]` warning (except in the kernel-missing
     fallback scenario, where it MUST appear and the exit code MUST still
     be 0).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
KERNEL_SRC = HERE.parent / "src" / "kernel"


def _install_project(tmp: Path) -> None:
    """Run `python -m engine init` against `tmp`."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(KERNEL_SRC) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, "-m", "engine", "init"],
        capture_output=True,
        cwd=str(tmp),
        env=env,
        timeout=60,
    )
    if proc.returncode != 0:
        raise SystemExit(
            f"init failed: stdout={proc.stdout.decode()!r} stderr={proc.stderr.decode()!r}"
        )


def _stage_kernel(tmp: Path) -> None:
    """Mirror what `/cbim_install` does: copy the kernel tree into `.cbim/kernel/`."""
    dst = tmp / ".cbim" / "kernel"
    if dst.exists():
        shutil.rmtree(dst)

    def _ignore(_dir: str, names: list[str]) -> list[str]:
        return [n for n in names if n in ("__pycache__", ".pytest_cache")]

    shutil.copytree(KERNEL_SRC, dst, ignore=_ignore)


def _run_hook(tmp: Path, script: str, event: dict, timeout: int = 30) -> tuple[int, str, str]:
    p = tmp / ".claude" / "hooks" / script
    proc = subprocess.run(
        [sys.executable, str(p)],
        input=json.dumps(event).encode("utf-8"),
        capture_output=True,
        cwd=str(tmp),
        timeout=timeout,
    )
    return proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr.decode("utf-8", "replace")


def _assert(results: dict, key: str, ok: bool, detail: str = "") -> None:
    results[key] = (ok, detail)


def _check_hooks_present(tmp: Path, results: dict) -> None:
    hooks_dir = tmp / ".claude" / "hooks"
    scripts = (
        "cbim_session_start.py",
        "cbim_stop.py",
        "cbim_session_end.py",
        "cbim_user_prompt_submit.py",
        "cbim_pre_tool_use.py",
        "cbim_post_tool_use.py",
        "cbim_auto_preview.py",
    )
    for s in scripts:
        _assert(results, f"present.{s}", (hooks_dir / s).is_file())
    lib = hooks_dir / "_lib"
    _assert(results, "present._lib.bridge", (lib / "bridge.py").is_file())
    _assert(results, "present._lib.paths", (lib / "paths.py").is_file())
    _assert(results, "present._lib.event_io", (lib / "event_io.py").is_file())
    _assert(
        results, "absent._lib.mcp_client",
        not (lib / "mcp_client.py").exists(),
        "mcp_client.py must be gone after Phase 6",
    )


def _hook_clean(rc: int, stderr: str) -> bool:
    return rc == 0 and "[CBIM:hook]" not in stderr


def _scenario_user_prompt(tmp: Path, results: dict) -> None:
    rc, _, err = _run_hook(
        tmp, "cbim_user_prompt_submit.py",
        {"cwd": str(tmp), "prompt": "hello", "transcript_path": ""},
    )
    _assert(results, "user_prompt.clean", _hook_clean(rc, err), err)
    cc = tmp / ".cbim" / ".cc-status"
    body = cc.read_text(encoding="utf-8") if cc.exists() else ""
    _assert(results, "user_prompt.cc_status_busy", cc.exists() and body.startswith("busy "), body)


def _scenario_pre_tool(tmp: Path, results: dict) -> None:
    rc, _, err = _run_hook(
        tmp, "cbim_pre_tool_use.py",
        {"cwd": str(tmp), "tool_name": "Read",
         "tool_input": {"file_path": "/tmp/x"}, "transcript_path": ""},
    )
    _assert(results, "pre_tool.clean", _hook_clean(rc, err), err)


def _scenario_post_tool(tmp: Path, results: dict) -> None:
    rc, _, err = _run_hook(
        tmp, "cbim_post_tool_use.py",
        {"cwd": str(tmp), "tool_name": "Read",
         "tool_input": {"file_path": "/tmp/x"},
         "tool_response": {"stdout": "ok"}, "transcript_path": ""},
    )
    _assert(results, "post_tool.clean", _hook_clean(rc, err), err)


def _scenario_stop(tmp: Path, results: dict) -> None:
    # transcript empty: distill is skipped but cc-status must still flip to idle
    rc, _, err = _run_hook(
        tmp, "cbim_stop.py",
        {"cwd": str(tmp), "transcript_path": ""},
    )
    _assert(results, "stop.clean", _hook_clean(rc, err), err)
    body = (tmp / ".cbim" / ".cc-status").read_text(encoding="utf-8")
    _assert(results, "stop.cc_status_idle", body.startswith("idle "), body)


def _scenario_session_end(tmp: Path, results: dict) -> None:
    rc, _, err = _run_hook(
        tmp, "cbim_session_end.py",
        {"cwd": str(tmp), "session_id": "smoke-sess", "reason": "user"},
    )
    _assert(results, "session_end.clean", _hook_clean(rc, err), err)


def _scenario_session_start(tmp: Path, results: dict) -> None:
    rc, out, err = _run_hook(
        tmp, "cbim_session_start.py",
        {"cwd": str(tmp), "session_id": "smoke-sess"},
    )
    _assert(results, "session_start.clean", _hook_clean(rc, err), err)

    # additionalContext payload is optional — may be empty when no memory yet.
    if out.strip():
        try:
            payload = json.loads(out)
            ok = (
                isinstance(payload, dict)
                and isinstance(payload.get("hookSpecificOutput"), dict)
                and payload["hookSpecificOutput"].get("hookEventName") == "SessionStart"
                and "additionalContext" in payload["hookSpecificOutput"]
            )
            _assert(results, "session_start.payload_shape", ok, out[:200])
        except json.JSONDecodeError as e:
            _assert(results, "session_start.payload_shape", False, f"{e}: {out[:200]}")
    else:
        _assert(results, "session_start.payload_shape", True, "empty (acceptable)")

    # session log file should exist
    logs = tmp / ".cbim" / "logs"
    has_log = logs.is_dir() and any(p.suffix == ".log" for p in logs.iterdir())
    _assert(results, "session_start.log_created", has_log)


def _scenario_auto_preview(tmp: Path, results: dict) -> None:
    # Disable auto_open so we don't spawn the dashboard during smoke.
    cfg_path = tmp / ".cbim" / "config.json"
    cfg = {}
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cfg = {}
    cfg.setdefault("dashboard", {})["auto_open"] = False
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

    rc, _, err = _run_hook(
        tmp, "cbim_auto_preview.py",
        {"cwd": str(tmp)},
    )
    _assert(results, "auto_preview.clean", _hook_clean(rc, err), err)


def _scenario_kernel_missing(results: dict) -> None:
    """Run a hook when `.cbim/kernel/` is absent — must exit 0 + emit warning."""
    tmp = Path(tempfile.mkdtemp(prefix="cbim-6-nokern-"))
    try:
        _install_project(tmp)
        # Deliberately do NOT stage the kernel.
        rc, _, err = _run_hook(
            tmp, "cbim_user_prompt_submit.py",
            {"cwd": str(tmp), "prompt": "hi", "transcript_path": ""},
        )
        _assert(results, "no_kernel.exit_zero", rc == 0, f"rc={rc}")
        _assert(
            results, "no_kernel.warning_emitted",
            "[CBIM:hook]" in err and "kernel missing" in err,
            err,
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    results: dict[str, tuple[bool, str]] = {}

    tmp = Path(tempfile.mkdtemp(prefix="cbim-6-smoke-"))
    try:
        _install_project(tmp)
        _stage_kernel(tmp)
        _check_hooks_present(tmp, results)

        _scenario_user_prompt(tmp, results)
        _scenario_pre_tool(tmp, results)
        _scenario_post_tool(tmp, results)
        _scenario_session_start(tmp, results)
        _scenario_stop(tmp, results)
        _scenario_session_end(tmp, results)
        _scenario_auto_preview(tmp, results)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    _scenario_kernel_missing(results)

    width = max(len(k) for k in results)
    failed = 0
    for k in sorted(results):
        ok, detail = results[k]
        flag = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
            print(f"{flag}  {k.ljust(width)}  {detail}")
        else:
            print(f"{flag}  {k}")

    print(f"\n{len(results) - failed}/{len(results)} checks passed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
