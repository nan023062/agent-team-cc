"""`cbim project sync` — refresh kernel-managed project files from templates.

Shared template-copy logic used by `init` and the standalone `project sync`
command. The rules per file:

| File                                    | Rule                                                           |
|-----------------------------------------|----------------------------------------------------------------|
| CLAUDE.md                               | Always overwrite from template                                 |
| .claude/agents/<name>/<name>.md (x4)    | Always overwrite (only the 4 built-in named agents)            |
| .claude/commands/<name>.md (x6)         | Always overwrite (only the 6 built-in slash commands:          |
|                                         | cbim_dashboard, cbim_debug, cbim_help, cbim_install,           |
|                                         | cbim_log, cbim_sched)                                          |
| .claude/settings.json                   | Surgical merge: per-event refresh of cbim hook entries (cmd     |
|                                         | starts with `.claude/hooks/cbim_`); ensure 4 cbim deny patterns |
|                                         | present; replace `permissions.defaultMode`. User events / user  |
|                                         | hook entries / user deny entries preserved. Also strips any     |
|                                         | legacy `mcpServers.cbim` key.                                   |
| .mcp.json (project root)                | Merge `mcpServers.cbim` only — preserve other servers          |
| .gitignore                              | Append missing entries only                                    |

Never touched by sync:
- .cbim/config.json
- .cbim/memory/**, .cbim/logs/**
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
_HOOKS_SRC = _PKG_DIR / "hooks_src"

# Kernel-managed hook script filenames installed into .claude/hooks/. Any other
# *.py file under .claude/hooks/ is treated as user-owned and never touched.
KERNEL_HOOK_SCRIPT_NAMES: tuple[str, ...] = (
    "cbim_session_start.py",
    "cbim_stop.py",
    "cbim_session_end.py",
    "cbim_user_prompt_submit.py",
    "cbim_pre_tool_use.py",
    "cbim_post_tool_use.py",
    "cbim_auto_preview.py",
)

# The four kernel-managed (built-in) agents. Any other agent directory under
# .claude/agents/ is treated as user-owned and never touched.
KERNEL_AGENT_NAMES: tuple[str, ...] = ("architect", "auditor", "hr", "programmer")

# The six kernel-managed (built-in) slash commands. Any other .md file under
# .claude/commands/ is treated as user-owned and never touched.
KERNEL_COMMAND_NAMES: tuple[str, ...] = (
    "cbim_dashboard",
    "cbim_debug",
    "cbim_help",
    "cbim_install",
    "cbim_log",
    "cbim_sched",
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
    """Append missing kernel entries to .claudeignore; never remove or reorder.

    Mirrors the .gitignore policy: if the file does not exist, create it from
    the template wholesale; otherwise only append entries that are not already
    present (line-equality match).
    """
    dst = project_root / ".claudeignore"
    rel = _rel(dst, project_root)
    template_text = _read_template("claudeignore.tmpl")
    entries = [line.strip() for line in template_text.splitlines() if line.strip()]

    if not dst.exists():
        verb = "would create" if dry_run else "created"
        if not dry_run:
            dst.write_text(template_text, encoding="utf-8")
        return f"{verb} {rel}"

    existing_text = dst.read_text(encoding="utf-8")
    existing_lines = {line.strip() for line in existing_text.splitlines()}
    missing = [e for e in entries if e not in existing_lines]
    if not missing:
        return f"unchanged {rel}"

    verb = "would patch" if dry_run else "patched"
    if not dry_run:
        suffix = "" if existing_text.endswith("\n") or not existing_text else "\n"
        addition = suffix + "\n".join(missing) + "\n"
        dst.write_text(existing_text + addition, encoding="utf-8")
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


def sync_hook_scripts(project_root: Path, dry_run: bool = False) -> list[str]:
    """Refresh .claude/hooks/ with the kernel-managed hook scripts + _lib/.

    Identification of "kernel-owned" hook artifacts:
      - top-level files in .claude/hooks/ matching KERNEL_HOOK_SCRIPT_NAMES
      - the entire .claude/hooks/_lib/ subdirectory

    Anything else under .claude/hooks/ is treated as user-owned and left alone.
    Existing kernel-owned artifacts are removed before re-copy (clean slate),
    so the result is byte-identical to the bundled hooks_src/ tree.

    Returns one action string per artifact touched, plus one summary line.
    """
    import os
    import shutil

    hooks_dir = project_root / ".claude" / "hooks"
    rel_dir = _rel(hooks_dir, project_root)
    actions: list[str] = []

    if dry_run:
        actions.append(f"would refresh {rel_dir}/ (7 scripts + _lib/)")
        return actions

    hooks_dir.mkdir(parents=True, exist_ok=True)

    # 1. Remove only kernel-owned artifacts (preserve user-added .py files).
    for name in KERNEL_HOOK_SCRIPT_NAMES:
        p = hooks_dir / name
        if p.exists():
            p.unlink()
    lib_dst = hooks_dir / "_lib"
    if lib_dst.exists():
        shutil.rmtree(lib_dst)

    # 2. Copy 7 cbim_*.py scripts; chmod 0755.
    for name in KERNEL_HOOK_SCRIPT_NAMES:
        src = _HOOKS_SRC / name
        dst = hooks_dir / name
        shutil.copy2(src, dst)
        os.chmod(dst, 0o755)
        actions.append(f"installed {_rel(dst, project_root)}")

    # 3. Copy _lib/ subdir (filter __pycache__ at any depth).
    lib_src = _HOOKS_SRC / "_lib"

    def _ignore(_dir: str, names: list[str]) -> list[str]:
        return [n for n in names if n == "__pycache__"]

    shutil.copytree(lib_src, lib_dst, ignore=_ignore)
    actions.append(f"installed {_rel(lib_dst, project_root)}/")
    return actions


_CBIM_HOOK_CMD_PREFIX = ".claude/hooks/cbim_"
_LEGACY_CBIM_HOOK_CMD_PREFIXES: tuple[str, ...] = (
    ".cbim/run hook",  # pre-Phase-3a shim
    "cbim hook ",      # pre-V1 CLI-based hooks (e.g. "cbim hook session-start")
)
_CBIM_DENY_PATTERNS: tuple[str, ...] = (
    "Write(.cbim/**)",
    "Edit(.cbim/**)",
    "Read(.cbim/**)",
    "Bash(.cbim/run *)",
)


def _is_cbim_hook_entry(entry: object) -> bool:
    """A single hook entry is 'cbim-owned' iff its command matches either
    the canonical cbim hook path prefix or the pre-Phase-3a legacy shim
    invocation (`.cbim/run hook ...`). The legacy form must be recognised
    so the upgrade path can strip it on next sync. Non-dict / non-command
    entries are not cbim-owned (user-defined or future-shape — leave
    untouched).
    """
    if not isinstance(entry, dict):
        return False
    cmd = entry.get("command")
    if not isinstance(cmd, str):
        return False
    return cmd.startswith(_CBIM_HOOK_CMD_PREFIX) or any(
        cmd.startswith(p) for p in _LEGACY_CBIM_HOOK_CMD_PREFIXES
    )


def _merge_cbim_hooks(user_hooks: object, template_hooks: dict) -> dict:
    """Per-event, per-entry merge of cbim hook entries into the user's hooks tree.

    Contract:
      - For every event the TEMPLATE declares: strip all cbim-owned entries
        from every group in the user's matching event array (preserving the
        user's non-cbim entries in place); drop any group whose `hooks` array
        becomes empty; then append a single trailing group containing all of
        the template's cbim entries for that event, in template order.
      - Events the template does NOT declare (e.g. user's `OnSave`) are left
        completely untouched.
      - If user_hooks is missing or malformed, start from `{}` and just install
        the template events fresh.

    Result is a fresh dict; callers replace user_hooks with it.
    """
    if not isinstance(user_hooks, dict):
        user_hooks = {}
    out: dict = {k: v for k, v in user_hooks.items()}

    for event, tmpl_groups in template_hooks.items():
        # Collect the template's cbim entries for this event, in declared order.
        tmpl_cbim_entries: list[dict] = []
        for g in tmpl_groups:
            if not isinstance(g, dict):
                continue
            for e in g.get("hooks", []):
                if _is_cbim_hook_entry(e):
                    tmpl_cbim_entries.append(e)

        user_event = out.get(event)
        if not isinstance(user_event, list):
            user_event = []

        # Strip cbim-owned entries from every user group; drop emptied groups.
        new_groups: list[dict] = []
        for g in user_event:
            if not isinstance(g, dict):
                new_groups.append(g)
                continue
            kept = [e for e in g.get("hooks", []) if not _is_cbim_hook_entry(e)]
            if kept:
                ng = {k: v for k, v in g.items()}
                ng["hooks"] = kept
                new_groups.append(ng)

        if tmpl_cbim_entries:
            new_groups.append({"hooks": tmpl_cbim_entries})

        out[event] = new_groups

    return out


def _merge_cbim_deny(user_deny: object) -> list:
    """Ensure the 4 cbim deny patterns are present; preserve all user entries
    and their order; do not deduplicate user entries.

    Missing cbim patterns are appended (in template order) after the user's
    existing entries. If user_deny is missing or malformed, return the 4 cbim
    patterns alone.
    """
    if not isinstance(user_deny, list):
        return list(_CBIM_DENY_PATTERNS)
    out = list(user_deny)
    for pat in _CBIM_DENY_PATTERNS:
        if pat not in out:
            out.append(pat)
    return out


def sync_settings(project_root: Path, dry_run: bool = False) -> str:
    """Merge kernel-managed keys into .claude/settings.json with surgical precision.

    Surfaces actually touched:
      - hooks[<event>] for every event the TEMPLATE declares: cbim-owned
        entries (command starting with `.claude/hooks/cbim_`) are refreshed
        from template; user entries (any other command) are preserved in
        place. Events the template doesn't declare (e.g. user `OnSave`) are
        not touched.
      - permissions.deny: the 4 cbim patterns (Write/Edit/Read on `.cbim/**`,
        Bash on `.cbim/run *`) are ensured present; user entries are preserved
        in original order.
      - permissions.defaultMode: replaced with template value (kernel-owned).

    Legacy cleanup: strip pre-Phase-7 `mcpServers.cbim` (registration moved to
    project-root `.mcp.json`); other `mcpServers.<name>` entries are preserved.

    All other keys are preserved verbatim. Missing file → wholesale create.
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
    existing["hooks"] = _merge_cbim_hooks(existing.get("hooks"), template["hooks"])
    existing.setdefault("permissions", {})
    existing["permissions"]["deny"] = _merge_cbim_deny(
        existing["permissions"].get("deny")
    )
    existing["permissions"]["defaultMode"] = template["permissions"]["defaultMode"]
    mcp = existing.get("mcpServers")
    if isinstance(mcp, dict) and "cbim" in mcp:
        del mcp["cbim"]
        if not mcp:
            del existing["mcpServers"]
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


def sync_mcp_json(project_root: Path, dry_run: bool = False) -> str:
    """Merge the cbim MCP server registration into project-root `.mcp.json`.

    Claude Code reads project-level MCP server registrations from
    `<project_root>/.mcp.json` (NOT `.claude/settings.json.mcpServers`). This
    function ensures the `cbim` entry exists there; other entries under
    `mcpServers.<name>` are preserved.

    File creation: if `.mcp.json` does not exist, it is created from the
    template wholesale. Merge: only `mcpServers.cbim` is overwritten; all
    other top-level keys and all other `mcpServers.<name>` entries survive.
    """
    mcp_path = project_root / ".mcp.json"
    rel = _rel(mcp_path, project_root)
    template = json.loads(_read_template("mcp.json.tmpl"))

    if not mcp_path.exists():
        verb = "would create" if dry_run else "created"
        if not dry_run:
            mcp_path.parent.mkdir(parents=True, exist_ok=True)
            mcp_path.write_text(
                json.dumps(template, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        return f"{verb} {rel}"

    try:
        existing = json.loads(mcp_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return f"skipped (invalid JSON) {rel}"

    before = json.dumps(existing, sort_keys=True, ensure_ascii=False)
    existing.setdefault("mcpServers", {})
    existing["mcpServers"]["cbim"] = template["mcpServers"]["cbim"]
    after = json.dumps(existing, sort_keys=True, ensure_ascii=False)

    if before == after:
        return f"unchanged {rel}"

    verb = "would merge" if dry_run else "merged"
    if not dry_run:
        mcp_path.write_text(
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
      5. .claude/hooks/cbim_*.py + _lib/  (7 hook scripts + shared library)
      6. .claude/settings.json
      7. .mcp.json
      8. .gitignore
    """
    project_root = Path(project_root).resolve()
    actions: list[str] = []
    actions.append(sync_claude_md(project_root, dry_run=dry_run))
    actions.append(sync_claudeignore(project_root, dry_run=dry_run))
    actions.extend(sync_agents(project_root, dry_run=dry_run))
    actions.extend(sync_commands(project_root, dry_run=dry_run))
    actions.extend(sync_hook_scripts(project_root, dry_run=dry_run))
    actions.append(sync_settings(project_root, dry_run=dry_run))
    actions.append(sync_mcp_json(project_root, dry_run=dry_run))
    actions.append(sync_gitignore(project_root, dry_run=dry_run))
    return actions
