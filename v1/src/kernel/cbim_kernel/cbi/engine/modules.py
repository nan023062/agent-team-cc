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

try:
    from cbim_kernel.engine.import_log import log_import as _log_import
except ImportError:
    def _log_import(*a, **kw): pass


def _rel_for_log(p: Path, root: Path) -> str:
    """Return path relative to project root for log entries (posix style)."""
    try:
        return p.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return p.as_posix()


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
        _log_import(f"dna:{_rel_for_log(module_md, root)}", "miss", "dna.load")
        return None


def _load_new_format(mod_dir: Path, root: Path, aimod: Path, module_md: Path) -> dict | None:
    try:
        raw = module_md.read_text(encoding="utf-8")
        _log_import(f"dna:{_rel_for_log(module_md, root)}", "ok", "dna.load")
    except Exception:
        _log_import(f"dna:{_rel_for_log(module_md, root)}", "miss", "dna.load")
        return None

    data = _parse_frontmatter(raw)
    body = _strip_frontmatter(raw)
    rel = mod_dir.relative_to(root).as_posix()

    contract_path = aimod / "contract.md"
    if contract_path.exists():
        contract = contract_path.read_text(encoding="utf-8")
        _log_import(f"dna:{_rel_for_log(contract_path, root)}", "ok", "dna.load")
    else:
        contract = ""
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
        _log_import(f"dna:{_rel_for_log(legacy_json, root)}", "ok", "dna.load")
    except Exception:
        _log_import(f"dna:{_rel_for_log(legacy_json, root)}", "miss", "dna.load")
        return None

    rel = mod_dir.relative_to(root).as_posix()
    arch_path = aimod / "architecture.md"
    if arch_path.exists():
        arch = arch_path.read_text(encoding="utf-8")
        _log_import(f"dna:{_rel_for_log(arch_path, root)}", "ok", "dna.load")
    else:
        arch = ""
    contract_path = aimod / "contract.md"
    if contract_path.exists():
        contract = contract_path.read_text(encoding="utf-8")
        _log_import(f"dna:{_rel_for_log(contract_path, root)}", "ok", "dna.load")
    else:
        contract = ""
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


# Directories never scanned for .dna/ — they're vendor/build/framework noise,
# not user business modules. Notably:
#   - node_modules (+ .pnpm/...): pnpm copies workspace pkgs in, which duplicates
#     real .dna/ many times and pollutes the index.
#   - .cbim: the framework itself; user projects host it but shouldn't index it.
#   - .git / dist / build / __pycache__ / .venv / coverage / .next / .cache:
#     standard tool output / VCS metadata.
_SCAN_SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", "__pycache__",
    ".venv", ".cbim", ".pnpm-store", "coverage",
    ".next", ".cache",
}


def _is_skipped(mod_dir: Path, root: Path) -> bool:
    try:
        parts = mod_dir.relative_to(root).parts
    except ValueError:
        return False
    return any(p in _SCAN_SKIP_DIRS for p in parts)


# ---------------------------------------------------------------------------
# Module registry — .cbim/index.md
# ---------------------------------------------------------------------------
#
# The registry is the canonical, fast-path source of "which modules exist in
# this project". Full filesystem rglob is expensive on large monorepos, so:
#   - list_modules() / snapshot.py read the registry first (O(N) where N =
#     module count, not filesystem size)
#   - init_module() appends new modules in place
#   - reindex() / update_index() rebuild from rglob (manual recovery)
#
# The registry lives in .cbim/index.md — NOT in the project root and NOT
# wrapped in a redundant .dna/ layer. This decouples the framework-managed
# registry from the optional project-root module document. .cbim/ is the
# framework, not a business module, and is excluded from module scans by
# _SCAN_SKIP_DIRS.


def index_path(root: Path) -> Path:
    """Return the canonical location of the module registry.

    Public helper — install/bootstrap reuses this to stay in sync with the
    kernel's authoritative path.
    """
    return root / ".cbim" / "index.md"


# Backwards-compatible private alias used throughout this module.
_index_path = index_path


def ensure_registry(root: Path) -> Path:
    """Create an empty .cbim/index.md if missing. Idempotent."""
    p = _index_path(root)
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# Module Index\n", encoding="utf-8")
    return p


