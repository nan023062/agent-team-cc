"""Unit tests for hr_gov.SafeDo — verifies the wired agent_edit path.

Patches `services.agent_service.update_agent` so we don't actually
mutate any agent files. Confirms:
  - empty safe bucket is a no-op
  - scan_broken finding with field+value → one update_agent call
  - scan_broken finding without field/value → advisory, no service call
  - update_agent exception → finding lands in advice_pending,
    leaf still returns SUCCESS
"""
from __future__ import annotations

from unittest.mock import patch

from engine.core.node import Status
from engine.dream.actions.hr_gov.safe_do import SafeDo


def _make_broken(
    subject: str = "translator",
    detail: str = "frontmatter 缺字段: description",
    *,
    field: str | None = None,
    value: object = None,
) -> dict:
    item: dict = {
        "kind": "scan_broken",
        "subject": subject,
        "detail": detail,
        "bucket_hint": "safe",
    }
    if field is not None:
        item["field"] = field
    if value is not None:
        item["value"] = value
    return item


def test_safe_do_empty_bucket_is_noop():
    state: dict = {"buckets": {"safe": []}}
    node = SafeDo(state=state)

    with patch("services.agent_service.update_agent") as mock_upd:
        assert node.tick(bb=None) is Status.SUCCESS

    mock_upd.assert_not_called()
    assert state["safe_actions_applied"] == []
    assert state.get("advice_pending", []) == []


def test_safe_do_scan_broken_with_field_value_invokes_update_agent():
    finding = _make_broken(
        subject="translator",
        field="description",
        value="translates between languages",
    )
    state: dict = {"buckets": {"safe": [finding]}}
    node = SafeDo(state=state)

    with patch("services.agent_service.update_agent") as mock_upd:
        mock_upd.return_value = "/abs/path/to/translator.md"
        assert node.tick(bb=None) is Status.SUCCESS

    assert mock_upd.call_count == 1
    kwargs = mock_upd.call_args.kwargs
    assert kwargs["name"] == "translator"
    assert kwargs["target"] == "frontmatter"
    assert kwargs["payload"] == {
        "field": "description",
        "value": "translates between languages",
    }
    applied = state["safe_actions_applied"]
    assert len(applied) == 1
    assert "translator" in applied[0]
    assert "description" in applied[0]
    assert state.get("advice_pending", []) == []


def test_safe_do_scan_broken_without_field_value_falls_back_to_advice():
    finding = _make_broken(subject="translator")  # no field/value
    state: dict = {"buckets": {"safe": [finding]}}
    node = SafeDo(state=state)

    with patch("services.agent_service.update_agent") as mock_upd:
        assert node.tick(bb=None) is Status.SUCCESS

    mock_upd.assert_not_called()
    assert state["safe_actions_applied"] == []
    advice = state["advice_pending"]
    assert len(advice) == 1
    assert "translator" in advice[0]


def test_safe_do_update_agent_failure_degrades_to_advice():
    finding = _make_broken(
        subject="translator",
        field="description",
        value="x",
    )
    state: dict = {"buckets": {"safe": [finding]}}
    node = SafeDo(state=state)

    with patch(
        "services.agent_service.update_agent",
        side_effect=FileNotFoundError("agent not found"),
    ):
        assert node.tick(bb=None) is Status.SUCCESS

    assert state["safe_actions_applied"] == []
    advice = state["advice_pending"]
    assert len(advice) == 1
    assert "translator" in advice[0]
    assert "FileNotFoundError" in advice[0]
    assert "agent not found" in advice[0]
