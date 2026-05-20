"""
agents.py — Materialize the 4 core agent .md files into .claude/agents/.

The contents come from installer/templates/agents.py constants; the installer
no longer copies physical agent files from cc-template/.
"""

from pathlib import Path

from ..templates.agents import ARCHITECT_MD, AUDITOR_MD, HR_MD, PROGRAMMER_MD


_AGENTS = {
    "architect": ARCHITECT_MD,
    "auditor":   AUDITOR_MD,
    "hr":        HR_MD,
    "programmer": PROGRAMMER_MD,
}


def _ok(text: str) -> None:
    print(f"    + {text}")


def install_agents(root: Path) -> None:
    dst_base = root / ".claude" / "agents"
    dst_base.mkdir(parents=True, exist_ok=True)
    for name, content in _AGENTS.items():
        agent_dir = dst_base / name
        agent_dir.mkdir(exist_ok=True)
        md = agent_dir / f"{name}.md"
        if md.exists() and md.read_text(encoding="utf-8") == content:
            print(f"    - {name}.md  (unchanged)")
            continue
        md.write_text(content, encoding="utf-8")
        _ok(f"{name}.md")
