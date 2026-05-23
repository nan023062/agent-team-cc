"""
Phase 7 smoke test — verify the .mcp.json split.

`mcpServers.cbim` previously lived inside `.claude/settings.json`. As of
Phase 7 it lives at the project-root `.mcp.json` so Claude Code auto-
discovers it. Init writes `.mcp.json`; sync (and re-init) drops the stale
`mcpServers.cbim` from `.claude/settings.json` on upgrade.

Three scenarios:
  A. Clean project — init writes .mcp.json with cbim; settings.json has
     no mcpServers.
  B. Legacy upgrade — pre-existing settings.json has mcpServers.cbim;
     no .mcp.json. After init, settings has no mcpServers.cbim, and
     .mcp.json has cbim.
  C. Mixed user state — settings has mcpServers.cbim + mcpServers.other;
     .mcp.json pre-exists with mcpServers.another. After init,
     settings's mcpServers retains only `other`, and .mcp.json merges
     cbim + another.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
KERNEL_SRC = HERE.parent / "kernel"


def _run_init(tmp: Path) -> None:
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


def _read_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(p: Path, data: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _assert(cond: bool, msg: str, results: list[tuple[bool, str]]) -> None:
    results.append((cond, msg))
    marker = "PASS" if cond else "FAIL"
    print(f"  [{marker}] {msg}")


def scenario_a(results: list[tuple[bool, str]]) -> None:
    print("Scenario A — clean project:")
    with tempfile.TemporaryDirectory(prefix="cbim_p7a_") as raw:
        tmp = Path(raw)
        _run_init(tmp)

        mcp_path = tmp / ".mcp.json"
        settings_path = tmp / ".claude" / "settings.json"

        _assert(mcp_path.exists(), ".mcp.json exists", results)
        mcp = _read_json(mcp_path)
        cbim = mcp.get("mcpServers", {}).get("cbim", {})
        _assert(cbim.get("command") == ".cbim/run", "mcp.json mcpServers.cbim.command == '.cbim/run'", results)
        _assert(cbim.get("args") == ["mcp"], "mcp.json mcpServers.cbim.args == ['mcp']", results)

        _assert(settings_path.exists(), ".claude/settings.json exists", results)
        settings = _read_json(settings_path)
        mcp_servers = settings.get("mcpServers")
        no_cbim_in_settings = (mcp_servers is None) or ("cbim" not in mcp_servers)
        _assert(no_cbim_in_settings, "settings.json has no mcpServers.cbim", results)


def scenario_b(results: list[tuple[bool, str]]) -> None:
    print("Scenario B — legacy upgrade:")
    with tempfile.TemporaryDirectory(prefix="cbim_p7b_") as raw:
        tmp = Path(raw)
        legacy_settings = {
            "mcpServers": {
                "cbim": {
                    "command": ".cbim/run",
                    "args": ["mcp"],
                }
            },
            "permissions": {"deny": []},
        }
        _write_json(tmp / ".claude" / "settings.json", legacy_settings)

        _run_init(tmp)

        mcp_path = tmp / ".mcp.json"
        settings_path = tmp / ".claude" / "settings.json"

        _assert(mcp_path.exists(), ".mcp.json exists after upgrade", results)
        mcp = _read_json(mcp_path)
        _assert("cbim" in mcp.get("mcpServers", {}), "mcp.json has mcpServers.cbim", results)

        settings = _read_json(settings_path)
        mcp_servers = settings.get("mcpServers")
        no_cbim = (mcp_servers is None) or ("cbim" not in mcp_servers)
        _assert(no_cbim, "legacy mcpServers.cbim removed from settings.json", results)
        empty_or_absent = (mcp_servers is None) or (mcp_servers == {})
        _assert(empty_or_absent, "no other servers in settings, so mcpServers field removed or empty", results)


def scenario_c(results: list[tuple[bool, str]]) -> None:
    print("Scenario C — mixed user state:")
    with tempfile.TemporaryDirectory(prefix="cbim_p7c_") as raw:
        tmp = Path(raw)
        legacy_settings = {
            "mcpServers": {
                "cbim": {"command": ".cbim/run", "args": ["mcp"]},
                "other-server": {"command": "/usr/bin/other", "args": []},
            },
            "permissions": {"deny": []},
        }
        _write_json(tmp / ".claude" / "settings.json", legacy_settings)

        pre_mcp = {
            "mcpServers": {
                "another-server": {"command": "/usr/bin/another", "args": ["--foo"]},
            }
        }
        _write_json(tmp / ".mcp.json", pre_mcp)

        _run_init(tmp)

        settings = _read_json(tmp / ".claude" / "settings.json")
        mcp_servers_in_settings = settings.get("mcpServers", {})
        _assert("cbim" not in mcp_servers_in_settings, "cbim removed from settings.mcpServers", results)
        _assert("other-server" in mcp_servers_in_settings, "user's other-server preserved in settings.mcpServers", results)

        mcp = _read_json(tmp / ".mcp.json")
        servers = mcp.get("mcpServers", {})
        _assert("cbim" in servers, ".mcp.json has cbim", results)
        _assert("another-server" in servers, ".mcp.json retains pre-existing another-server", results)
        _assert(servers.get("another-server", {}).get("command") == "/usr/bin/another",
                ".mcp.json another-server.command preserved unchanged", results)


def main() -> int:
    results: list[tuple[bool, str]] = []
    scenario_a(results)
    scenario_b(results)
    scenario_c(results)

    passed = sum(1 for ok, _ in results if ok)
    total = len(results)
    print()
    print(f"phase7_smoke: {passed}/{total} assertions passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
