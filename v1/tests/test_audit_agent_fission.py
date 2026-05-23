"""Unit tests for engine.audit.checks.agent_fission."""
from __future__ import annotations

from pathlib import Path

from engine.audit.checks._agent_skill_parser import count_skills
from engine.audit.checks.agent_fission import check


def _seed(root: Path) -> None:
    (root / ".cbim").mkdir(parents=True)
    (root / ".claude" / "agents").mkdir(parents=True)


def _make_agent(root: Path, name: str, body_lines: int, skill_files: int = 0,
                skills_section: str = "") -> None:
    d = root / ".claude" / "agents" / name
    d.mkdir(parents=True)
    body = "\n".join(f"line {i}" for i in range(body_lines))
    md = (
        f"---\nname: {name}\ndescription: test\nmodel: x\n---\n\n"
        f"{body}\n{skills_section}\n"
    )
    d.joinpath(f"{name}.md").write_text(md, encoding="utf-8")
    if skill_files:
        sd = d / "skills"
        sd.mkdir()
        for i in range(skill_files):
            sd.joinpath(f"s{i}.md").write_text("---\n---\n\nbody\n", encoding="utf-8")


def test_clean_agent_no_findings(tmp_path):
    _seed(tmp_path)
    _make_agent(tmp_path, "worker", body_lines=10, skill_files=2)
    findings = check(tmp_path, {"agent_fission": {"max_body_lines": 250, "max_skill_count": 6}})
    assert findings == []


def test_body_oversize_warn(tmp_path):
    _seed(tmp_path)
    _make_agent(tmp_path, "worker", body_lines=120)
    findings = check(tmp_path, {"agent_fission": {"max_body_lines": 100, "max_skill_count": 6}})
    body_f = [f for f in findings if f.code == "AGENT_BODY_OVERSIZE"]
    assert len(body_f) == 1
    assert body_f[0].severity == "warn"


def test_body_oversize_error(tmp_path):
    _seed(tmp_path)
    _make_agent(tmp_path, "worker", body_lines=160)
    findings = check(tmp_path, {"agent_fission": {"max_body_lines": 100, "max_skill_count": 6}})
    body_f = next(f for f in findings if f.code == "AGENT_BODY_OVERSIZE")
    assert body_f.severity == "error"


def test_body_info_band(tmp_path):
    _seed(tmp_path)
    _make_agent(tmp_path, "worker", body_lines=85)
    findings = check(tmp_path, {"agent_fission": {"max_body_lines": 100, "max_skill_count": 6}})
    body_f = next(f for f in findings if f.code == "AGENT_BODY_OVERSIZE")
    assert body_f.severity == "info"


def test_skill_overload_from_table(tmp_path):
    _seed(tmp_path)
    table = (
        "\n## Skills\n\n"
        "| Skill | Purpose |\n"
        "|-------|---------|\n"
        "| a | x |\n| b | x |\n| c | x |\n| d | x |\n| e | x |\n| f | x |\n| g | x |\n"
    )
    _make_agent(tmp_path, "worker", body_lines=5, skills_section=table)
    findings = check(tmp_path, {"agent_fission": {"max_body_lines": 999, "max_skill_count": 6}})
    skill_f = [f for f in findings if f.code == "AGENT_SKILL_OVERLOAD"]
    assert len(skill_f) == 1
    assert skill_f[0].metadata["count"] == 7


def test_skill_parser_table_then_fallback():
    body = (
        "## Skills\n\n"
        "| a | b |\n"
        "|---|---|\n"
        "| 1 | 2 |\n"
        "| 3 | 4 |\n"
    )
    assert count_skills(body, "worker") == 2
    body2 = "blah\n`cbim skill show worker.alpha`\n`cbim skill show worker.beta`\n"
    assert count_skills(body2, "worker") == 2