def read_index(root: Path) -> list[str]:
    """Return the list of module paths registered in .cbim/index.md.

    Returns [] if the registry doesn't exist or is empty. Each line is parsed
    as `- <path> [optional annotation]`; only the first whitespace-delimited
    token is taken (so `- . (root module)` yields `.`).
    """
    p = _index_path(root)
    if not p.exists():
        _log_import(f"dna:{_rel_for_log(p, root)}", "miss", "dna.load")
        return []
    _log_import(f"dna:{_rel_for_log(p, root)}", "ok", "dna.load")
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip().lstrip("- ").strip()
        if not s or s.startswith("#"):
            continue
        first = s.split()[0] if s.split() else ""
        if first:
            out.append(first)
    return out


def _write_index(root: Path, paths: list[str]) -> None:
    """Atomically rewrite .cbim/index.md with the given paths (sorted)."""
    ensure_registry(root)
    lines = ["# Module Index", ""]
    for p_str in sorted(set(paths)):
        lines.append(f"- {p_str}")
    _index_path(root).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_to_index(root: Path, rel_path: str) -> None:
    """Add a single module path to the registry, preserving existing entries."""
    paths = set(read_index(root))
    paths.add(rel_path)
    _write_index(root, list(paths))


def _scan_modules(root: Path) -> list[dict]:
    """Slow path: rglob the filesystem for all .dna/module.md (and legacy
    module.json) files, skipping vendor/build/framework dirs. Used by reindex
    and as a fallback when the registry is missing."""
    modules = []
    seen_dirs: set[Path] = set()

    for mm in sorted(root.rglob(".dna/module.md")):
        mod_dir = mm.parent.parent
        if _is_skipped(mod_dir, root):
            continue
        seen_dirs.add(mod_dir)
        m = load_module(mod_dir, root)
        if m:
            modules.append(m)

    for mj in sorted(root.rglob(".dna/module.json")):
        mod_dir = mj.parent.parent
        if mod_dir in seen_dirs or _is_skipped(mod_dir, root):
            continue
        m = load_module(mod_dir, root)
        if m:
            modules.append(m)

    return modules


def list_modules(root: Path, use_registry: bool = True) -> list[dict]:
    """Return all modules. Reads .cbim/index.md by default for speed; falls
    back to a full filesystem scan if the registry is missing/empty.

    Pass use_registry=False to force a fresh scan (used by reindex / governance
    validation that needs to compare on-disk state against the registry).
    """
    if use_registry:
        registered = read_index(root)
        if registered:
            modules = []
            for rel in registered:
                mod_dir = root if rel == "." else (root / rel)
                m = load_module(mod_dir, root)
                if m:
                    modules.append(m)
            return modules
    return _scan_modules(root)


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

_VALID_TYPES = ("root", "parent", "leaf")

_LEAF_BODY = """
## Positioning

<!-- One sentence: what this module is and why it exists. -->

## Class Diagram

```mermaid
classDiagram
    %% classes, interfaces, key method signatures, relationships
```

## Key Decisions

<!-- Design choices whose "why" is invisible from the code itself.
     Each decision applies to the module as a whole. -->
"""

_PARENT_BODY = """
## Positioning

<!-- One sentence: what this module is and why it exists. -->

## Sub-module Relationships

```mermaid
graph TD
    %% Nodes = sub-modules (each with one-line positioning).
    %% Edges = inter-sub-module dependencies.
```

## Key Decisions

<!-- ONLY cross-sub-module emergent insights:
     why these sub-modules exist together, how they relate at boundaries.
     DO NOT write any single sub-module's internal design here —
     that belongs in the sub-module's own .dna/module.md. -->
"""


