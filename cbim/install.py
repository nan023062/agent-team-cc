#!/usr/bin/env python3
"""
install.py — CBIM one-shot installer.

Run from anywhere — the script locates itself and the project root automatically.

    python cbim/install.py          # from project root
    python install.py               # from inside cbim/

Steps:
  1. Create .venv  +  install memory engine dependencies
  2. Copy cbim/agents/  →  .claude/agents/
  3. Add Claude Code hooks to .claude/settings.json
  4. Bootstrap CLAUDE.md with cbim/CLAUDE-template.md
  5. Create cbim/memory/store/{short,medium}/  +  update .gitignore
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

CBIM = Path(__file__).resolve().parent   # cbim/
ROOT = CBIM.parent                       # project root (where .venv will live)
CC   = CBIM / "cc-template"             # Claude Code install sources


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _h(text: str) -> None:
    print(f"\n  {text}")

def _ok(text: str) -> None:
    print(f"    + {text}")

def _skip(text: str) -> None:
    print(f"    - {text}  (skipped)")

def _venv_python() -> str:
    for p in [ROOT / ".venv/Scripts/python.exe", ROOT / ".venv/bin/python"]:
        if p.exists():
            return str(p)
    return sys.executable


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

def step_venv() -> None:
    _h("[1/5] Virtual environment")
    venv = ROOT / ".venv"
    if venv.exists():
        _skip(".venv already exists")
    else:
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
        _ok("Created .venv")

    _h("[2/5] Dependencies")
    # Default memory backend (FileBackend) uses only stdlib — no pip install needed.
    # Optional: install chromadb for semantic search (see cbim/memory/engine/requirements.txt).
    _ok("No required dependencies (FileBackend uses stdlib only)")


def step_agents() -> None:
    _h("[3/5] Agents  →  .claude/agents/")
    src = CC / "agents"
    dst = ROOT / ".claude" / "agents"
    dst.mkdir(parents=True, exist_ok=True)
    if not src.exists():
        _skip("cbim/cc-template/agents/ not found")
        return
    for item in sorted(src.iterdir()):
        target = dst / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(str(target))
                shutil.copytree(str(item), str(target))
                print(f"    * {item.name}  (updated)")
            else:
                shutil.copytree(str(item), str(target))
                _ok(item.name)
        else:
            if target.exists():
                shutil.copy2(str(item), str(target))
                print(f"    * {item.name}  (updated)")
            else:
                shutil.copy2(str(item), str(target))
                _ok(item.name)


def step_hooks() -> None:
    _h("[4/5] Claude Code hooks  →  .claude/settings.json")
    settings_path = ROOT / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8")) \
            if settings_path.exists() else {}
    except json.JSONDecodeError:
        settings = {}

    hooks = settings.setdefault("hooks", {})

    def _add(event: str, command: str) -> bool:
        entries = hooks.setdefault(event, [])
        exists = any(
            h.get("command") == command
            for entry in entries
            for h in entry.get("hooks", [])
        )
        if not exists:
            entries.append({"hooks": [{"type": "command", "command": command}]})
        return not exists

    added = []
    if _add("Stop",         "python cbim/cc-template/hooks/write-memory.py"): added.append("Stop → write-memory")
    if _add("SessionStart", "python cbim/cc-template/hooks/load-memory.py"):  added.append("SessionStart → load-memory")

    # permissions.deny — block direct file access to cbim/ and .dna/ directories
    deny_rules = [
        "Read(cbim/**)", "Read(**/.dna/**)",
        "Glob(cbim/**)", "Glob(**/.dna/**)",
        "Grep(cbim/**)", "Grep(**/.dna/**)",
    ]
    deny_list = settings.setdefault("permissions", {}).setdefault("deny", [])
    new_rules = [r for r in deny_rules if r not in deny_list]
    deny_list.extend(new_rules)

    settings_path.write_text(
        json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    for h in added:
        _ok(h)
    if not added:
        _skip("hooks already configured")
    if new_rules:
        _ok(f"permissions.deny ← {', '.join(new_rules)}")
    else:
        _skip("permissions.deny already configured")


def step_bootstrap() -> None:
    _h("[5/5] CLAUDE.md  +  .gitignore  +  .claudeignore  +  memory store")

    # CLAUDE.md
    src = CC / "CLAUDE-template.md"
    dst = ROOT / "CLAUDE.md"
    if src.exists():
        content = src.read_text(encoding="utf-8")
        if dst.exists():
            existing = dst.read_text(encoding="utf-8")
            if "cbim" in existing.lower():
                _skip("CLAUDE.md already references cbim")
            else:
                dst.write_text(existing.rstrip() + "\n\n" + content, encoding="utf-8")
                _ok("Appended cbim section to CLAUDE.md")
        else:
            shutil.copy2(str(src), str(dst))
            _ok("Created CLAUDE.md")

    # memory store dirs
    for d in ["short", "medium"]:
        (CBIM / "memory" / "store" / d).mkdir(parents=True, exist_ok=True)
    _ok("cbim/memory/store/{short,medium}/ ready")

    # .gitignore
    gitignore = ROOT / ".gitignore"
    needed = ["cbim/memory/store/", "__pycache__/", "*.pyc", ".venv/"]
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    missing = [e for e in needed if e not in existing]
    if missing:
        with gitignore.open("a", encoding="utf-8") as f:
            if existing and not existing.endswith("\n"):
                f.write("\n")
            f.write("\n".join(missing) + "\n")
        _ok(f".gitignore ← {', '.join(missing)}")
    else:
        _skip(".gitignore already up to date")

    # .claudeignore — keep cbim/ and .dna/ out of agent file searches
    claudeignore = ROOT / ".claudeignore"
    ci_needed = ["cbim/", "**/.dna/"]
    ci_existing = claudeignore.read_text(encoding="utf-8") if claudeignore.exists() else ""
    ci_missing = [e for e in ci_needed if e not in ci_existing]
    if ci_missing:
        with claudeignore.open("a", encoding="utf-8") as f:
            if not ci_existing:
                f.write("# CBIM framework files — access via skill Python scripts only\n")
            elif not ci_existing.endswith("\n"):
                f.write("\n")
            f.write("\n".join(ci_missing) + "\n")
        _ok(f".claudeignore ← {', '.join(ci_missing)}")
    else:
        _skip(".claudeignore already up to date")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print()
    print("=" * 52)
    print("  CBIM  —  Capability-Business Independence + Memory")
    print("=" * 52)

    try:
        step_venv()
        step_agents()
        step_hooks()
        step_bootstrap()
    except Exception as exc:
        print(f"\n  ERROR: {exc}")
        sys.exit(1)

    print()
    print("=" * 52)
    print("  Done. Restart Claude Code to activate hooks.")
    print("=" * 52)
    print()

    if sys.platform == "win32":
        import time
        time.sleep(4)
