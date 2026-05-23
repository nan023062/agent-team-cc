"""Unit tests for engine.audit.checks.dna_tree."""
from __future__ import annotations

from pathlib import Path

from engine.audit.checks.dna_tree import check


def _seed(root: Path, index_entries: list[str]) -> None:
    (root / ".cbim").mkdir(parents=True)
    lines = ["# Module Index", ""] + [f"- {e}" for e in index_entries]
    (root / ".cbim" / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _make_module(root: Path, rel: str, deps: list[str] | None = None) -> None:
    mod = root if rel == "." else (root / rel)
    dna = mod / ".dna"
    dna.mkdir(parents=True)
    fm = ["---", f"name: {rel}", "owner: x", "description: m"]
    if deps:
        fm.append("dependencies:")
        for d in deps:
            fm.append(f"  - {d}")
    else:
        fm.append("dependencies: []")
    fm.append("---")
    (dna / "module.md").write_text("\n".join(fm) + "\n\nbody\n", encoding="utf-8")


def test_clean_tree_no_findings(tmp_path):
    _seed(tmp_path, [".", "alpha", "beta"])
    _make_module(tmp_path, ".")
    _make_module(tmp_path, "alpha", deps=["beta"])
    _make_module(tmp_path, "beta")
    assert check(tmp_path, {}) == []


def test_orphan_warn(tmp_path):
    _seed(tmp_path, ["alpha/beta"])
    _make_module(tmp_path, "alpha/beta")
    findings = check(tmp_path, {})
    orphans = [f for f in findings if f.code == "TREE_ORPHAN"]
    assert len(orphans) == 1
    assert orphans[0].severity == "warn"
    assert orphans[0].target == "alpha/beta"


def test_dep_dangling(tmp_path):
    _seed(tmp_path, [".", "alpha"])
    _make_module(tmp_path, ".")
    _make_module(tmp_path, "alpha", deps=["ghost"])
    findings = check(tmp_path, {})
    dangling = [f for f in findings if f.code == "TREE_DEP_DANGLING"]
    assert len(dangling) == 1


def test_dep_ancestor_declared(tmp_path):
    _seed(tmp_path, [".", "alpha", "alpha/child"])
    _make_module(tmp_path, ".")
    _make_module(tmp_path, "alpha")
    _make_module(tmp_path, "alpha/child", deps=["alpha"])
    findings = check(tmp_path, {})
    anc = [f for f in findings if f.code == "TREE_DEP_ANCESTOR_DECLARED"]
    assert len(anc) == 1
    assert anc[0].target == "alpha/child"
    assert anc[0].metadata["dep"] == "alpha"
    assert [f for f in findings if f.code == "TREE_DEP_UP_TREE"] == []


def test_dep_ancestor_declared_root(tmp_path):
    _seed(tmp_path, [".", "alpha"])
    _make_module(tmp_path, ".")
    _make_module(tmp_path, "alpha", deps=["."])
    findings = check(tmp_path, {})
    anc = [f for f in findings if f.code == "TREE_DEP_ANCESTOR_DECLARED"]
    assert len(anc) == 1
    assert anc[0].metadata["dep"] == "."


def test_dep_cycle_error(tmp_path):
    _seed(tmp_path, [".", "alpha", "beta"])
    _make_module(tmp_path, ".")
    _make_module(tmp_path, "alpha", deps=["beta"])
    _make_module(tmp_path, "beta", deps=["alpha"])
    findings = check(tmp_path, {})
    cycles = [f for f in findings if f.code == "TREE_CYCLE"]
    assert len(cycles) == 1
    assert cycles[0].severity == "error"
    assert set(cycles[0].metadata["cycle"]) == {"alpha", "beta"}
