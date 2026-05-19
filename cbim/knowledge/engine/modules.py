"""
engine/modules.py — Knowledge module (.dna) CRUD primitives.

Operates on .dna/ directories anywhere in the project tree.

Supports dual format:
  - New: .dna/module.md (YAML frontmatter + markdown body)
  - Legacy: .dna/module.json + .dna/architecture.md (deprecated, loaded with warning)
"""

import json
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# YAML frontmatter parser (no PyYAML dependency)
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str) -> dict:
    """Parse YAML frontmatter from markdown text. Returns (meta, body)."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    block = text[3:end].strip()
    return _parse_yaml_block(block)


def _strip_frontmatter(text: str) -> str:
    """Return markdown body after frontmatter."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:].strip()
    return text.strip()


def _parse_yaml_block(block: str) -> dict:
    """Minimal YAML parser for frontmatter: supports scalars, simple lists, flow lists."""
    meta: dict = {}
    current_key = ""
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # List continuation: "  - value"
        if line.startswith("  - ") and current_key:
            val = line.strip().lstrip("- ").strip()
            if not isinstance(meta.get(current_key), list):
                meta[current_key] = []
            meta[current_key].append(val)
            continue
        if ":" in stripped:
            k, _, v = stripped.partition(":")
            k = k.strip()
            v = v.strip()
            current_key = k
            if not v:
                # Next lines may be list items
                meta[k] = []
            elif v.startswith("[") and v.endswith("]"):
                # Flow list: [a, b, c]
                inner = v[1:-1].strip()
                if inner:
                    meta[k] = [item.strip().strip("'\"") for item in inner.split(",")]
                else:
                    meta[k] = []
            else:
                meta[k] = v.strip("'\"")
    return meta


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def load_module(mod_dir: Path, root: Path) -> dict | None:
    aimod = mod_dir / ".dna"
    module_md = aimod / "module.md"
    legacy_json = aimod / "module.json"

    if module_md.exists():
        return _load_new_format(mod_dir, root, aimod, module_md)
    elif legacy_json.exists():
        print(f"[DEPRECATED] {mod_dir}: using legacy module.json + architecture.md; "
              f"migrate to module.md", file=sys.stderr)
        return _load_legacy_format(mod_dir, root, aimod, legacy_json)
    else:
        return None


def _load_new_format(mod_dir: Path, root: Path, aimod: Path, module_md: Path) -> dict | None:
    try:
        raw = module_md.read_text(encoding="utf-8")
    except Exception:
        return None

    data = _parse_frontmatter(raw)
    body = _strip_frontmatter(raw)
    rel = str(mod_dir.relative_to(root))

    contract = (aimod / "contract.md").read_text(encoding="utf-8") \
        if (aimod / "contract.md").exists() else ""
    workflows_dir = aimod / "workflows"
    workflows = sorted(w.parent.name for w in workflows_dir.glob("*/workflow.md")) \
        if workflows_dir.exists() else []

    return {
        "id": rel or ".",
        "path": rel or ".",
        "name": data.get("name", rel),
        "owner": data.get("owner", ""),
        "description": data.get("description", ""),
        "keywords": data.get("keywords", []),
        "dependencies": data.get("dependencies", []),
        "architecture": body,
        "contract": contract,
        "workflows": workflows,
    }


def _load_legacy_format(mod_dir: Path, root: Path, aimod: Path,
                        legacy_json: Path) -> dict | None:
    try:
        data = json.loads(legacy_json.read_text(encoding="utf-8"))
    except Exception:
        return None

    rel = str(mod_dir.relative_to(root))
    arch = (aimod / "architecture.md").read_text(encoding="utf-8") \
        if (aimod / "architecture.md").exists() else ""
    contract = (aimod / "contract.md").read_text(encoding="utf-8") \
        if (aimod / "contract.md").exists() else ""
    workflows_dir = aimod / "workflows"
    workflows = sorted(w.parent.name for w in workflows_dir.glob("*/workflow.md")) \
        if workflows_dir.exists() else []

    return {
        "id": rel or ".",
        "path": rel or ".",
        "name": data.get("name", rel),
        "owner": data.get("owner", ""),
        "description": data.get("description", ""),
        "keywords": data.get("keywords", []),
        "dependencies": data.get("dependencies", []),
        "architecture": arch,
        "contract": contract,
        "workflows": workflows,
    }


