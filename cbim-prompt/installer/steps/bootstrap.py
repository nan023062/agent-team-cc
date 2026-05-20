"""
bootstrap.py — Copy cbim-prompt/ -> .cbim-prompt/, write CLAUDE.md, create memory
store + module registry, update .gitignore / .claudeignore.
"""

import shutil
from pathlib import Path

from cbi.coordinator.agent import ASSISTANT_MD as CLAUDE_MD


# Directories never copied into the install destination.
_COPY_SKIP_DIRS = {"__pycache__", "store", ".chroma"}
# Top-level paths in cbim-prompt/ that are runtime data and should not be
# shipped into a fresh install.
_COPY_SKIP_TOP = {"memory/store"}


def _ok(text: str) -> None:
    print(f"    + {text}")


def _skip(text: str) -> None:
    print(f"    - {text}  (skipped)")


def _copy_tree(src: Path, dst: Path) -> None:
    """Copy src tree into dst, skipping caches and runtime data.

    Preserves runtime-managed paths across reinstalls:
      - dst/.dna/            module registry (architect-managed)
      - dst/memory/store/    short/medium memory tiers (Stop hook-managed)

    Everything else under dst is wiped to guarantee framework files match
    the source version after install.
    """
    preserved: dict[str, bytes] = {}
    registry = dst / ".dna" / "index.md"
    store = dst / "memory" / "store"

    if dst.exists():
        # Stash the registry so we don't lose module bookkeeping.
        if registry.exists():
            preserved["registry"] = registry.read_bytes()
        # Stash memory store paths -> bytes (small, file backend is plain md).
        stash: dict[str, bytes] = {}
        if store.exists():
            for p in store.rglob("*"):
                if p.is_file():
                    stash[str(p.relative_to(store))] = p.read_bytes()
        preserved["store"] = stash  # type: ignore[assignment]
        shutil.rmtree(str(dst))

    shutil.copytree(
        str(src), str(dst),
        ignore=shutil.ignore_patterns(
            "__pycache__", "*.pyc", ".chroma", ".preview.pid",
        ),
    )

    # Drop any memory/store contents that snuck in via the source tree.
    fresh_store = dst / "memory" / "store"
    if fresh_store.exists():
        shutil.rmtree(str(fresh_store))

    # Restore preserved registry, if any.
    if "registry" in preserved:
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_bytes(preserved["registry"])  # type: ignore[arg-type]
    # Restore preserved memory store, if any.
    stash = preserved.get("store", {})  # type: ignore[assignment]
    if stash:
        for rel, data in stash.items():
            target = store / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)


def copy_framework(cbim_src: Path, root: Path) -> Path:
    """Copy cbim-prompt/ as .cbim-prompt/ inside the project root.

    Returns the destination path (.cbim-prompt/).
    """
    dst = root / ".cbim-prompt"
    _copy_tree(cbim_src, dst)
    _ok(f"copied cbim-prompt/ -> {dst.relative_to(root)}/")
    return dst


def write_claude_md(root: Path) -> None:
    dst = root / "CLAUDE.md"
    if dst.exists():
        existing = dst.read_text(encoding="utf-8")
        if existing == CLAUDE_MD:
            _skip("CLAUDE.md already current")
            return
        bak = root / "CLAUDE.md.bak"
        bak.write_text(existing, encoding="utf-8")
        dst.write_text(CLAUDE_MD, encoding="utf-8")
        _ok(f"overwrote CLAUDE.md with latest template (old saved to {bak.name})")
    else:
        dst.write_text(CLAUDE_MD, encoding="utf-8")
        _ok("created CLAUDE.md")


def ensure_store(cbim_dst: Path) -> None:
    for d in ("short", "medium"):
        (cbim_dst / "memory" / "store" / d).mkdir(parents=True, exist_ok=True)
    _ok(".cbim-prompt/memory/store/{short,medium}/ ready")


def ensure_registry(cbim_dst: Path, root: Path) -> None:
    """Create .cbim-prompt/.dna/index.md (the module registry).

    The cbi.engine.modules helpers expect a project layout where the registry
    lives at <project-root>/.cbim-prompt/.dna/index.md (renamed from the legacy
    cbim-prompt/.dna/index.md location). We seed it with a fresh filesystem
    scan if nothing exists yet.
    """
    # cbi is already importable from the source cbim-prompt/ (install.py
    # inserts it into sys.path). Don't re-insert cbim_dst — namespace package
    # aggregation would then drop __pycache__ into the user-facing
    # .cbim-prompt/ tree.
    from cbi.engine.modules import ensure_registry as _ensure, update_index, read_index

    pre_path = root / ".cbim-prompt" / ".dna" / "index.md"
    existed_before = pre_path.exists()
    before = pre_path.read_text(encoding="utf-8") if existed_before else ""
    idx = _ensure(root)
    if existed_before:
        # Preserved by _copy_tree; only rescan if it was the empty seed and we
        # find existing modules on disk.
        if before.strip() == "# Module Index":
            update_index(root)
            n = len(read_index(root))
            if n:
                _ok(f"refreshed {idx.relative_to(root)}  (seeded with {n} existing module(s))")
            else:
                _skip(f"{idx.relative_to(root)} already exists (empty)")
        else:
            _skip(f"{idx.relative_to(root)} already exists")
    else:
        update_index(root)
        n = len(read_index(root))
        if n:
            _ok(f"created {idx.relative_to(root)}  (seeded with {n} existing module(s))")
        else:
            _ok(f"created {idx.relative_to(root)}  (empty — architect will populate)")


def update_gitignore(root: Path) -> None:
    gitignore = root / ".gitignore"
    needed = [".cbim-prompt/memory/store/", "__pycache__/", "*.pyc", ".venv/"]
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    missing = [e for e in needed if e not in existing]
    if missing:
        with gitignore.open("a", encoding="utf-8") as f:
            if existing and not existing.endswith("\n"):
                f.write("\n")
            f.write("\n".join(missing) + "\n")
        _ok(f".gitignore <- {', '.join(missing)}")
    else:
        _skip(".gitignore already up to date")


def update_claudeignore(root: Path) -> None:
    claudeignore = root / ".claudeignore"
    needed = [".cbim-prompt/", "**/.dna/"]
    existing = claudeignore.read_text(encoding="utf-8") if claudeignore.exists() else ""
    missing = [e for e in needed if e not in existing]
    if missing:
        with claudeignore.open("a", encoding="utf-8") as f:
            if not existing:
                f.write("# CBIM framework files — access via skill Python scripts only\n")
            elif not existing.endswith("\n"):
                f.write("\n")
            f.write("\n".join(missing) + "\n")
        _ok(f".claudeignore <- {', '.join(missing)}")
    else:
        _skip(".claudeignore already up to date")
