"""Unit tests for engine.audit.checks.dna_fission."""
from __future__ import annotations

from pathlib import Path

from engine.audit.checks.dna_fission import check


def _seed(root: Path) -> None:
    (root / ".cbim").mkdir(parents=True)
    (root / ".cbim" / "index.md").write_text("# Module Index\n\n- alpha\n", encoding="utf-8")


def _make_module(root: Path, rel: str, body_lines: int, workflows: int) -> None:
    mod = root / rel
    dna = mod / ".dna"
    dna.mkdir(parents=True)
    body = "\n".join(f"line {i}" for i in range(body_lines)) if body_lines > 0 else ""
    dna.joinpath("module.md").write_text(
        f"---\nname: {rel}\nowner: x\ndescription: m\n---\n\n{body}\n",
        encoding="utf-8",
    )
    if workflows > 0:
        wf_dir = dna / "workflows"
        wf_dir.mkdir()
        for i in range(workflows):
            d = wf_dir / f"wf{i}"
            d.mkdir()
            d.joinpath("workflow.md").write_text(
                f"---\nname: wf{i}\n---\n\nstep\n", encoding="utf-8"
            )


def test_clean_module_no_findings(tmp_path):
    _seed(tmp_path)
    _make_module(tmp_path, "alpha", body_lines=10, workflows=1)
    findings = check(tmp_path, {"dna_fission": {"max_body_lines": 350, "max_workflow_count": 8}})
    assert findings == []


def test_body_oversize_warn(tmp_path):
    _seed(tmp_path)
    _make_module(tmp_path, "alpha", body_lines=120, workflows=0)
    findings = check(tmp_path, {"dna_fission": {"max_body_lines": 100, "max_workflow_count": 8}})
    body_f = [f for f in findings if f.code == "DNA_BODY_OVERSIZE"]
    assert len(body_f) == 1
    assert body_f[0].severity == "warn"


def test_body_oversize_error_band(tmp_path):
    _seed(tmp_path)
    _make_module(tmp_path, "alpha", body_lines=160, workflows=0)
    findings = check(tmp_path, {"dna_fission": {"max_body_lines": 100, "max_workflow_count": 8}})
    body_f = next(f for f in findings if f.code == "DNA_BODY_OVERSIZE")
    assert body_f.severity == "error"


def test_body_info_band(tmp_path):
    _seed(tmp_path)
    _make_module(tmp_path, "alpha", body_lines=85, workflows=0)
    findings = check(tmp_path, {"dna_fission": {"max_body_lines": 100, "max_workflow_count": 8}})
    body_f = next(f for f in findings if f.code == "DNA_BODY_OVERSIZE")
    assert body_f.severity == "info"


def test_workflow_overload(tmp_path):
    _seed(tmp_path)
    _make_module(tmp_path, "alpha", body_lines=5, workflows=10)
    findings = check(tmp_path, {"dna_fission": {"max_body_lines": 999, "max_workflow_count": 8}})
    wf = [f for f in findings if f.code == "DNA_WORKFLOW_OVERLOAD"]
    assert len(wf) == 1
    assert wf[0].severity == "warn"
