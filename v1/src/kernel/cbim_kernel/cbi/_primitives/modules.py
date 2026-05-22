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
from dataclasses import dataclass, field
from pathlib import Path

from cbim_kernel.services._fm import (
    parse_frontmatter,
    render_frontmatter,
    strip_frontmatter,
)

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

    data = parse_frontmatter(raw)
    body = strip_frontmatter(raw)
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
        # Backward compat: older module.md files have no `status` — default to
        # "implemented" because by definition the existing code in the repo
        # already realises whatever the DNA describes (otherwise the file
        # wouldn't be there yet).
        "status": data.get("status", "implemented"),
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
        # Legacy module.json was authored before the status field existed —
        # treat as implemented for backward compat (see _load_new_format).
        "status": data.get("status", "implemented"),
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
                status: str | None = None,
                project_root: Path | None = None) -> Path:
    """Initialize a new module.

    type_: 'root' | 'parent' | 'leaf'
      - root: must be the project root; auto-creates index.md
      - parent: requires root .dna/ to exist; uses parent body template
      - leaf: requires root .dna/ to exist; uses leaf body template

    status: 'spec' | 'planned' | 'implemented' — declared intent of the new
      module. When omitted, defaults to 'spec' for parent/leaf (architect is
      writing DNA ahead of code) and 'implemented' for root (the project root
      module of an existing repo is by definition already real). Validated
      against _MODULE_FM_STATUS_VALUES.
    """
    if type_ not in _VALID_TYPES:
        raise ValueError(
            f"type_ must be one of {_VALID_TYPES}, got: {type_!r}"
        )
    if status is None:
        status = "implemented" if type_ == "root" else "spec"
    if status not in _MODULE_FM_STATUS_VALUES:
        raise ValueError(
            f"status must be one of {_MODULE_FM_STATUS_VALUES}, got: {status!r}"
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
    fm_lines.append(f"status: {status}")
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
        meta = parse_frontmatter(raw)
        body = strip_frontmatter(raw)
        meta.update({k: v for k, v in kwargs.items() if v is not None})
        module_md.write_text(_build_module_md(meta, body), encoding="utf-8")
    elif legacy_json.exists():
        data = json.loads(legacy_json.read_text(encoding="utf-8"))
        data.update({k: v for k, v in kwargs.items() if v is not None})
        legacy_json.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


_MODULE_FM_SCHEMA = (
    "name", "owner", "description",
    "keywords", "dependencies", "includeDirs",
    "status",
)

# Frontmatter fields whose YAML type is a list. The CLI uses this to reject
# scalar `--value` writes against these fields and to require `--value-list`
# instead, so users never accidentally serialize "a,b,c" as a single string.
_MODULE_FM_LIST_FIELDS = frozenset({
    "keywords", "dependencies", "includeDirs",
})

# Allowed values for the `status` frontmatter field. Declared intent (set by
# the architect), orthogonal to the observed DNA state (0/1/2/3):
#   - spec         : designed; not yet implemented (state-3 source of truth)
#   - planned      : named only; design still pending (rarely used; early stub)
#   - implemented  : code matches the DNA (the steady state)
# Defined here once; engine/cli.py and resources/dna_module.py import this
# tuple — do NOT duplicate the value set.
_MODULE_FM_STATUS_VALUES = ("spec", "planned", "implemented")


def _build_module_md(meta: dict, body: str) -> str:
    """Reconstruct module.md from meta dict and body string."""
    return render_frontmatter(meta, _MODULE_FM_SCHEMA) + "\n" + body + "\n"


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


# ---------------------------------------------------------------------------
# Section-level edits (write_module_section)
# ---------------------------------------------------------------------------
#
# Surgical H2/H3 edits on .dna/{module.md,contract.md} bodies. The frontmatter
# is preserved byte-for-byte; only the body is rewritten. Atomic via .tmp +
# os.replace, like write_module_doc.

_WRITE_SECTION_ALLOWED = ("module.md", "contract.md")
_WRITE_SECTION_MODES = ("replace", "append", "insert-after", "delete")

# Heading: 1-6 '#'s, space, text, optional trailing '#'s. Only matched outside
# fenced code blocks (see _split_sections).
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
# Code-fence opener/closer. Toggled regardless of language tag after the fence.
_FENCE_RE = re.compile(r"^(?:```|~~~)")


@dataclass
class _Section:
    level: int           # 1..6
    heading: str         # trimmed text, no leading '#'s
    start: int           # line index of the heading line
    end: int             # line index after the section (exclusive)
    body_lines: list[str] = field(default_factory=list)


def _split_frontmatter_block(text: str) -> tuple[str, str]:
    """Return (frontmatter_block, body_text). frontmatter_block includes the
    closing '---' and its trailing newline if present. If no frontmatter,
    returns ('', text)."""
    if not text.startswith("---"):
        return "", text
    end = text.find("\n---", 3)
    if end == -1:
        return "", text
    fm_end = end + 4  # past "\n---"
    if fm_end < len(text) and text[fm_end] == "\n":
        fm_end += 1
    return text[:fm_end], text[fm_end:]


def _split_sections(body_text: str) -> list[_Section]:
    """Walk markdown body lines and return all headings as _Section objects,
    skipping headings inside fenced code blocks. section.end points to the
    start of the next section whose level <= section.level, or len(lines).
    """
    lines = body_text.splitlines()
    in_fence = False
    raw: list[_Section] = []
    for i, line in enumerate(lines):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _HEADING_RE.match(line)
        if not m:
            continue
        level = len(m.group(1))
        heading = m.group(2).strip()
        raw.append(_Section(level=level, heading=heading, start=i, end=len(lines)))

    # Compute end for each section: index of next section with level <= self.level.
    for idx, sec in enumerate(raw):
        end = len(lines)
        for j in range(idx + 1, len(raw)):
            if raw[j].level <= sec.level:
                end = raw[j].start
                break
        sec.end = end
        sec.body_lines = lines[sec.start + 1:end]
    return raw


def _normalize_content_lines(content: str) -> list[str]:
    """Strip surrounding newlines and split into lines (no trailing empty)."""
    return content.strip("\n").splitlines()


def write_module_section(
    mod_dir: Path,
    file_name: str,
    heading: str,
    level: int,
    mode: str,
    content: str | None,
    create_if_missing: bool = False,
    dry_run: bool = False,
) -> Path | str:
    """Section-level surgical edit of <mod_dir>/.dna/<file_name>.

    Returns the absolute Path of the written file on success, or the resulting
    file content (str) when dry_run=True.

    Modes:
      - 'replace'      : replace section body (keep heading line)
      - 'append'       : append content to end of section body
      - 'insert-after' : insert content as a new section right after this one
      - 'delete'       : remove heading line and its body

    Raises ValueError / FileNotFoundError on misuse; raises LookupError when the
    heading cannot be found and create_if_missing is not applicable.
    """
    import os

    if file_name not in _WRITE_SECTION_ALLOWED:
        raise ValueError(
            f"--file must be one of {_WRITE_SECTION_ALLOWED}, got: {file_name!r}"
        )
    if mode not in _WRITE_SECTION_MODES:
        raise ValueError(
            f"--mode must be one of {_WRITE_SECTION_MODES}, got: {mode!r}"
        )
    if level not in (2, 3):
        raise ValueError(f"--level must be 2 or 3, got: {level!r}")
    if mode == "delete":
        if content is not None:
            raise ValueError("--content is forbidden when --mode delete")
    else:
        if content is None:
            raise ValueError(f"--content is required when --mode {mode}")

    aimod = mod_dir.resolve() / ".dna"
    if not aimod.is_dir():
        raise FileNotFoundError(
            f"module not initialized at {mod_dir}; run `dna init` first "
            f"(missing {aimod})"
        )

    target = aimod / file_name
    if not target.is_file():
        raise FileNotFoundError(
            f"file does not exist: {target} (use `dna init` or `dna write-doc` "
            f"to create it first)"
        )

    original = target.read_text(encoding="utf-8")
    had_frontmatter = original.startswith("---") and original.find("\n---", 3) != -1
    original_meta = parse_frontmatter(original) if had_frontmatter else {}

    frontmatter_block, body_text = _split_frontmatter_block(original)
    body_lines = body_text.splitlines()

    sections = _split_sections(body_text)
    matches = [s for s in sections if s.level == level and s.heading == heading]

    if len(matches) > 1:
        raise LookupError(
            f"ambiguous: {len(matches)} sections match heading "
            f"'{heading}' at level {level}; heading must be unique within file"
        )

    if not matches:
        # Heading absent — behaviour depends on mode.
        if mode == "delete":
            # No-op: report on stderr, return current file path.
            print(
                f"write-section: heading not found: '{heading}' at level {level}; "
                f"delete is a no-op",
                file=sys.stderr,
            )
            return target
        if mode == "insert-after":
            raise LookupError(
                f"heading not found: '{heading}' at level {level} "
                f"(insert-after has no create-if-missing fallback)"
            )
        # replace / append
        if not create_if_missing:
            raise LookupError(
                f"heading not found: '{heading}' at level {level} "
                f"(pass --create-if-missing to append a new section instead)"
            )
        # Create a new section at EOF.
        content_lines = _normalize_content_lines(content or "")
        new_lines = list(body_lines)
        # Ensure separation before the new section.
        while new_lines and new_lines[-1].strip() == "":
            new_lines.pop()
        if new_lines:
            new_lines.append("")
        new_lines.append(f"{'#' * level} {heading}")
        new_lines.append("")
        new_lines.extend(content_lines)
    else:
        sec = matches[0]
        content_lines = _normalize_content_lines(content) if content is not None else []
        new_lines = list(body_lines)

        if mode == "replace":
            # Keep heading line; replace lines (start+1 .. end) with blank + content + blank.
            replacement = [""] + content_lines + [""]
            new_lines[sec.start + 1:sec.end] = replacement
        elif mode == "append":
            # Insert content_lines just before sec.end. Ensure a leading blank
            # line if the section body doesn't already end in one.
            insertion: list[str] = []
            # Determine if section body already ends in blank.
            tail_blank = (sec.end - 1 >= sec.start + 1) and \
                new_lines[sec.end - 1].strip() == ""
            if not tail_blank:
                insertion.append("")
            insertion.extend(content_lines)
            insertion.append("")
            new_lines[sec.end:sec.end] = insertion
        elif mode == "insert-after":
            # Caller provides the heading line themselves. Surround with blanks.
            insertion = [""] + content_lines + [""]
            new_lines[sec.end:sec.end] = insertion
        elif mode == "delete":
            # Drop the section entirely. Collapse surrounding double blanks.
            del new_lines[sec.start:sec.end]
            # Collapse: if both the line before and after the deletion site are
            # blank, drop one.
            i = sec.start
            if 0 < i < len(new_lines):
                if new_lines[i - 1].strip() == "" and new_lines[i].strip() == "":
                    del new_lines[i]

    # Reassemble file. Drop leading blanks in body and re-insert exactly one
    # separator blank line between frontmatter and body, so the output is
    # idempotent under repeated edits.
    while new_lines and new_lines[0].strip() == "":
        new_lines.pop(0)
    new_body = "\n".join(new_lines).rstrip() + "\n"
    if frontmatter_block:
        # frontmatter_block already ends in "\n"; add one blank line then body.
        new_content = frontmatter_block + "\n" + new_body
    else:
        new_content = new_body

    # Validate frontmatter still parses if it did before.
    if had_frontmatter:
        new_meta = parse_frontmatter(new_content)
        if not new_meta and original_meta:
            raise RuntimeError(
                "post-edit frontmatter failed to parse; aborting (file unchanged)"
            )

    if dry_run:
        return new_content

    tmp = target.with_suffix(target.suffix + ".tmp")
    try:
        tmp.write_text(new_content, encoding="utf-8")
        os.replace(tmp, target)
    except Exception:
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


# ---------------------------------------------------------------------------
# Cross-module split (split_module)
# ---------------------------------------------------------------------------
#
# split_module decomposes one source .dna/module.md into one source + N new
# modules, by extracting named H2 sections into freshly-initialized leaf
# modules. Atomicity unit is the COMMAND (not an fs syscall): all writes are
# staged into .tmp files first; if any validation / staging step fails, the
# .tmp files are unlinked and disk is untouched. Only after the full plan
# validates do we run init_module (which creates .dna/ + appends to index)
# for each new module and rewrite the source body in-place.
#
# Cross-module dependency references (other modules whose frontmatter
# `dependencies:` list mentions the source path) are SCAN-ONLY: they're
# reported back in the return dict for architect follow-up. This command
# does NOT mutate any other module's frontmatter — splitting one module
# should not silently rewrite the entire project's reference graph.

def split_module(
    source_mod_dir: Path,
    splits: list[dict],
    root: Path,
    dry_run: bool = False,
    keep_source: bool = True,
) -> dict:
    """Decompose `source_mod_dir`'s .dna/module.md into one source + N new modules.

    Parameters
    ----------
    source_mod_dir : Path
        Directory containing the source `.dna/module.md` to split.
    splits : list[dict]
        Each dict describes a new module to create:
            {
                "path": "<absolute or root-relative module dir>",
                "name": "<frontmatter name for new module>",
                "headings": ["## Foo", "## Bar"],   # H2 sections to move
                "owner": "<optional; defaults to source's owner>",
                "description": "<optional>",
            }
    root : Path
        Project root (the one containing .cbim/).
    dry_run : bool
        If True, validate and plan only; touch zero files; return the report
        with `created` listing the would-be paths.
    keep_source : bool
        If True (default), leave the split sections in source body and append
        an HTML comment beneath each migrated heading noting the new location.
        If False, remove the migrated sections from source entirely.

    Returns
    -------
    dict
        {
            "created": [<absolute Path of each new .dna/module.md>],
            "updated_source": bool,
            "dependency_refs": [
                {"module": "<rel path>", "dep_line": "<source rel path>",
                 "action_required": "..."},
                ...
            ],
        }

    Raises
    ------
    FileNotFoundError, ValueError, FileExistsError, LookupError
        Any precondition failure aborts before any disk write.
    """
    import os

    source_mod_dir = source_mod_dir.resolve()
    root = root.resolve()

    # --- 1. Validate source --------------------------------------------------
    source_aimod = source_mod_dir / ".dna"
    source_md = source_aimod / "module.md"
    if not source_md.is_file():
        raise FileNotFoundError(
            f"source module has no .dna/module.md: {source_md}"
        )

    source_raw = source_md.read_text(encoding="utf-8")
    source_meta = parse_frontmatter(source_raw)
    source_body = strip_frontmatter(source_raw)
    source_owner = source_meta.get("owner", "")

    try:
        source_rel = source_mod_dir.relative_to(root).as_posix()
    except ValueError:
        raise ValueError(
            f"source module {source_mod_dir} is not inside project root {root}"
        )

    # --- 2. Validate split specs --------------------------------------------
    if not splits:
        raise ValueError("splits must list at least one new module")

    norm_splits: list[dict] = []
    requested_headings: list[str] = []
    for i, spec in enumerate(splits):
        if not isinstance(spec, dict):
            raise ValueError(f"splits[{i}] must be a dict")
        if "path" not in spec or "name" not in spec or "headings" not in spec:
            raise ValueError(
                f"splits[{i}] missing required keys; need: path, name, headings"
            )
        if not spec["headings"] or not isinstance(spec["headings"], list):
            raise ValueError(
                f"splits[{i}].headings must be a non-empty list"
            )
        spec_path = Path(spec["path"])
        if not spec_path.is_absolute():
            spec_path = (root / spec_path).resolve()
        else:
            spec_path = spec_path.resolve()
        if (spec_path / ".dna").exists():
            raise FileExistsError(
                f"target module already has .dna/: {spec_path}"
            )
        # Headings are stored with their leading '## '; normalise to bare text
        # for the section finder.
        norm_headings = []
        for h in spec["headings"]:
            h = h.strip()
            if h.startswith("## "):
                h = h[3:].strip()
            elif h.startswith("##"):
                h = h[2:].strip()
            norm_headings.append(h)
            requested_headings.append(h)
        norm_splits.append({
            "path": spec_path,
            "name": spec["name"],
            "headings": norm_headings,
            "owner": spec.get("owner") or source_owner,
            "description": spec.get("description", ""),
        })

    # Reject overlap: same heading claimed by two splits.
    seen: set[str] = set()
    for h in requested_headings:
        if h in seen:
            raise ValueError(
                f"heading '{h}' claimed by more than one split target"
            )
        seen.add(h)

    # --- 3. Validate headings exist in source as H2 -------------------------
    sections = _split_sections(source_body)
    h2_index = {s.heading: s for s in sections if s.level == 2}
    missing = [h for h in requested_headings if h not in h2_index]
    if missing:
        raise LookupError(
            f"source module is missing required H2 headings: {missing}"
        )

    # --- 4. Build new body text for each split + new source body -----------
    body_lines = source_body.splitlines()

    extracted: dict[str, list[str]] = {}
    for h in requested_headings:
        sec = h2_index[h]
        extracted[h] = body_lines[sec.start:sec.end]

    # Build new source body. Two modes:
    #   keep_source=True  : leave section in place + append HTML comment beneath heading
    #   keep_source=False : drop the section entirely
    new_source_lines = list(body_lines)
    # Process from bottom up so prior indices stay valid.
    sec_list = sorted(
        [(h, h2_index[h]) for h in requested_headings],
        key=lambda x: x[1].start,
        reverse=True,
    )
    heading_to_dest: dict[str, str] = {}
    for split in norm_splits:
        try:
            dest_rel = split["path"].relative_to(root).as_posix()
        except ValueError:
            dest_rel = str(split["path"])
        for h in split["headings"]:
            heading_to_dest[h] = dest_rel

    if keep_source:
        for h, sec in sec_list:
            dest_rel = heading_to_dest[h]
            comment = f"<!-- split: moved '{h}' -> {dest_rel} -->"
            new_source_lines.insert(sec.start + 1, comment)
    else:
        for h, sec in sec_list:
            del new_source_lines[sec.start:sec.end]

    while new_source_lines and new_source_lines[-1].strip() == "":
        new_source_lines.pop()
    new_source_body = "\n".join(new_source_lines) + "\n" if new_source_lines else ""

    frontmatter_block, _ = _split_frontmatter_block(source_raw)
    if frontmatter_block:
        new_source_text = frontmatter_block + "\n" + new_source_body
    else:
        new_source_text = new_source_body

    # --- 5. Scan dependency references (SCAN ONLY, no mutation) -------------
    dependency_refs = _scan_dependency_refs(root, source_rel)

    # --- 6. Plan list of would-be-created paths -----------------------------
    created_paths = [
        (split["path"] / ".dna" / "module.md") for split in norm_splits
    ]

    if dry_run:
        return {
            "created": created_paths,
            "updated_source": True,
            "dependency_refs": dependency_refs,
        }

    # --- 7. Execute: stage source rewrite to .tmp first, then init each
    # new split (init_module creates .dna/ + appends to index), then sweep
    # the source rewrite with os.replace.
    #
    # Atomicity contract: if anything fails after .tmp staging, we unlink
    # the .tmp and roll back every newly-created .dna/ dir + corresponding
    # index.md entry, leaving the source file untouched.

    source_tmp = source_md.with_suffix(source_md.suffix + ".tmp")
    try:
        source_tmp.write_text(new_source_text, encoding="utf-8")
    except Exception:
        if source_tmp.exists():
            try:
                source_tmp.unlink()
            except OSError:
                pass
        raise

    created_dirs: list[Path] = []
    try:
        for split in norm_splits:
            # ContextPack mandates status='spec' for new splits (task-12 dep).
            try:
                init_module(
                    split["path"],
                    name=split["name"],
                    owner=split["owner"],
                    description=split["description"],
                    type_="leaf",
                    project_root=root,
                    status="spec",
                )
            except TypeError:
                # task-12 (status field on init_module) not yet landed in
                # this checkout. Fall back to current signature so split is
                # usable in dev; the architect will see the missing status
                # field and can fix it manually once task-12 ships.
                init_module(
                    split["path"],
                    name=split["name"],
                    owner=split["owner"],
                    description=split["description"],
                    type_="leaf",
                    project_root=root,
                )
            created_dirs.append(split["path"] / ".dna")

            # Populate body with the extracted sections (frontmatter intact).
            body_chunks: list[str] = []
            for h in split["headings"]:
                lines = extracted[h]
                body_chunks.append("\n".join(lines))
            new_body = "\n\n".join(body_chunks) + "\n"
            write_module_doc(split["path"], "module.md", new_body)

        os.replace(source_tmp, source_md)

    except Exception:
        if source_tmp.exists():
            try:
                source_tmp.unlink()
            except OSError:
                pass
        for d in created_dirs:
            _rm_rf(d)
            parent = d.parent
            try:
                if parent.is_dir() and not any(parent.iterdir()):
                    parent.rmdir()
            except OSError:
                pass
        _rollback_index_entries(
            root,
            [d.parent for d in created_dirs],
        )
        raise

    return {
        "created": created_paths,
        "updated_source": True,
        "dependency_refs": dependency_refs,
    }


def _scan_dependency_refs(root: Path, source_rel: str) -> list[dict]:
    """Report every module whose frontmatter `dependencies:` mentions
    `source_rel`. SCAN ONLY — no mutation.

    The split command surfaces these so the architect can manually rewrite
    each affected module's dependencies afterward via `cbim dna edit`.
    """
    refs: list[dict] = []
    for mod_dict in _scan_modules(root):
        deps = mod_dict.get("dependencies") or []
        if not isinstance(deps, list):
            continue
        for dep in deps:
            if isinstance(dep, str) and dep.strip() == source_rel:
                refs.append({
                    "module": mod_dict["path"],
                    "dep_line": dep,
                    "action_required": (
                        f"`dependencies:` lists '{source_rel}'; consider "
                        f"updating to point at the new split target(s)."
                    ),
                })
                break
    return refs


def _rm_rf(p: Path) -> None:
    """Best-effort recursive delete; suppress errors (called during rollback)."""
    if not p.exists():
        return
    try:
        if p.is_file() or p.is_symlink():
            p.unlink()
            return
        for child in p.iterdir():
            _rm_rf(child)
        p.rmdir()
    except OSError:
        pass


def _rollback_index_entries(root: Path, mod_dirs: list[Path]) -> None:
    """Remove a list of module-dir paths from .cbim/index.md.

    Used by split_module's rollback path to undo the per-module appends
    init_module made before the overall command failed.
    """
    if not mod_dirs:
        return
    try:
        existing = read_index(root)
    except Exception:
        return
    to_remove: set[str] = set()
    for d in mod_dirs:
        try:
            rel = d.resolve().relative_to(root.resolve()).as_posix()
            to_remove.add(rel)
        except ValueError:
            continue
    remaining = [p for p in existing if p not in to_remove]
    try:
        _write_index(root, remaining)
    except Exception:
        pass
