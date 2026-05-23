"""
Phase 9c smoke test — verify install/sync's unified rule:
built-in items are ALWAYS overwritten, user-created items are NEVER touched.

Scenario:
  1. Fresh init into an empty tmp project.
  2. Mutate every cbim built-in file (agents, commands, hooks) so we can
     detect that a second init refreshes them.
  3. Inject user-owned artifacts on all 5 surfaces:
        - .claude/agents/my_agent/my_agent.md
        - .claude/commands/my_command.md
        - .claude/hooks/my_custom_hook.py
        - .claude/settings.json: add a user entry inside SessionStart's hooks
          group, add an entire `OnSave` event, add a custom deny pattern
        - .mcp.json: add a user MCP server
  4. Re-run init.
  5. Assert:
        - every built-in agent / command / hook is back to template content
        - every user-owned artifact is byte-identical and mtime-identical
        - settings.json: SessionStart still has user entry; OnSave still
          present untouched; cbim hook entries refreshed; deny has all 4
          cbim patterns + the user pattern
        - .mcp.json: both `cbim` and `my_server` present
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
TEMPLATES = KERNEL_SRC / "project" / "templates"
AGENTS_SRC = KERNEL_SRC / "project" / "agents"
COMMANDS_SRC = KERNEL_SRC / "project" / "commands"
HOOKS_SRC = KERNEL_SRC / "project" / "hooks_src"

AGENT_NAMES = ("architect", "auditor", "hr", "programmer")
COMMAND_NAMES = (
    "cbim_dashboard", "cbim_debug", "cbim_help",
    "cbim_install", "cbim_log", "cbim_sched",
)
HOOK_NAMES = (
    "cbim_session_start.py", "cbim_stop.py", "cbim_session_end.py",
    "cbim_user_prompt_submit.py", "cbim_pre_tool_use.py",
    "cbim_post_tool_use.py", "cbim_auto_preview.py",
)
CBIM_DENY = (
    "Write(.cbim/**)", "Edit(.cbim/**)",
    "Read(.cbim/**)", "Bash(.cbim/run *)",
)
USER_DENY = "Bash(rm -rf /)"


def _stage_kernel(tmp: Path) -> None:
    dst = tmp / ".cbim" / "kernel"
    if dst.exists():
        shutil.rmtree(dst)

    def _ignore(_dir: str, names: list[str]) -> list[str]:
        return [n for n in names if n in ("__pycache__", ".pytest_cache")]

    shutil.copytree(KERNEL_SRC, dst, ignore=_ignore)


def _run_init(tmp: Path) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(KERNEL_SRC) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, "-m", "engine", "init"],
        capture_output=True, cwd=str(tmp), env=env, timeout=180,
    )
    if proc.returncode != 0:
        raise SystemExit(
            f"init failed: stdout={proc.stdout.decode()!r} stderr={proc.stderr.decode()!r}"
        )


# ---------------------------------------------------------------------------

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    status = "PASS" if ok else "FAIL"
    line = f"  [{status}] {name}"
    if detail and not ok:
        line += f" — {detail}"
    print(line)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cbim_phase9c_") as raw:
        tmp = Path(raw).resolve()
        print(f"[phase9c] working in {tmp}")
        _stage_kernel(tmp)
        print("[phase9c] first init…")
        _run_init(tmp)

        # ----- 2. mutate built-ins so refresh is detectable -----
        for n in AGENT_NAMES:
            (tmp / ".claude" / "agents" / n / f"{n}.md").write_text(
                "MUTATED\n", encoding="utf-8"
            )
        for n in COMMAND_NAMES:
            (tmp / ".claude" / "commands" / f"{n}.md").write_text(
                "MUTATED\n", encoding="utf-8"
            )
        for n in HOOK_NAMES:
            (tmp / ".claude" / "hooks" / n).write_text(
                "#!/usr/bin/env python3\nprint('MUTATED')\n", encoding="utf-8"
            )

        # ----- 3. inject user artifacts -----
        user_agent = tmp / ".claude" / "agents" / "my_agent" / "my_agent.md"
        user_agent.parent.mkdir(parents=True, exist_ok=True)
        user_agent.write_text("USER AGENT CONTENT\n", encoding="utf-8")
        user_agent_mtime = user_agent.stat().st_mtime

        user_cmd = tmp / ".claude" / "commands" / "my_command.md"
        user_cmd.write_text("USER COMMAND CONTENT\n", encoding="utf-8")
        user_cmd_mtime = user_cmd.stat().st_mtime

        user_hook = tmp / ".claude" / "hooks" / "my_custom_hook.py"
        user_hook.write_text(
            "#!/usr/bin/env python3\nprint('user hook')\n", encoding="utf-8"
        )
        os.chmod(user_hook, 0o755)
        user_hook_mtime = user_hook.stat().st_mtime

        # mutate settings.json
        settings_path = tmp / ".claude" / "settings.json"
        s = json.loads(settings_path.read_text(encoding="utf-8"))
        # add user entry to SessionStart's only group
        s["hooks"]["SessionStart"][0]["hooks"].append({
            "type": "command",
            "command": ".claude/hooks/my_custom_hook.py",
        })
        # add a brand-new OnSave event
        s["hooks"]["OnSave"] = [{
            "hooks": [{
                "type": "command",
                "command": ".claude/hooks/user_save_hook.py",
            }]
        }]
        # add a user deny entry
        s["permissions"]["deny"].append(USER_DENY)
        # add a user top-level key
        s["userCustomKey"] = "preserve me"
        settings_path.write_text(
            json.dumps(s, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        # mutate .mcp.json
        mcp_path = tmp / ".mcp.json"
        m = json.loads(mcp_path.read_text(encoding="utf-8"))
        m["mcpServers"]["my_server"] = {
            "command": "node",
            "args": ["my-server.js"],
        }
        mcp_path.write_text(
            json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        print("[phase9c] second init (sync)…")
        _run_init(tmp)

        # ----- 5. assertions -----
        # built-in agents refreshed
        for n in AGENT_NAMES:
            actual = (tmp / ".claude" / "agents" / n / f"{n}.md").read_text(
                encoding="utf-8"
            )
            expected = (AGENTS_SRC / f"{n}.md").read_text(encoding="utf-8")
            check(f"agent {n} refreshed to template", actual == expected)

        # built-in commands refreshed
        for n in COMMAND_NAMES:
            actual = (tmp / ".claude" / "commands" / f"{n}.md").read_text(
                encoding="utf-8"
            )
            expected = (COMMANDS_SRC / f"{n}.md").read_text(encoding="utf-8")
            check(f"command {n} refreshed to template", actual == expected)

        # built-in hooks refreshed
        for n in HOOK_NAMES:
            actual = (tmp / ".claude" / "hooks" / n).read_text(encoding="utf-8")
            expected = (HOOKS_SRC / n).read_text(encoding="utf-8")
            check(f"hook {n} refreshed to template", actual == expected)

        # user artifacts preserved (content + mtime)
        check(
            "user agent content preserved",
            user_agent.read_text(encoding="utf-8") == "USER AGENT CONTENT\n",
        )
        check(
            "user agent mtime preserved",
            user_agent.stat().st_mtime == user_agent_mtime,
        )
        check(
            "user command content preserved",
            user_cmd.read_text(encoding="utf-8") == "USER COMMAND CONTENT\n",
        )
        check(
            "user command mtime preserved",
            user_cmd.stat().st_mtime == user_cmd_mtime,
        )
        check(
            "user hook content preserved",
            user_hook.read_text(encoding="utf-8")
            == "#!/usr/bin/env python3\nprint('user hook')\n",
        )
        check(
            "user hook mtime preserved",
            user_hook.stat().st_mtime == user_hook_mtime,
        )

        # settings.json: surgical merge
        s2 = json.loads(settings_path.read_text(encoding="utf-8"))
        # cbim hook entries present in every cbim-managed event
        for event, expected_cmds in [
            ("SessionStart", [
                ".claude/hooks/cbim_session_start.py",
                ".claude/hooks/cbim_auto_preview.py",
            ]),
            ("SessionEnd", [".claude/hooks/cbim_session_end.py"]),
            ("Stop", [".claude/hooks/cbim_stop.py"]),
            ("UserPromptSubmit", [".claude/hooks/cbim_user_prompt_submit.py"]),
            ("PreToolUse", [".claude/hooks/cbim_pre_tool_use.py"]),
            ("PostToolUse", [".claude/hooks/cbim_post_tool_use.py"]),
        ]:
            groups = s2["hooks"].get(event, [])
            all_cmds = [
                e.get("command")
                for g in groups if isinstance(g, dict)
                for e in g.get("hooks", []) if isinstance(e, dict)
            ]
            ok = all(c in all_cmds for c in expected_cmds)
            check(
                f"settings hooks.{event} contains cbim entries",
                ok,
                f"got {all_cmds}",
            )

        # user entry in SessionStart preserved
        ss_cmds = [
            e.get("command")
            for g in s2["hooks"]["SessionStart"] if isinstance(g, dict)
            for e in g.get("hooks", []) if isinstance(e, dict)
        ]
        check(
            "settings SessionStart preserves my_custom_hook.py",
            ".claude/hooks/my_custom_hook.py" in ss_cmds,
            f"got {ss_cmds}",
        )

        # OnSave preserved verbatim
        on_save = s2["hooks"].get("OnSave")
        expected_onsave = [{
            "hooks": [{
                "type": "command",
                "command": ".claude/hooks/user_save_hook.py",
            }]
        }]
        check("settings OnSave preserved verbatim", on_save == expected_onsave)

        # deny: cbim 4 + user 1
        deny = s2["permissions"]["deny"]
        for pat in CBIM_DENY:
            check(f"deny contains cbim {pat}", pat in deny)
        check(f"deny preserves user {USER_DENY}", USER_DENY in deny)

        # user top-level key preserved
        check(
            "settings userCustomKey preserved",
            s2.get("userCustomKey") == "preserve me",
        )

        # .mcp.json: cbim + my_server both present
        m2 = json.loads(mcp_path.read_text(encoding="utf-8"))
        check("mcp.json has cbim server", "cbim" in m2.get("mcpServers", {}))
        check(
            "mcp.json preserves my_server",
            m2.get("mcpServers", {}).get("my_server", {}).get("command") == "node",
        )

    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    print(f"\n[phase9c] {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