def list_modules(root: Path) -> list[dict]:
    modules = []
    seen_dirs: set[Path] = set()

    # New format: .dna/module.md
    for mm in sorted(root.rglob(".dna/module.md")):
        mod_dir = mm.parent.parent
        seen_dirs.add(mod_dir)
        m = load_module(mod_dir, root)
        if m:
            modules.append(m)

    # Legacy format: .dna/module.json (only if not already loaded via module.md)
    for mj in sorted(root.rglob(".dna/module.json")):
        mod_dir = mj.parent.parent
        if mod_dir in seen_dirs:
            continue
        m = load_module(mod_dir, root)
        if m:
            modules.append(m)

    return modules


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def init_module(mod_dir: Path, name: str, owner: str,
                description: str = "",
                with_contract: bool = False) -> Path:
    aimod = mod_dir / ".dna"
    if aimod.exists():
        raise FileExistsError(f".dna already exists: {aimod}")

    aimod.mkdir(parents=True)
    (aimod / "workflows").mkdir()

    # Build module.md with YAML frontmatter + body skeleton
    fm_lines = [
        "---",
        f"name: {name}",
        f"owner: {owner}",
    ]
    if description:
        fm_lines.append(f"description: {description}")
    fm_lines.append("keywords: []")
    fm_lines.append("dependencies: []")
    fm_lines.append("---")

    body = f"\n## Positioning\n\n\n## Class Diagram\n\n\n## Key Decisions\n"

    (aimod / "module.md").write_text(
        "\n".join(fm_lines) + "\n" + body,
        encoding="utf-8",
    )
    if with_contract:
        (aimod / "contract.md").write_text(
            f"# {name} — Contract\n\n## Interfaces\n\n## Events\n",
            encoding="utf-8",
        )
    return aimod


def update_module_meta(mod_dir: Path, **kwargs) -> None:
    """Merge kwargs into module.md frontmatter (or legacy module.json)."""
    module_md = mod_dir / ".dna" / "module.md"
    legacy_json = mod_dir / ".dna" / "module.json"

    if module_md.exists():
        raw = module_md.read_text(encoding="utf-8")
        meta = _parse_frontmatter(raw)
        body = _strip_frontmatter(raw)
        meta.update({k: v for k, v in kwargs.items() if v is not None})
        module_md.write_text(_build_module_md(meta, body), encoding="utf-8")
    elif legacy_json.exists():
        data = json.loads(legacy_json.read_text(encoding="utf-8"))
        data.update({k: v for k, v in kwargs.items() if v is not None})
        legacy_json.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _build_module_md(meta: dict, body: str) -> str:
    """Reconstruct module.md from meta dict and body string."""
    fm_lines = ["---"]
    # Emit known fields in a stable order
    for key in ["name", "owner", "description", "keywords", "dependencies", "includeDirs"]:
        if key not in meta:
            continue
        val = meta[key]
        if isinstance(val, list):
            if val:
                fm_lines.append(f"{key}:")
                for item in val:
                    fm_lines.append(f"  - {item}")
            else:
                fm_lines.append(f"{key}: []")
        else:
            fm_lines.append(f"{key}: {val}")
    # Emit any remaining keys
    for key, val in meta.items():
        if key in ("name", "owner", "description", "keywords", "dependencies", "includeDirs"):
            continue
        if isinstance(val, list):
            if val:
                fm_lines.append(f"{key}:")
                for item in val:
                    fm_lines.append(f"  - {item}")
            else:
                fm_lines.append(f"{key}: []")
        else:
            fm_lines.append(f"{key}: {val}")
    fm_lines.append("---")
    return "\n".join(fm_lines) + "\n\n" + body + "\n"


def update_index(root: Path, paths: list[str] | None = None) -> None:
    """Rebuild index.md from all discovered modules (or accept explicit list)."""
    index_path = root / ".dna" / "index.md"
    if paths is None:
        paths = [m["path"] for m in list_modules(root)]
    lines = ["# 模块索引\n"]
    for p in sorted(paths):
        lines.append(f"- {p}")
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
