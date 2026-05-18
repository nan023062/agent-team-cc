"""
engine/modules.py — Knowledge module (.aimodule) CRUD primitives.

Operates on .aimodule/ directories anywhere in the project tree.
"""

import json
from pathlib import Path


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def load_module(mod_dir: Path, root: Path) -> dict | None:
    aimod = mod_dir / ".aimodule"
    mj = aimod / "module.json"
    if not mj.exists():
        return None
    try:
        data = json.loads(mj.read_text(encoding="utf-8"))
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
    for mj in sorted(root.rglob(".aimodule/module.json")):
        mod_dir = mj.parent.parent
        m = load_module(mod_dir, root)
        if m:
            modules.append(m)
    return modules


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def init_module(mod_dir: Path, name: str, owner: str,
                description: str = "") -> Path:
    aimod = mod_dir / ".aimodule"
    if aimod.exists():
        raise FileExistsError(f".aimodule already exists: {aimod}")

    aimod.mkdir(parents=True)
    (aimod / "workflows").mkdir()

    meta: dict = {"name": name, "owner": owner}
    if description:
        meta["description"] = description

    (aimod / "module.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (aimod / "architecture.md").write_text(
        f"# {name} — Architecture\n\n## Overview\n\n## Structure\n\n## Key Decisions\n",
        encoding="utf-8",
    )
    (aimod / "contract.md").write_text(
        f"# {name} — Contract\n\n## Interfaces\n\n## Events\n",
        encoding="utf-8",
    )
    return aimod


def update_module_meta(mod_dir: Path, **kwargs) -> None:
    """Merge kwargs into module.json (description, keywords, dependencies, owner, etc.)"""
    mj = mod_dir / ".aimodule" / "module.json"
    data = json.loads(mj.read_text(encoding="utf-8"))
    data.update({k: v for k, v in kwargs.items() if v is not None})
    mj.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def update_index(root: Path, paths: list[str] | None = None) -> None:
    """Rebuild index.md from all discovered modules (or accept explicit list)."""
    index_path = root / ".aimodule" / "index.md"
    if paths is None:
        paths = [m["path"] for m in list_modules(root)]
    lines = ["# 模块索引\n"]
    for p in sorted(paths):
        lines.append(f"- {p}")
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
