"""`cbim project sync` — refresh kernel-managed project files from templates.

Shared template-copy logic used by `init`, `migrate`, and the standalone
`project sync` command. The rules per file:

| File                                    | Rule                                                           |
|-----------------------------------------|----------------------------------------------------------------|
| CLAUDE.md                               | Always overwrite from template                                 |
| .claude/agents/<name>/<name>.md (x4)    | Always overwrite (only the 4 built-in named agents)            |
| .claude/commands/<name>.md (x6)         | Always overwrite (only the 6 built-in slash commands)          |
| .claude/settings.json                   | Merge: only `hooks`, `permissions.deny`, `permissions.default- |
|                                         | Mode`, `mcpServers` — preserve everything else                  |
| .gitignore                              | Append missing entries only                                    |

Never touched by sync:
- .cbim/config.json                 (pin is updated separately by `cbim update`)
- .cbim/memory/**, .cbim/logs/**, .cbim/.upgrade_cache.json
- .claude/commands/<other>.md       (any slash command not in the built-in 6)
- .claude/agents/<other>/           (any agent not in the built-in 4)
- Any .dna/ directory
"""
from __future__ import annotations

import json
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent
_TEMPLATES = _PKG_DIR / "templates"
_AGENTS = _PKG_DIR / "agents"
_COMMANDS = _PKG_DIR / "commands"

# The four kernel-managed (built-in) agents. Any other agent directory under
# .claude/agents/ is treated as user-owned and never touched.
KERNEL_AGENT_NAMES: tuple[str, ...] = ("architect", "auditor", "hr", "programmer")

# The six kernel-managed (built-in) slash commands. Any other .md file under
# .claude/commands/ is treated as user-owned and never touched.
KERNEL_COMMAND_NAMES: tuple[str, ...] = (
    "cbim_dashboard",
    "cbim_debug",
    "cbim_help",
    "cbim_log",
    "cbim_sched",
    "cbim_update",
)


def _read_template(name: str) -> str:
    return (_TEMPLATES / name).read_text(encoding="utf-8")


def read_template(name: str) -> str:
    """Public accessor for kernel-managed template files."""
    return _read_template(name)


def _rel(path: Path, root: Path) -> str:
    try:
        rel = path.relative_to(root)
    except ValueError:
        rel = path
    return str(rel).replace("\\", "/")


# ---------------------------------------------------------------------------
# Per-file sync primitives. Each returns an action string describing what was
# done (or would be done, when dry_run=True). Returning a falsy string means
# "no action / no-op"; the caller decides whether to print it.
# ---------------------------------------------------------------------------


def sync_claude_md(project_root: Path, dry_run: bool = False) -> str:
    dst = project_root / "CLAUDE.md"
    content = _read_template("CLAUDE.md.tmpl")
    rel = _rel(dst, project_root)

    if dst.exists() and dst.read_text(encoding="utf-8") == content:
        return f"unchanged {rel}"
    verb = "would overwrite" if dry_run else "overwrote"
    if not dst.exists():
        verb = "would create" if dry_run else "created"
    if not dry_run:
        dst.write_text(content, encoding="utf-8")
    return f"{verb} {rel}"


def sync_claudeignore(project_root: Path, dry_run: bool = False) -> str:
    """OWNED file. Overwrite from template on every sync."""
    dst = project_root / ".claudeignore"
    content = _read_template("claudeignore.tmpl")
    rel = _rel(dst, project_root)

    if dst.exists() and dst.read_text(encoding="utf-8") == content:
        return f"unchanged {rel}"
    verb = "would overwrite" if dry_run else "overwrote"
    if not dst.exists():
        verb = "would create" if dry_run else "created"
    if not dry_run:
        dst.write_text(content, encoding="utf-8")
    return f"{verb} {rel}"


def sync_agent(project_root: Path, name: str, dry_run: bool = False) -> str:
    src = _AGENTS / f"{name}.md"
    dst = project_root / ".claude" / "agents" / name / f"{name}.md"
    rel = _rel(dst, project_root)
    content = src.read_text(encoding="utf-8")

    if dst.exists() and dst.read_text(encoding="utf-8") == content:
        return f"unchanged {rel}"
    verb = "would overwrite" if dry_run else "overwrote"
    if not dst.exists():
        verb = "would create" if dry_run else "created"
    if not dry_run:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(content, encoding="utf-8")
    return f"{verb} {rel}"


def sync_agents(project_root: Path, dry_run: bool = False) -> list[str]:
    return [sync_agent(project_root, name, dry_run) for name in KERNEL_AGENT_NAMES]


