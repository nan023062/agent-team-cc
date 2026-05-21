"""`cbim init` — bootstrap a new CBIM project."""
from __future__ import annotations

import json
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent
_TEMPLATES = _PKG_DIR / "templates"
_AGENTS = _PKG_DIR / "agents"

_AGENT_NAMES = ("architect", "auditor", "hr", "programmer")


def _read_template(name: str) -> str:
    return (_TEMPLATES / name).read_text(encoding="utf-8")


def _print(action: str, path: Path, root: Path) -> None:
    try:
        rel = path.relative_to(root)
    except ValueError:
        rel = path
    rel_str = str(rel).replace("\\", "/")
    if path.is_dir() and not rel_str.endswith("/"):
        rel_str += "/"
    print(f"[cbim] {action} {rel_str}")


def _ensure_dir(path: Path, root: Path) -> None:
    if path.exists():
        _print("skipped (exists)", path, root)
        return
    path.mkdir(parents=True, exist_ok=True)
    _print("created", path, root)


def _write_if_absent(path: Path, content: str, root: Path, force: bool) -> None:
    if path.exists() and not force:
        _print("skipped (exists)", path, root)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _print("created" if not path.exists() or not force else "overwrote", path, root)


def _install_config(project_root: Path, version: str, force: bool) -> None:
    cfg_path = project_root / ".cbim" / "config.json"
    if cfg_path.exists() and not force:
        _print("skipped (exists)", cfg_path, project_root)
        return
    content = _read_template("config.json.tmpl").replace("{version}", version)
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(content, encoding="utf-8")
    _print("created", cfg_path, project_root)


def _install_agents(project_root: Path, force: bool) -> None:
    for name in _AGENT_NAMES:
        src = _AGENTS / f"{name}.md"
        dst = project_root / ".claude" / "agents" / name / f"{name}.md"
        if dst.exists() and not force:
            _print("skipped (exists)", dst, project_root)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        _print("created", dst, project_root)


def _install_settings(project_root: Path, force: bool) -> None:
    """Merge CBIM-managed keys into .claude/settings.json (preserve user keys)."""
    settings_path = project_root / ".claude" / "settings.json"
    template = json.loads(_read_template("settings.json.tmpl"))

    if settings_path.exists():
        try:
            existing = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            _print("skipped (invalid JSON, not touching)", settings_path, project_root)
            return
        before = json.dumps(existing, sort_keys=True, ensure_ascii=False)
        existing["hooks"] = template["hooks"]
        existing.setdefault("permissions", {})
        existing["permissions"]["deny"] = template["permissions"]["deny"]
        existing["permissions"].setdefault(
            "defaultMode", template["permissions"]["defaultMode"]
        )
        existing["mcpServers"] = template["mcpServers"]
        after = json.dumps(existing, sort_keys=True, ensure_ascii=False)
        if before == after and not force:
            _print("skipped (already up to date)", settings_path, project_root)
            return
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(
            json.dumps(existing, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        _print("merged", settings_path, project_root)
        return

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(template, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _print("created", settings_path, project_root)


def _install_claude_md(project_root: Path, force: bool) -> None:
    dst = project_root / "CLAUDE.md"
    content = _read_template("CLAUDE.md.tmpl")
    if dst.exists() and not force:
        _print("skipped (exists)", dst, project_root)
        return
    dst.write_text(content, encoding="utf-8")
    _print("created", dst, project_root)


def _patch_gitignore(project_root: Path) -> None:
    gi_path = project_root / ".gitignore"
    entries = [
        line.strip()
        for line in _read_template("gitignore_entries.txt").splitlines()
        if line.strip()
    ]

    if gi_path.exists():
        existing_text = gi_path.read_text(encoding="utf-8")
        existing_lines = {line.strip() for line in existing_text.splitlines()}
        missing = [e for e in entries if e not in existing_lines]
        if not missing:
            _print("skipped (already up to date)", gi_path, project_root)
            return
        suffix = "" if existing_text.endswith("\n") or not existing_text else "\n"
        addition = suffix + "\n# CBIM\n" + "\n".join(missing) + "\n"
        gi_path.write_text(existing_text + addition, encoding="utf-8")
        _print("patched", gi_path, project_root)
        return

    gi_path.write_text("# CBIM\n" + "\n".join(entries) + "\n", encoding="utf-8")
    _print("created", gi_path, project_root)


def init_project(project_root: Path, version: str, force: bool = False) -> None:
    """Bootstrap a new CBIM project at project_root.

    Idempotent: existing files are not overwritten unless force=True. The
    .claude/settings.json file is merged, and .gitignore is patched, regardless
    of force.
    """
    project_root = Path(project_root).resolve()
    print(f"[cbim] Initializing CBIM project at {project_root}")

    _install_config(project_root, version, force)
    _ensure_dir(project_root / ".cbim" / "logs", project_root)
    _ensure_dir(project_root / ".cbim" / "memory" / "short", project_root)
    _ensure_dir(project_root / ".cbim" / "memory" / "medium", project_root)
    _install_agents(project_root, force)
    _install_settings(project_root, force)
    _install_claude_md(project_root, force)
    _patch_gitignore(project_root)

    print("[cbim] Done! Start Claude Code in this directory.")
