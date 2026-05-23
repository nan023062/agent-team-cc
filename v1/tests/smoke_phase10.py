"""
Phase 10 smoke test — verify the 4 runtime MCP tools and the 6 slash
command files use the expected wire shape.

Tests run in-process: we exercise the tool callables directly (no live
MCP transport, no actual dashboard subprocess execution end-to-end).
The dashboard tool is tested for its return shape, not for actually
opening a browser — that's a UX concern, not a contract concern.

Run:
    PYTHONPATH=v1/kernel python3 v1/tests/smoke_phase10.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
KERNEL_SRC = HERE.parent / "kernel"
COMMANDS_SRC = KERNEL_SRC / "project" / "commands"

# Ensure kernel modules import (mirrors conftest behaviour for direct runs).
if str(KERNEL_SRC) not in sys.path:
    sys.path.insert(0, str(KERNEL_SRC))

# Stand up the registration shim against a lightweight fake mcp instance:
# we don't need FastMCP for the contract check — we only need to capture
# the tool callables that `runtime.register(mcp)` decorates.
from mcp_server.tools import runtime  # noqa: E402


class _FakeMCP:
    def __init__(self) -> None:
        self.tools: dict = {}

    def tool(self):
        def deco(fn):
            self.tools[fn.__name__] = fn
            return fn
        return deco


# ---------------------------------------------------------------------------

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    status = "PASS" if ok else "FAIL"
    line = f"  [{status}] {name}"
    if detail and not ok:
        line += f" - {detail}"
    print(line)


def _seed_project(tmp: Path) -> None:
    """Create the bare minimum .cbim/ layout for a project root."""
    (tmp / ".cbim").mkdir(parents=True, exist_ok=True)
    (tmp / ".cbim" / "logs").mkdir(parents=True, exist_ok=True)
    (tmp / ".cbim" / "dashboard" / ".run").mkdir(parents=True, exist_ok=True)


def _load_json(s: str) -> dict:
    return json.loads(s)


def main() -> int:
    mcp = _FakeMCP()
    runtime.register(mcp)

    expected = {
        "dashboard_ensure_running",
        "debug_get",
        "debug_set",
        "log_show",
    }
    got = set(mcp.tools.keys())
    check(
        "all 4 runtime tools registered",
        expected == got,
        f"missing={expected - got} extra={got - expected}",
    )

    with tempfile.TemporaryDirectory(prefix="cbim_phase10_") as raw:
        tmp = Path(raw).resolve()
        _seed_project(tmp)
        cwd = str(tmp)

        # ----- debug_set on -----
        flag_path = tmp / ".cbim" / ".debug"
        out = _load_json(mcp.tools["debug_set"]("on", cwd=cwd))
        check("debug_set on returns ok", out.get("ok") is True)
        check("debug_set on creates flag file", flag_path.exists())
        check("debug_set on reports enabled=True", out.get("enabled") is True)

        # ----- debug_get reflects True -----
        out = _load_json(mcp.tools["debug_get"](cwd=cwd))
        check("debug_get after on reports enabled=True", out.get("enabled") is True)

        # ----- debug_set off -----
        out = _load_json(mcp.tools["debug_set"]("off", cwd=cwd))
        check("debug_set off returns ok", out.get("ok") is True)
        check("debug_set off removes flag file", not flag_path.exists())
        check("debug_set off reports enabled=False", out.get("enabled") is False)

        # ----- debug_set idempotency: off when already off -----
        out = _load_json(mcp.tools["debug_set"]("off", cwd=cwd))
        check("debug_set off (idempotent)", out.get("enabled") is False)

        # ----- debug_set invalid -----
        out = _load_json(mcp.tools["debug_set"]("toggle", cwd=cwd))
        check("debug_set rejects invalid state", "error" in out)

        # ----- log_show with no log file -----
        out = _load_json(mcp.tools["log_show"](10, cwd=cwd))
        check(
            "log_show returns empty when no log file",
            out.get("session_log") == "" and out.get("session_file") == "",
        )

        # ----- log_show with a fake session log -----
        log_path = tmp / ".cbim" / "logs" / "session_20260523_120000.log"
        body = "".join(f"line {i}\n" for i in range(1, 101))
        log_path.write_text(body, encoding="utf-8")

        out = _load_json(mcp.tools["log_show"](5, cwd=cwd))
        check(
            "log_show returns session_file name",
            out.get("session_file") == log_path.name,
        )
        tail_lines = out.get("session_log", "").splitlines()
        check(
            "log_show honours lines=5",
            tail_lines == [f"line {i}" for i in range(96, 101)],
            f"got {tail_lines!r}",
        )

        # log_show respects .current pointer when present
        other = tmp / ".cbim" / "logs" / "session_20260101_000000.log"
        other.write_text("old\n", encoding="utf-8")
        (tmp / ".cbim" / "logs" / ".current").write_text(
            str(log_path), encoding="utf-8"
        )
        out = _load_json(mcp.tools["log_show"](2, cwd=cwd))
        check(
            "log_show prefers .current pointer over newest",
            out.get("session_file") == log_path.name,
        )

        # ----- dashboard_ensure_running on a clean project -----
        # Cannot actually spawn (no kernel CLI is available inside tmp,
        # python -m engine would fail to find PYTHONPATH). We do the
        # spawn anyway because Popen returns before the child fails;
        # what we check is contract shape, not child liveness.
        os.environ["CI"] = "1"  # disable browser auto-open
        out = _load_json(
            mcp.tools["dashboard_ensure_running"](cwd=cwd)
        )
        check(
            "dashboard_ensure_running returns url field",
            isinstance(out.get("url"), str) and out["url"].startswith("http://"),
            f"got {out!r}",
        )
        check(
            "dashboard_ensure_running returns started=True on fresh project",
            out.get("started") is True,
        )

        # ----- dashboard_ensure_running idempotent on stale pid file -----
        # Simulate a stale pid file (process not alive) and verify the
        # tool detects it and re-launches rather than returning the stale pid.
        pid_path = tmp / ".cbim" / "dashboard" / ".run" / ".preview.pid"
        pid_path.write_text(
            json.dumps({"pid": 999999, "port": 8765}), encoding="utf-8"
        )
        out = _load_json(
            mcp.tools["dashboard_ensure_running"](cwd=cwd)
        )
        check(
            "dashboard_ensure_running detects stale pid and re-launches",
            out.get("started") is True,
        )
        check(
            "dashboard_ensure_running cleans up stale pid file",
            not pid_path.exists() or _load_json(pid_path.read_text())["pid"] != 999999,
        )

    # ---------------------------------------------------------------
    # Slash command frontmatter contract: the 3 rewritten commands must
    # list the right `allowed-tools`; the doc-only fixes must not have
    # introduced stale `.cbim/xxx/` legacy paths.
    # ---------------------------------------------------------------

    expectations = {
        "cbim_dashboard.md": ["mcp__cbim__dashboard_ensure_running"],
        "cbim_debug.md": ["mcp__cbim__debug_get", "mcp__cbim__debug_set"],
        "cbim_log.md": ["mcp__cbim__log_show"],
    }
    for cmd, must_contain in expectations.items():
        path = COMMANDS_SRC / cmd
        text = path.read_text(encoding="utf-8")
        # Frontmatter is the first --- block
        head = text.split("---", 2)[1] if text.startswith("---") else ""
        missing = [t for t in must_contain if t not in head]
        check(
            f"{cmd} frontmatter declares {must_contain}",
            not missing,
            f"missing {missing}",
        )

    # No `cbim debug on/off/status` shell-out and no `auto_preview.py`
    # references in the rewritten commands.
    for cmd in ("cbim_dashboard.md", "cbim_debug.md", "cbim_log.md"):
        text = (COMMANDS_SRC / cmd).read_text(encoding="utf-8")
        check(
            f"{cmd} does not shell out to global `cbim debug`",
            "cbim debug" not in text,
        )
        check(
            f"{cmd} does not reference auto_preview.py",
            "auto_preview.py" not in text,
        )

    # cbim_sched.md and cbim_help.md no longer mention legacy
    # `.cbim/mcp_server/` or `.cbim/cbi/skills/` paths.
    sched = (COMMANDS_SRC / "cbim_sched.md").read_text(encoding="utf-8")
    check(
        "cbim_sched.md uses .cbim/kernel/mcp_server path",
        ".cbim/kernel/mcp_server" in sched,
    )
    check(
        "cbim_sched.md does not mention legacy .cbim/mcp_server path",
        ".cbim/mcp_server" not in sched.replace(".cbim/kernel/mcp_server", ""),
    )

    helpmd = (COMMANDS_SRC / "cbim_help.md").read_text(encoding="utf-8")
    check(
        "cbim_help.md does not reference legacy .cbim/cbi/skills",
        ".cbim/cbi/skills" not in helpmd,
    )
    check(
        "cbim_help.md does not reference legacy .cbim/index.md",
        ".cbim/index.md" not in helpmd,
    )

    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    print(f"\n[phase10] {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
