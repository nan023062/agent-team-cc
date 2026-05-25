"""Unit tests for arch_gov.SafeApply — verifies the wired dna_reindex path.

Patches `cbi._primitives.modules.update_index` so we don't actually scan
the test repo. Confirms:
  - empty safe bucket is a no-op
  - N orphan findings → exactly one update_index call, N applied entries
  - update_index exception → all orphans degrade to advice_pending,
    leaf still returns SUCCESS
"""
from __future__ import annotations

from unittest.mock import patch

from engine.core.node import Status
from engine.dream.actions.arch_gov.safe_apply import SafeApply


def _make_orphan(subject: str, detail: str = "ghost module") -> dict:
    return {
        "kind": "scan_orphan",
        "subject": subject,
        "detail": detail,
        "bucket_hint": "safe",
    }


def test_safe_apply_empty_bucket_is_noop():
    state: dict = {"buckets": {"safe": []}}
    node = SafeApply(state=state)

    with patch("cbi._primitives.modules.update_index") as mock_idx:
        assert node.tick(bb=None) is Status.SUCCESS

    mock_idx.assert_not_called()
    assert state["safe_actions_applied"] == []
    assert state.get("advice_pending", []) == []


def test_safe_apply_two_orphans_one_reindex_call():
    state: dict = {
        "buckets": {
            "safe": [
                _make_orphan("src/ghost_a", "dna_present=true dir_present=false"),
                _make_orphan("src/ghost_b", "dna_present=true dir_present=false"),
            ]
        }
    }
    node = SafeApply(state=state)

    with patch("cbi._primitives.modules.update_index") as mock_idx:
        assert node.tick(bb=None) is Status.SUCCESS

    assert mock_idx.call_count == 1
    applied = state["safe_actions_applied"]
    assert len(applied) == 2
    assert any("src/ghost_a" in line for line in applied)
    assert any("src/ghost_b" in line for line in applied)
    assert state.get("advice_pending", []) == []


def test_safe_apply_reindex_failure_degrades_to_advice():
    state: dict = {
        "buckets": {
            "safe": [
                _make_orphan("src/ghost_a"),
                _make_orphan("src/ghost_b"),
            ]
        }
    }
    node = SafeApply(state=state)

    with patch(
        "cbi._primitives.modules.update_index",
        side_effect=RuntimeError("registry locked"),
    ):
        assert node.tick(bb=None) is Status.SUCCESS

    assert state["safe_actions_applied"] == []
    advice = state["advice_pending"]
    assert len(advice) == 2
    for line in advice:
        assert "reindex" in line
        assert "RuntimeError" in line
        assert "registry locked" in line
