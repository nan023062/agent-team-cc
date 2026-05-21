"""Tests for `dna write-doc` — body-content write into module.md / contract.md.

Covers the contract in cbim_kernel.cbi.engine.modules.write_module_doc and the
argparse-level cmd_modules_write_doc in cbim_kernel.cbi.engine.cli.

Scope:
  - frontmatter on module.md is preserved byte-for-byte; only the body is replaced
  - contract.md can be created (no prior file) or replaced
  - rejects file names other than module.md / contract.md
  - rejects a module dir without a .dna/ subdirectory
  - atomic write: a mid-write failure leaves the original file intact and no
    .tmp residue
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from cbim_kernel.cbi.engine.modules import write_module_doc
from cbim_kernel.cbi.engine.cli import cmd_modules_write_doc


# --- helpers --------------------------------------------------------------


def _make_module(tmp_path: Path, *, with_module_md: bool = True,
                 with_contract: bool = False,
                 module_md_content: str | None = None) -> Path:
    """Create a fake module directory with a .dna/ subdir. Returns mod_dir."""
    mod = tmp_path / "mymod"
    (mod / ".dna").mkdir(parents=True)
    if with_module_md:
        if module_md_content is None:
            module_md_content = (
                "---\n"
                "name: mymod\n"
                "owner: someone\n"
                "description: placeholder\n"
                "keywords: []\n"
                "dependencies: []\n"
                "---\n\n"
                "## Old Body\n\nplaceholder text\n"
            )
        (mod / ".dna" / "module.md").write_text(module_md_content, encoding="utf-8")
    if with_contract:
        (mod / ".dna" / "contract.md").write_text(
            "# Old Contract\n\noriginal interfaces\n", encoding="utf-8"
        )
    return mod


def _ns(**kw) -> argparse.Namespace:
    """Build a Namespace with the four CLI fields the cmd expects."""
    return argparse.Namespace(
        module_path=kw.get("module_path"),
        file=kw.get("file"),
        content=kw.get("content"),
        content_file=kw.get("content_file"),
    )


# --- write_module_doc: frontmatter preservation ---------------------------


def test_write_module_md_preserves_frontmatter(tmp_path):
    mod = _make_module(tmp_path)
    new_body = "## New Body\n\nfresh content from architect\n"

    written = write_module_doc(mod, "module.md", new_body)

    assert written == (mod / ".dna" / "module.md").resolve()
    out = written.read_text(encoding="utf-8")

    # Frontmatter is preserved byte-for-byte
    assert out.startswith(
        "---\n"
        "name: mymod\n"
        "owner: someone\n"
        "description: placeholder\n"
        "keywords: []\n"
        "dependencies: []\n"
        "---\n"
    )
    # Old body gone, new body present
    assert "Old Body" not in out
    assert "## New Body" in out
    assert "fresh content from architect" in out


def test_write_module_md_handles_body_without_trailing_newline(tmp_path):
    mod = _make_module(tmp_path)
    written = write_module_doc(mod, "module.md", "## X\n\nno trailing newline")
    out = written.read_text(encoding="utf-8")
    assert out.endswith("\n"), "writer must guarantee final newline"
    assert "## X" in out


def test_write_module_md_no_frontmatter_overwrites_whole_file(tmp_path):
    # If module.md somehow has no frontmatter, the whole file is body.
    mod = _make_module(
        tmp_path,
        module_md_content="just a body, no frontmatter\n",
    )
    written = write_module_doc(mod, "module.md", "## Brand New\n")
    out = written.read_text(encoding="utf-8")
    assert out == "## Brand New\n"


# --- write_module_doc: contract.md create/replace -------------------------


def test_write_contract_md_creates_when_missing(tmp_path):
    mod = _make_module(tmp_path, with_contract=False)
    contract_body = "# Contract\n\n## Interfaces\n\n- foo(x): y\n"

    written = write_module_doc(mod, "contract.md", contract_body)

    assert written.exists()
    assert written.read_text(encoding="utf-8") == contract_body


def test_write_contract_md_replaces_existing(tmp_path):
    mod = _make_module(tmp_path, with_contract=True)
    new = "# New Contract\n\n## Events\n\n- onTick\n"

    write_module_doc(mod, "contract.md", new)

    assert (mod / ".dna" / "contract.md").read_text(encoding="utf-8") == new


def test_write_contract_md_preserves_frontmatter_if_present(tmp_path):
    mod = _make_module(tmp_path)
    (mod / ".dna" / "contract.md").write_text(
        "---\nname: x\n---\n\nold body\n", encoding="utf-8"
    )
    write_module_doc(mod, "contract.md", "new body\n")
    out = (mod / ".dna" / "contract.md").read_text(encoding="utf-8")
    assert out.startswith("---\nname: x\n---\n")
    assert "old body" not in out
    assert "new body" in out


# --- write_module_doc: validation -----------------------------------------


def test_rejects_disallowed_file_name(tmp_path):
    mod = _make_module(tmp_path)
    with pytest.raises(ValueError, match="must be one of"):
        write_module_doc(mod, "index.md", "anything")
    with pytest.raises(ValueError):
        write_module_doc(mod, "../escape.md", "anything")
    with pytest.raises(ValueError):
        write_module_doc(mod, "module.json", "anything")


def test_rejects_uninitialized_module(tmp_path):
    mod = tmp_path / "no_dna_here"
    mod.mkdir()
    with pytest.raises(FileNotFoundError, match="not initialized"):
        write_module_doc(mod, "module.md", "body\n")


# --- write_module_doc: atomicity ------------------------------------------


def test_atomic_write_failure_leaves_original_intact(tmp_path, monkeypatch):
    """Simulate os.replace blowing up; original file must survive and no .tmp
    must be visible to subsequent readers."""
    import os

    mod = _make_module(tmp_path)
    target = mod / ".dna" / "module.md"
    original = target.read_text(encoding="utf-8")

    real_replace = os.replace

    def boom(src, dst):  # noqa: ARG001
        raise OSError("simulated disk failure")

    monkeypatch.setattr("os.replace", boom)

    with pytest.raises(OSError, match="simulated"):
        write_module_doc(mod, "module.md", "## should not land\n")

    # restore for any downstream side effects
    monkeypatch.setattr("os.replace", real_replace)

    # Original file untouched
    assert target.read_text(encoding="utf-8") == original
    # No leftover .tmp
    tmp_residue = list((mod / ".dna").glob("*.tmp"))
    assert tmp_residue == [], f"unexpected tmp residue: {tmp_residue}"


# --- CLI wrapper ----------------------------------------------------------


def test_cli_inline_content(tmp_path, capsys):
    mod = _make_module(tmp_path)
    rc = cmd_modules_write_doc(_ns(
        module_path=str(mod),
        file="module.md",
        content="## CLI Body\n",
    ))
    assert rc == 0
    captured = capsys.readouterr().out.strip()
    assert captured == str((mod / ".dna" / "module.md").resolve())
    assert "## CLI Body" in (mod / ".dna" / "module.md").read_text(encoding="utf-8")


def test_cli_content_file(tmp_path):
    mod = _make_module(tmp_path)
    src = tmp_path / "src.md"
    src.write_text("## From File\n\nbig content here\n", encoding="utf-8")

    rc = cmd_modules_write_doc(_ns(
        module_path=str(mod),
        file="contract.md",
        content_file=str(src),
    ))
    assert rc == 0
    assert (mod / ".dna" / "contract.md").read_text(encoding="utf-8") == \
        "## From File\n\nbig content here\n"


def test_cli_requires_content_source(tmp_path, capsys):
    mod = _make_module(tmp_path)
    rc = cmd_modules_write_doc(_ns(module_path=str(mod), file="module.md"))
    assert rc == 1
    assert "required" in capsys.readouterr().err


def test_cli_rejects_both_content_sources(tmp_path, capsys):
    mod = _make_module(tmp_path)
    rc = cmd_modules_write_doc(_ns(
        module_path=str(mod),
        file="module.md",
        content="x",
        content_file="y",
    ))
    assert rc == 1
    assert "mutually exclusive" in capsys.readouterr().err


def test_cli_missing_content_file(tmp_path, capsys):
    mod = _make_module(tmp_path)
    rc = cmd_modules_write_doc(_ns(
        module_path=str(mod),
        file="module.md",
        content_file=str(tmp_path / "does_not_exist.md"),
    ))
    assert rc == 1
    assert "not found" in capsys.readouterr().err


def test_cli_rejects_bad_file_name(tmp_path, capsys):
    mod = _make_module(tmp_path)
    rc = cmd_modules_write_doc(_ns(
        module_path=str(mod),
        file="readme.md",
        content="x",
    ))
    assert rc == 1
    assert "must be one of" in capsys.readouterr().err


def test_cli_rejects_uninitialized_module(tmp_path, capsys):
    mod = tmp_path / "bare"
    mod.mkdir()
    rc = cmd_modules_write_doc(_ns(
        module_path=str(mod),
        file="module.md",
        content="x",
    ))
    assert rc == 1
    assert "not initialized" in capsys.readouterr().err
