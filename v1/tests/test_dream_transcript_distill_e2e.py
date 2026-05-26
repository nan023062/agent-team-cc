"""E2E for the v2 transcript-driven memory governance step.

Exercises the three-yield trajectory:
  1. tick → DistillGate sees transcripts → DispatchMemDistill yields
     to the main agent (agent_type="main",
     subtask_id="governance_memory_distill").
  2. resume with the skill's report → TranscriptDelete unlinks the
     distilled paths → ArchitectGovernanceStep's first leaf yields.
  3. resume the architect report → HRGovernanceStep yields.
  4. resume the HR report → done.

Plus a regression: when the report carries no `distilled_paths`
(skill skipped everything), nothing on disk is touched.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from engine.dream.api import dream_tick as api


def _aged_transcript(parent: Path, name: str, age_seconds: float) -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    p = parent / name
    p.write_text('{"role": "user"}\n', encoding="utf-8")
    past = time.time() - age_seconds
    os.utime(p, (past, past))
    return p


@pytest.fixture
def isolated_dirs(tmp_path: Path, monkeypatch):
    scheduler_root = tmp_path / "scheduler"
    memory_root = tmp_path / "memory"
    transcripts_root = tmp_path / "transcripts"
    (memory_root / "medium").mkdir(parents=True)
    scheduler_root.mkdir(parents=True)
    transcripts_root.mkdir(parents=True)
    monkeypatch.setattr(api, "_scheduler_root", lambda: scheduler_root)
    monkeypatch.setattr(api, "_memory_store_dir", lambda: memory_root)
    monkeypatch.setattr(api, "_transcripts_dir", lambda: transcripts_root)
    return scheduler_root, memory_root, transcripts_root


def _arch_payload() -> str:
    return json.dumps({
        "arch_governance_report": {
            "safe_actions_applied": [],
            "advice_pending": [],
        }
    })


def _hr_payload() -> str:
    return json.dumps({
        "hr_governance_report": {
            "safe_actions_applied": [],
            "advice_pending": [],
        }
    })


def test_mature_transcripts_trigger_main_distill_yield_then_arch_then_hr(
    isolated_dirs,
):
    scheduler_root, memory_root, transcripts_root = isolated_dirs
    # Seed two mature transcripts.
    t1 = _aged_transcript(transcripts_root, "old.jsonl", 3 * 86400)
    t2 = _aged_transcript(transcripts_root, "older.jsonl", 5 * 86400)

    res = api.dream_tick("manual")
    assert res.kind == "yield", res.to_dict()
    dr = res.dispatch_request
    assert dr.agent_type == "main"
    assert dr.subtask_id == "governance_memory_distill"
    assert dr.agent_file is None
    assert dr.prompt.lstrip().startswith("## 治理模式")
    # The prompt embeds the path list (JSON-encoded). Compare against the
    # JSON-quoted form so Windows backslashes match against their escaped
    # counterparts on disk.
    for p in (t1, t2):
        assert json.dumps(str(p), ensure_ascii=False) in dr.prompt

    # The skill claims to have distilled both, and wrote one medium file.
    medium_path = memory_root / "medium" / "decision-test.md"
    medium_path.write_text("# decision-test\n", encoding="utf-8")
    distill_report = json.dumps({
        "distilled_paths": [str(t1), str(t2)],
        "medium_entries_written": [str(medium_path)],
        "skipped_paths": [],
        "errors": [],
    })
    res2 = api.dream_tick_resume(res.run_id, distill_report)
    assert res2.kind == "yield", res2.to_dict()
    assert res2.dispatch_request.agent_type == "architect"
    assert res2.dispatch_request.subtask_id == "governance_knowledge"

    # TranscriptDelete must have unlinked both files between yields.
    assert not t1.exists()
    assert not t2.exists()

    res3 = api.dream_tick_resume(res2.run_id, _arch_payload())
    assert res3.kind == "yield"
    assert res3.dispatch_request.agent_type == "hr"

    res4 = api.dream_tick_resume(res3.run_id, _hr_payload())
    assert res4.kind == "done", res4.to_dict()


def test_skill_skips_all_paths_then_no_files_are_deleted(isolated_dirs):
    _, memory_root, transcripts_root = isolated_dirs
    t1 = _aged_transcript(transcripts_root, "a.jsonl", 3 * 86400)

    res = api.dream_tick("manual")
    assert res.kind == "yield"
    assert res.dispatch_request.agent_type == "main"

    # Skill reports nothing distilled (e.g. all transcripts were too noisy).
    distill_report = json.dumps({
        "distilled_paths": [],
        "medium_entries_written": [],
        "skipped_paths": [{"path": str(t1), "reason": "no-signal"}],
        "errors": [],
    })
    res2 = api.dream_tick_resume(res.run_id, distill_report)
    assert res2.kind == "yield"
    assert res2.dispatch_request.agent_type == "architect"
    # The transcript MUST still exist — TranscriptDelete must respect
    # the empty distilled_paths list.
    assert t1.exists()