def sync_command(project_root: Path, name: str, dry_run: bool = False) -> str:
    """OWNED file. Overwrite the built-in slash command from template."""
    src = _COMMANDS / f"{name}.md"
    dst = project_root / ".claude" / "commands" / f"{name}.md"
    rel = _rel(dst, project_root)
    content = src.read_text(encoding="utf-8")

    if dst.exists() and dst.read_text(encoding="utf-8") == content:
        return f"unchanged {rel}"
    verb = "would overwrite" if dry_run else "overwrote"
    if not dst.exists():
        verb = "would create" if dry_run else "created"
    if not dry_run:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(content, encoding="utf-8")
    return f"{verb} {rel}"


def sync_commands(project_root: Path, dry_run: bool = False) -> list[str]:
    return [sync_command(project_root, name, dry_run) for name in KERNEL_COMMAND_NAMES]


def sync_settings(project_root: Path, dry_run: bool = False) -> str:
    """Merge kernel-managed keys into .claude/settings.json.

    Only these keys are touched:
      - hooks                       (replace)
      - permissions.deny            (replace)
      - permissions.defaultMode     (replace)
      - mcpServers                  (replace)

    Everything else in the file is preserved verbatim. If the file does not
    exist, it is created from the template wholesale.
    """
    settings_path = project_root / ".claude" / "settings.json"
    rel = _rel(settings_path, project_root)
    template = json.loads(_read_template("settings.json.tmpl"))

    if not settings_path.exists():
        verb = "would create" if dry_run else "created"
        if not dry_run:
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            settings_path.write_text(
                json.dumps(template, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        return f"{verb} {rel}"

    try:
        existing = json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return f"skipped (invalid JSON) {rel}"

    before = json.dumps(existing, sort_keys=True, ensure_ascii=False)
    existing["hooks"] = template["hooks"]
    existing.setdefault("permissions", {})
    existing["permissions"]["deny"] = template["permissions"]["deny"]
    existing["permissions"]["defaultMode"] = template["permissions"]["defaultMode"]
    existing["mcpServers"] = template["mcpServers"]
    after = json.dumps(existing, sort_keys=True, ensure_ascii=False)

    if before == after:
        return f"unchanged {rel}"

    verb = "would merge" if dry_run else "merged"
    if not dry_run:
        settings_path.write_text(
            json.dumps(existing, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return f"{verb} {rel}"


def sync_gitignore(project_root: Path, dry_run: bool = False) -> str:
    """Append missing kernel entries to .gitignore; never remove or reorder."""
    gi_path = project_root / ".gitignore"
    rel = _rel(gi_path, project_root)
    entries = [
        line.strip()
        for line in _read_template("gitignore_entries.txt").splitlines()
        if line.strip()
    ]

    if not gi_path.exists():
        verb = "would create" if dry_run else "created"
        if not dry_run:
            gi_path.write_text("# CBIM\n" + "\n".join(entries) + "\n", encoding="utf-8")
        return f"{verb} {rel}"

    existing_text = gi_path.read_text(encoding="utf-8")
    existing_lines = {line.strip() for line in existing_text.splitlines()}
    missing = [e for e in entries if e not in existing_lines]
    if not missing:
        return f"unchanged {rel}"

    verb = "would patch" if dry_run else "patched"
    if not dry_run:
        suffix = "" if existing_text.endswith("\n") or not existing_text else "\n"
        addition = suffix + "\n# CBIM\n" + "\n".join(missing) + "\n"
        gi_path.write_text(existing_text + addition, encoding="utf-8")
    return f"{verb} {rel}"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def sync_templates(project_root: Path, dry_run: bool = False) -> list[str]:
    """Refresh all kernel-managed project files. Returns action strings.

    Order is fixed and deterministic so dry-run output is reproducible:
      1. CLAUDE.md
      2. .claudeignore
      3. .claude/agents/<name>/<name>.md  (architect, auditor, hr, programmer)
      4. .claude/commands/<name>.md       (6 built-in slash commands)
      5. .claude/settings.json
      6. .gitignore
    """
    project_root = Path(project_root).resolve()
    actions: list[str] = []
    actions.append(sync_claude_md(project_root, dry_run=dry_run))
    actions.append(sync_claudeignore(project_root, dry_run=dry_run))
    actions.extend(sync_agents(project_root, dry_run=dry_run))
    actions.extend(sync_commands(project_root, dry_run=dry_run))
    actions.append(sync_settings(project_root, dry_run=dry_run))
    actions.append(sync_gitignore(project_root, dry_run=dry_run))
    return actions
