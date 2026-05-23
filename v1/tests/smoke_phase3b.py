"""
Phase 3b smoke test - drive `python -m engine init` end-to-end against a
throwaway project directory and assert the install footprint matches the
Phase 3b spec:

  1. .claude/hooks/cbim_*.py present + 0755; .claude/hooks/_lib/ present.
  2. .claude/settings.json hooks section uses .claude/hooks/cbim_*.py commands
     (NO `.cbim/run hook ...` survivors). SessionStart has 2 commands.
  3. .claude/settings.json permissions.deny contains the 4 expected entries.
  4. .claudeignore contains `.cbim/`.
  5. `mcp` SDK detection path runs (warn-only, never fatal).
  6. Idempotency: second init = identical settings.json, no duplicate deny
     entries, no duplicate hook commands.
  7. Upgrade path: pre-seeded settings.json containing old `.cbim/run hook`
     commands gets fully rewritten; permissions.deny gains the 2 new entries
     without duplicating the old 2.
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
KERNEL_SRC = HERE.parent / "kernel"


HOOK_SCRIPTS = (
    "cbim_session_start.py",
    "cbim_stop.py",
    "cbim_session_end.py",
    "cbim_user_prompt_submit.py",
    "cbim_pre_tool_use.py",
    "cbim_post_tool_use.py",
    "cbim_auto_preview.py",
)

EXPECTED_DENY = {
    "Write(.cbim/**)",
    "Edit(.cbim/**)",
    "Read(.cbim/**)",
    "Bash(.cbim/run *)",
}


def _run_init(project_root: Path) -> tuple[int, str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(KERNEL_SRC) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, "-m", "engine", "init"],
        capture_output=True,
        cwd=str(project_root),
        env=env,
        timeout=60,
    )
    return proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr.decode("utf-8", "replace")


def _check_install(project_root: Path, results: dict, prefix: str) -> None:
    hooks_dir = project_root / ".claude" / "hooks"

    # 1. hook scripts present + executable
    for name in HOOK_SCRIPTS:
        p = hooks_dir / name
        exists = p.is_file()
        results[f"{prefix}.hook.{name}.exists"] = exists
        if exists:
            mode = p.stat().st_mode & 0o777
            results[f"{prefix}.hook.{name}.mode_0755"] = (mode == 0o755)

    # 2. _lib present
    lib_dir = hooks_dir / "_lib"
    results[f"{prefix}.hook._lib.exists"] = lib_dir.is_dir()
    if lib_dir.is_dir():
        for name in ("paths.py", "bridge.py", "event_io.py", "__init__.py"):
            results[f"{prefix}.hook._lib.{name}"] = (lib_dir / name).is_file()

    # 3. settings.json shape
    settings_path = project_root / ".claude" / "settings.json"
    results[f"{prefix}.settings.exists"] = settings_path.is_file()
    if not settings_path.is_file():
        return
    settings = json.loads(settings_path.read_text(encoding="utf-8"))

    hooks = settings.get("hooks", {})
    raw = json.dumps(hooks)
    results[f"{prefix}.settings.no_legacy_cbim_run_hook"] = (".cbim/run hook" not in raw)

    # SessionStart array shape: [{ "hooks": [{type, command}, {type, command}] }]
    ss = hooks.get("SessionStart", [])
    ss_cmds = []
    if ss and isinstance(ss, list):
        ss_cmds = [h.get("command") for h in (ss[0].get("hooks") or [])]
    results[f"{prefix}.settings.SessionStart.has_two_cmds"] = (
        len(ss_cmds) == 2
        and ".claude/hooks/cbim_session_start.py" in ss_cmds
        and ".claude/hooks/cbim_auto_preview.py" in ss_cmds
    )

    # Each single-cmd hook event
    for event, script in (
        ("Stop", "cbim_stop.py"),
        ("SessionEnd", "cbim_session_end.py"),
        ("UserPromptSubmit", "cbim_user_prompt_submit.py"),
        ("PreToolUse", "cbim_pre_tool_use.py"),
        ("PostToolUse", "cbim_post_tool_use.py"),
    ):
        arr = hooks.get(event, [])
        cmd = None
        if arr and isinstance(arr, list):
            inner = arr[0].get("hooks") or []
            if inner:
                cmd = inner[0].get("command")
        results[f"{prefix}.settings.{event}.cmd"] = (cmd == f".claude/hooks/{script}")

    # 4. permissions.deny
    deny = settings.get("permissions", {}).get("deny", [])
    deny_set = set(deny)
    results[f"{prefix}.settings.deny.has_all_four"] = EXPECTED_DENY.issubset(deny_set)
    # no duplicates
    results[f"{prefix}.settings.deny.no_dupes"] = (len(deny) == len(deny_set))

    # 5. .claudeignore contains .cbim/
    ci = project_root / ".claudeignore"
    results[f"{prefix}.claudeignore.has_cbim"] = (
        ci.is_file() and ".cbim/" in ci.read_text(encoding="utf-8")
    )


def _scenario_fresh(results: dict) -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="cbim-3b-fresh-"))
    try:
        code, out, err = _run_init(tmpdir)
        results["fresh.init.exit_zero"] = (code == 0)
        combined = out + err
        results["fresh.init.mcp_probe_ran"] = (
            "mcp` SDK" in combined
            or "mcp` Python SDK" in combined
            or "verified `mcp`" in combined
        )
        _check_install(tmpdir, results, "fresh")

        # Idempotency: second run
        code2, out2, err2 = _run_init(tmpdir)
        results["fresh.init2.exit_zero"] = (code2 == 0)

        settings_path = tmpdir / ".claude" / "settings.json"
        snapshot_before = settings_path.read_text(encoding="utf-8")
        # Re-run a third time and confirm byte-identical
        code3, _, _ = _run_init(tmpdir)
        results["fresh.init3.exit_zero"] = (code3 == 0)
        snapshot_after = settings_path.read_text(encoding="utf-8")
        results["fresh.idempotent.settings_unchanged"] = (snapshot_before == snapshot_after)

        # Hooks dir still clean
        _check_install(tmpdir, results, "fresh_after_repeat")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _scenario_upgrade(results: dict) -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="cbim-3b-upgrade-"))
    try:
        # Pre-seed the project as if it had been installed by an older kernel:
        #   - .claude/settings.json with `.cbim/run hook ...` commands
        #   - permissions.deny with the old 2 entries only
        #   - an existing .claudeignore with only `.cbim/`
        (tmpdir / ".claude").mkdir(parents=True)
        legacy_settings = {
            "hooks": {
                "SessionStart": [
                    {"hooks": [{"type": "command", "command": ".cbim/run hook session-start"}]}
                ],
                "UserPromptSubmit": [
                    {"hooks": [{"type": "command", "command": ".cbim/run hook log-prompt"}]}
                ],
            },
            "permissions": {
                "defaultMode": "bypassPermissions",
                "deny": ["Write(.cbim/**)", "Edit(.cbim/**)"],
            },
            "userCustomField": "should-survive",
        }
        (tmpdir / ".claude" / "settings.json").write_text(
            json.dumps(legacy_settings, indent=2) + "\n", encoding="utf-8"
        )
        (tmpdir / ".claudeignore").write_text(".cbim/\n", encoding="utf-8")

        code, out, err = _run_init(tmpdir)
        results["upgrade.init.exit_zero"] = (code == 0)
        _check_install(tmpdir, results, "upgrade")

        # Verify user custom field survived
        settings = json.loads((tmpdir / ".claude" / "settings.json").read_text(encoding="utf-8"))
        results["upgrade.user_field_preserved"] = (
            settings.get("userCustomField") == "should-survive"
        )

        # Verify no .cbim/run hook command survived anywhere
        raw = json.dumps(settings.get("hooks", {}))
        results["upgrade.no_legacy_hook_cmd"] = (".cbim/run hook" not in raw)

        # Verify permissions.deny has all 4, no duplicates of the old 2
        deny = settings.get("permissions", {}).get("deny", [])
        results["upgrade.deny.all_four_no_dupes"] = (
            set(deny) == EXPECTED_DENY and len(deny) == 4
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main() -> int:
    results: dict = {}
    _scenario_fresh(results)
    _scenario_upgrade(results)

    print()
    print("=" * 64)
    all_pass = True
    for k in sorted(results):
        v = results[k]
        mark = "PASS" if v else "FAIL"
        print(f"  [{mark}] {k}")
        if not v:
            all_pass = False
    print("=" * 64)
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
