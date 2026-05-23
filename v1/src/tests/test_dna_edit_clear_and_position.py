"""Tests for Phase 3a CLI extensions: --clear, --insert-after, --insert-at-top.

Coverage:
  - CLI payload builders accept --clear and convert to value_list=[]
  - CLI three-way mutex (--value / --value-list / --clear) reports correctly
  - CLI position flags (--insert-after / --insert-at-top) reach the payload
  - Body.write_section honours position kwargs on the create-if-missing path
  - Body.write_section raises when --insert-after target heading is absent
  - Service round-trip: edit a module then reload → frontmatter cleared and
    new section sits at the right location.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from cbi.resources._body import Body
from engine.cli import (
    _build_dna_edit_payload,
    _build_agent_update_payload,
)
from services import edit_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dna_ns(**kw) -> argparse.Namespace:
    """Build a Namespace with every dna-edit flag defaulted to its argparse default."""
    defaults = dict(
        target=None, field=None, value=None, value_list=None, clear=False,
        content=None, content_file=None, stdin=False,
        heading=None, level=2, mode=None, name=None,
        create_if_missing=False, insert_after=None, insert_at_top=False,
        dry_run=False, module_path="dummy",
    )
    defaults.update(kw)
    return argparse.Namespace(**defaults)


def _agent_ns(**kw) -> argparse.Namespace:
    defaults = dict(
        target=None, field=None, value=None, value_list=None, clear=False,
        content=None, content_file=None, stdin=False,
        heading=None, level=2, mode=None,
        create_if_missing=False, insert_after=None, insert_at_top=False,
        dry_run=False, name="dummy",
    )
    defaults.update(kw)
    return argparse.Namespace(**defaults)


def _make_project(tmp_path: Path) -> Path:
    """Minimum project root: .cbim/config.json + root .dna/module.md + index.md."""
    (tmp_path / ".cbim").mkdir()
    (tmp_path / ".cbim" / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".dna").mkdir()
    (tmp_path / ".dna" / "module.md").write_text(
        "---\nname: root\nowner: arch\ndescription: rt\n"
        "keywords: []\ndependencies: []\n---\n\n## Positioning\n\nroot\n",
        encoding="utf-8",
    )
    (tmp_path / "index.md").write_text("# Index\n", encoding="utf-8")
    return tmp_path


def _make_module(root: Path, rel: str, body: str = "## Old\n\nbody\n",
                 deps: list[str] | None = None) -> Path:
    mod = root / rel
    (mod / ".dna").mkdir(parents=True)
    deps_block = "dependencies: []\n"
    if deps:
        deps_block = "dependencies:\n" + "".join(f"  - {d}\n" for d in deps)
    (mod / ".dna" / "module.md").write_text(
        f"---\nname: {rel}\nowner: arch\ndescription: x\n"
        f"keywords: []\n{deps_block}---\n\n{body}",
        encoding="utf-8",
    )
    return mod


# ---------------------------------------------------------------------------
# CLI payload builders — --clear and three-way mutex
# ---------------------------------------------------------------------------

def test_dna_clear_sets_empty_list_payload():
    payload = _build_dna_edit_payload(
        _dna_ns(target="frontmatter", field="dependencies", clear=True),
        "frontmatter",
    )
    assert payload == {"field": "dependencies", "value_list": []}


def test_agent_clear_sets_empty_list_payload():
    # `tools` isn't list-typed in current schema but CLI builder doesn't know
    # that — schema validation lives in the service layer.
    payload = _build_agent_update_payload(
        _agent_ns(target="frontmatter", field="tools", clear=True),
        "frontmatter",
    )
    assert payload == {"field": "tools", "value_list": []}


def test_dna_three_way_mutex_value_and_clear():
    with pytest.raises(ValueError, match="mutually exclusive"):
        _build_dna_edit_payload(
            _dna_ns(target="frontmatter", field="dependencies",
                    value="x", clear=True),
            "frontmatter",
        )


def test_dna_three_way_mutex_value_list_and_clear():
    with pytest.raises(ValueError, match="mutually exclusive"):
        _build_dna_edit_payload(
            _dna_ns(target="frontmatter", field="dependencies",
                    value_list=["x"], clear=True),
            "frontmatter",
        )


def test_dna_three_way_mutex_none_given():
    with pytest.raises(ValueError, match="one of --value"):
        _build_dna_edit_payload(
            _dna_ns(target="frontmatter", field="dependencies"),
            "frontmatter",
        )


def test_dna_status_rejects_clear():
    with pytest.raises(ValueError, match="status.*scalar enum"):
        _build_dna_edit_payload(
            _dna_ns(target="frontmatter", field="status", clear=True),
            "frontmatter",
        )


# ---------------------------------------------------------------------------
# CLI payload builders — position flags reach the payload
# ---------------------------------------------------------------------------

def test_dna_section_payload_includes_insert_after():
    payload = _build_dna_edit_payload(
        _dna_ns(target="section", heading="New", content="body",
                create_if_missing=True, insert_after="Positioning"),
        "section",
    )
    assert payload["insert_after"] == "Positioning"
    assert payload["insert_at_top"] is False


def test_dna_section_payload_includes_insert_at_top():
    payload = _build_dna_edit_payload(
        _dna_ns(target="section", heading="New", content="body",
                create_if_missing=True, insert_at_top=True),
        "section",
    )
    assert payload["insert_at_top"] is True
    assert payload["insert_after"] is None


def test_agent_section_payload_includes_position_flags():
    payload = _build_agent_update_payload(
        _agent_ns(target="section", heading="New", content="body",
                  create_if_missing=True, insert_at_top=True),
        "section",
    )
    assert payload["insert_at_top"] is True


# ---------------------------------------------------------------------------
# Body position resolver — direct primitive tests
# ---------------------------------------------------------------------------

_BODY_TEXT = (
    "## Positioning\n\nstuff\n\n"
    "## Non-Goals\n\nthings\n\n"
    "## Deprecation\n\nlegacy notice\n"
)


def test_body_insert_at_top_places_new_section_first():
    b = Body(_BODY_TEXT)
    b.write_section("Brand New", "fresh\n", level=2,
                    create_if_missing=True, insert_at_top=True)
    out = b.read()
    headings = [ln for ln in out.splitlines() if ln.startswith("## ")]
    assert headings[0] == "## Brand New"


def test_body_insert_after_places_section_after_target():
    b = Body(_BODY_TEXT)
    b.write_section("Inserted", "x\n", level=2,
                    create_if_missing=True, insert_after="Positioning")
    out = b.read()
    headings = [ln for ln in out.splitlines() if ln.startswith("## ")]
    assert headings == ["## Positioning", "## Inserted", "## Non-Goals", "## Deprecation"]


def test_body_insert_after_missing_target_raises():
    b = Body(_BODY_TEXT)
    with pytest.raises(ValueError, match="insert-after.*not found"):
        b.write_section("Inserted", "x\n", level=2,
                        create_if_missing=True, insert_after="NoSuchHeading")


def test_body_position_flags_mutually_exclusive():
    b = Body(_BODY_TEXT)
    with pytest.raises(ValueError, match="mutually exclusive"):
        b.write_section("X", "y\n", level=2, create_if_missing=True,
                        insert_after="Positioning", insert_at_top=True)


def test_body_position_flags_ignored_when_heading_exists():
    b = Body(_BODY_TEXT)
    # 'Positioning' already exists — position flags are no-ops; replace works.
    b.write_section("Positioning", "replaced text\n", level=2,
                    mode="replace", insert_at_top=True)
    out = b.read()
    assert "replaced text" in out
    headings = [ln for ln in out.splitlines() if ln.startswith("## ")]
    assert headings == ["## Positioning", "## Non-Goals", "## Deprecation"]


def test_body_insert_at_top_into_empty_body():
    b = Body("")
    b.write_section("First", "hello\n", level=2,
                    create_if_missing=True, insert_at_top=True)
    out = b.read()
    assert out.startswith("## First")


# ---------------------------------------------------------------------------
# Service round-trip — knowledge_service.edit_module
# ---------------------------------------------------------------------------

def test_service_clear_dependencies_round_trip(tmp_path):
    root = _make_project(tmp_path)
    mod = _make_module(root, "mymod",
                       deps=["foo/bar", "baz"])

    edit_module(mod, "frontmatter",
                {"field": "dependencies", "value_list": []},
                cwd=str(root))

    out = (mod / ".dna" / "module.md").read_text(encoding="utf-8")
    # YAML may render as either `dependencies: []` or `dependencies:` with no
    # items; both are valid empty-list representations.
    assert "foo/bar" not in out
    assert "baz" not in out
    assert "dependencies:" in out


def test_service_clear_rejects_non_list_field(tmp_path):
    root = _make_project(tmp_path)
    mod = _make_module(root, "mymod")
    with pytest.raises(ValueError, match="not list-typed"):
        edit_module(mod, "frontmatter",
                    {"field": "description", "value_list": []},
                    cwd=str(root))


def test_service_insert_at_top_round_trip(tmp_path):
    root = _make_project(tmp_path)
    body = (
        "## Positioning\n\nstuff\n\n"
        "## Non-Goals\n\nthings\n\n"
        "## Deprecation\n\nlegacy notice\n"
    )
    mod = _make_module(root, "mymod", body=body)

    # Pull Deprecation up to the top: delete then re-insert at top.
    edit_module(mod, "section",
                {"heading": "Deprecation", "mode": "delete", "level": 2},
                cwd=str(root))
    edit_module(mod, "section",
                {"heading": "Deprecation",
                 "content": "legacy notice\n",
                 "mode": "replace", "level": 2,
                 "create_if_missing": True,
                 "insert_at_top": True},
                cwd=str(root))

    out = (mod / ".dna" / "module.md").read_text(encoding="utf-8")
    headings = [ln for ln in out.splitlines() if ln.startswith("## ")]
    assert headings[0] == "## Deprecation"
    assert "legacy notice" in out
