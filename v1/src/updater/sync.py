"""Updater-private template sync — schema migration of `.cbim/` and `.claude/`.

Lives in the updater package (not the kernel) because cross-version schema
migration must remain runnable even when the project's pinned kernel cannot
import. Reads kernel-shipped templates/agents/commands from a kernel snapshot
directory passed in as `kernel_root` (resolved by the caller via
`updater.registry.get_kernel_path(version)`). Never imports `cbim_kernel`.

Action strings returned here are an implicit contract with `migrate.py`,
which prefix-matches on `"unchanged "` to decide "fully aligned". Preserve
those exact prefixes.

Asset layout inside a kernel snapshot (`<install_root>/kernel/<ver>/`):

    cbim_kernel/project/templates/settings.json.tmpl
    cbim_kernel/project/agents/<name>.md
    cbim_kernel/project/commands/<name>.md

Only the subset migrate.py actually consumes is ported:
    KERNEL_AGENT_NAMES, KERNEL_COMMAND_NAMES,
    sync_settings, sync_agents, sync_commands
(plus sync_agent / sync_command as their per-file helpers).
"""
from __future__ import annotations

import json
from pathlib import Path


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


def _assets_dir(kernel_root: Path) -> Path:
    """Resolve the kernel snapshot's `cbim_kernel/project/` directory."""
    return Path(kernel_root) / "cbim_kernel" / "project"


def _read_template(kernel_root: Path, name: str) -> str:
    return (_assets_dir(kernel_root) / "templates" / name).read_text(encoding="utf-8")


def _rel(path: Path, root: Path) -> str:
    try:
        rel = path.relative_to(root)
    except ValueError:
        rel = path
    return str(rel).replace("\\", "/")


def sync_agent(
    project_root: Path,
    name: str,
    kernel_root: Path,
    dry_run: bool = False,
) -> str:
    src = _assets_dir(kernel_root) / "agents" / f"{name}.md"
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


def sync_agents(
    project_root: Path,
    kernel_root: Path,
    dry_run: bool = False,
) -> list[str]:
    return [
        sync_agent(project_root, name, kernel_root, dry_run)
        for name in KERNEL_AGENT_NAMES
    ]


def sync_command(
    project_root: Path,
    name: str,
    kernel_root: Path,
    dry_run: bool = False,
) -> str:
    """OWNED file. Overwrite the built-in slash command from template."""
    src = _assets_dir(kernel_root) / "commands" / f"{name}.md"
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


def sync_commands(
    project_root: Path,
    kernel_root: Path,
    dry_run: bool = False,
) -> list[str]:
    return [
        sync_command(project_root, name, kernel_root, dry_run)
        for name in KERNEL_COMMAND_NAMES
    ]


def sync_settings(
    project_root: Path,
    kernel_root: Path,
    dry_run: bool = False,
) -> str:
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
    template = json.loads(_read_template(kernel_root, "settings.json.tmpl"))

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
