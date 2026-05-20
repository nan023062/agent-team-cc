"""
install/cli.py — CBIM legacy one-shot installer.

Prefer the copy-based install documented in INSTALL.md at the repo root.
This script is kept for users who want a one-command install:

    python install/install.py            # from repo root

Steps:
  1. Create .venv (no required dependencies — FileBackend uses stdlib only)
  2. Copy <repo>/.cbim/  ->  <target>/.cbim/  (framework files at install destination)
  3. Materialize core agent .md files into .claude/agents/
  4. Merge hooks + permissions into .claude/settings.json
  5. Bootstrap CLAUDE.md, memory store, .dna/index.md, .gitignore, .claudeignore
"""

import argparse
import subprocess
import sys
from pathlib import Path


def _h(text: str) -> None:
    print(f"\n  {text}")


def _ok(text: str) -> None:
    print(f"    + {text}")


def _skip(text: str) -> None:
    print(f"    - {text}  (skipped)")


def _venv_python(root: Path) -> str:
    for p in [root / ".venv/Scripts/python.exe", root / ".venv/bin/python"]:
        if p.exists():
            return str(p)
    return sys.executable


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--root", default=None, help="Target project root (default: repo root containing install/)")
    args, _ = parser.parse_known_args()

    # Locate source .cbim/ and project root.
    # cli.py lives at <repo>/install/cli.py; .cbim/ is at <repo>/.cbim/.
    repo_root = Path(__file__).resolve().parent.parent
    cbim_src = repo_root / ".cbim"
    root = Path(args.root).resolve() if args.root else repo_root

    print()
    print("=" * 52)
    print("  CBIM  —  Capability-Business Independence + Memory")
    print("=" * 52)

    try:
        _step_venv(root)
        cbim_dst = _step_copy(cbim_src, root)
        _step_install_deps(root)  # must run after copy (needs .cbim/mcp_server/)
        _step_agents(root)
        _step_hooks(root)
        _step_bootstrap(cbim_dst, root)
    except Exception as exc:  # noqa: BLE001
        print(f"\n  ERROR: {exc}")
        return 1

    print()
    print("=" * 52)
    print("  Done. Restart Claude Code to activate hooks.")
    print("=" * 52)
    print()

    if sys.platform == "win32":
        import time
        time.sleep(4)
    return 0


def _step_venv(root: Path) -> None:
    _h("[1/5] Virtual environment")
    venv = root / ".venv"
    if venv.exists():
        _skip(".venv already exists")
    else:
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
        _ok("created .venv")


def _step_install_deps(root: Path) -> None:
    _h("[2a/5] Dependencies (MCP SDK)")
    venv = root / ".venv"
    pip = venv / ("Scripts/pip.exe" if sys.platform == "win32" else "bin/pip")
    req = root / ".cbim" / "mcp_server" / "requirements.txt"
    if not pip.exists():
        _skip("no .venv/pip — skipping MCP SDK install")
        return
    if not req.exists():
        _skip(f"{req.relative_to(root)} missing — skipping MCP SDK install")
        return
    try:
        subprocess.run(
            [str(pip), "install", "-q", "-r", str(req)],
            check=True,
        )
        _ok(f"installed MCP SDK from {req.relative_to(root)}")
    except subprocess.CalledProcessError as exc:
        print(f"    ! pip install failed (rc={exc.returncode}); MCP server will not start")


def _step_copy(cbim_src: Path, root: Path) -> Path:
    from .steps.bootstrap import copy_framework

    _h("[2b/5] Framework  ->  .cbim/")
    return copy_framework(cbim_src, root)


def _step_agents(root: Path) -> None:
    from .steps.agents import install_agents

    _h("[3/5] Agents  ->  .claude/agents/")
    install_agents(root)


def _step_hooks(root: Path) -> None:
    from .steps.hooks import install_settings

    _h("[4/5] Claude Code hooks  ->  .claude/settings.json")
    install_settings(root)


def _step_bootstrap(cbim_dst: Path, root: Path) -> None:
    from .steps.bootstrap import (
        write_claude_md, ensure_store, ensure_config, ensure_registry,
        update_gitignore, update_claudeignore,
    )

    _h("[5/5] CLAUDE.md  +  config  +  .gitignore  +  .claudeignore  +  memory store  +  registry")
    write_claude_md(root)
    ensure_store(cbim_dst)
    ensure_config(root)
    ensure_registry(cbim_dst, root)
    update_gitignore(root)
    update_claudeignore(root)