def init_module(mod_dir: Path, name: str, owner: str,
                description: str = "",
                with_contract: bool = False,
                type_: str = "leaf",
                project_root: Path | None = None) -> Path:
    """Initialize a new module.

    type_: 'root' | 'parent' | 'leaf'
      - root: must be the project root; auto-creates index.md
      - parent: requires root .dna/ to exist; uses parent body template
      - leaf: requires root .dna/ to exist; uses leaf body template
    """
    if type_ not in _VALID_TYPES:
        raise ValueError(
            f"type_ must be one of {_VALID_TYPES}, got: {type_!r}"
        )

    target = mod_dir.resolve()
    root = (project_root or Path.cwd()).resolve()

    # Registry (.cbim/index.md) must exist — proves cbim is installed.
    # The project-root .dna/ is OPTIONAL; mixed monorepos can skip it.
    if not _index_path(root).exists():
        raise FileNotFoundError(
            f"Registry missing at {_index_path(root)}.\n"
            f"Run `python .cbim/install.py` first to install cbim into this project."
        )

    if type_ == "root":
        if target != root:
            raise ValueError(
                f"--type root must be the project root (creates ./.dna/module.md).\n"
                f"  project root : {root}\n"
                f"  target       : {target}\n"
                f"For monorepos, a project-root module is optional — consider "
                f"`--type parent` on your workspace dir (e.g. `packages/`) instead."
            )

    aimod = mod_dir / ".dna"
    if aimod.exists():
        raise FileExistsError(f".dna already exists: {aimod}")

    aimod.mkdir(parents=True)

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

    body = _LEAF_BODY if type_ == "leaf" else _PARENT_BODY

    (aimod / "module.md").write_text(
        "\n".join(fm_lines) + body,
        encoding="utf-8",
    )

    if with_contract:
        (aimod / "contract.md").write_text(
            f"# {name} — Contract\n\n## Interfaces\n\n## Events\n",
            encoding="utf-8",
        )

    # Append to the registry so list_modules / snapshot see it immediately.
    # (Note: index.md lives at .cbim/index.md, not under any .dna/.)
    rel = mod_dir.resolve().relative_to(root).as_posix()
    _append_to_index(root, rel)

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


_WRITE_DOC_ALLOWED = ("module.md", "contract.md")


def write_module_doc(mod_dir: Path, file_name: str, body: str) -> Path:
    """Replace the markdown body of <mod_dir>/.dna/<file_name>, preserving any
    leading YAML frontmatter verbatim.

    Rules:
      - file_name must be 'module.md' or 'contract.md'; anything else raises ValueError.
      - <mod_dir>/.dna/ must already exist (i.e. `dna init` has been run); otherwise FileNotFoundError.
      - If the target file does not yet exist, it is created (body only, no frontmatter).
      - If the target file exists and starts with `---` frontmatter, the frontmatter is
        preserved exactly as on disk and only the body is replaced.
      - Atomic: write to <file>.tmp then os.replace to <file>. Crash mid-write leaves
        either the old file intact or no .tmp residue visible to readers.

    Returns the absolute path of the written file.
    """
    import os

    if file_name not in _WRITE_DOC_ALLOWED:
        raise ValueError(
            f"--file must be one of {_WRITE_DOC_ALLOWED}, got: {file_name!r}"
        )

    aimod = mod_dir.resolve() / ".dna"
    if not aimod.is_dir():
        raise FileNotFoundError(
            f"module not initialized at {mod_dir}; run `dna init` first "
            f"(missing {aimod})"
        )

    target = aimod / file_name
    body_text = body if body.endswith("\n") else body + "\n"

    if target.exists():
        existing = target.read_text(encoding="utf-8")
        if existing.startswith("---"):
            end = existing.find("\n---", 3)
            if end != -1:
                # Keep frontmatter block byte-for-byte: from start through "\n---" and its trailing newline.
                fm_end = end + 4  # past "\n---"
                # Preserve the single newline that conventionally follows the closing ---
                if fm_end < len(existing) and existing[fm_end] == "\n":
                    fm_end += 1
                frontmatter = existing[:fm_end]
                new_content = frontmatter + body_text
            else:
                # Malformed frontmatter (opens but never closes) — treat whole file as body, overwrite.
                new_content = body_text
        else:
            new_content = body_text
    else:
        new_content = body_text

    tmp = target.with_suffix(target.suffix + ".tmp")
    try:
        tmp.write_text(new_content, encoding="utf-8")
        os.replace(tmp, target)
    except Exception:
        # Best-effort cleanup of half-written tmp; suppress secondary errors.
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise

    return target


def update_index(root: Path, paths: list[str] | None = None) -> None:
    """Rebuild .cbim/index.md from a fresh filesystem scan (or accept an
    explicit path list). Use this for one-shot recovery / migration; the
    normal CLI flow keeps the registry up to date via init_module."""
    if paths is None:
        paths = [m["path"] for m in _scan_modules(root)]
    _write_index(root, paths)
