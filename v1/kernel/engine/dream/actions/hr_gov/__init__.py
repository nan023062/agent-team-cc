"""hr_gov — HR governance subtree (Python BT, in-process).

Replaces the legacy "dispatch HR once, parse a big JSON" pattern with a
real BT subtree. Same shape as arch_gov: deterministic Load → six scans
(LLM-driven) → deterministic Classify / SafeDo / RiskyAdvise / Build.

Side-effects (single-writer per node):
  Load        → state["inventory"]
  Scan*       → state["findings"][<scan_id>]
  Classify    → state["buckets"] = {"safe", "risky"}
  SafeDo      → state["safe_actions_applied"]
  RiskyAdvise → state["advice_pending"]
  Build       → bb.hr_governance_report = {safe_actions_applied, advice_pending}

`state` is a shared dict held by reference; whole subtree runs in one tick.
"""
from __future__ import annotations

from engine.core.composite import Sequence
from engine.core.node import Node

from .load import Load
from .scans import (
    ScanBroken,
    ScanDrift,
    ScanDuplicate,
    ScanGap,
    ScanIdle,
    ScanWide,
)
from .classify import Classify
from .safe_do import SafeDo
from .risky_advise import RiskyAdvise
from .build import Build


def build_hr_governance_subtree(llm) -> Node:
    """Construct the 11-node HR-governance Sequence.

    `llm` is the in-process LLM client used by the six Scan* leaves.
    Deterministic leaves (Load/Classify/SafeDo/RiskyAdvise/Build) ignore it.
    """
    state: dict = {
        "inventory": None,
        "findings": {},
        "buckets": {"safe": [], "risky": []},
        "safe_actions_applied": [],
        "advice_pending": [],
    }

    scans = Sequence(
        [
            ScanIdle(llm=llm, state=state, name="ScanIdle"),
            ScanBroken(llm=llm, state=state, name="ScanBroken"),
            ScanGap(llm=llm, state=state, name="ScanGap"),
            ScanDrift(llm=llm, state=state, name="ScanDrift"),
            ScanDuplicate(llm=llm, state=state, name="ScanDuplicate"),
            ScanWide(llm=llm, state=state, name="ScanWide"),
        ],
        name="HRGovScans",
    )

    return Sequence(
        [
            Load(state=state, name="Load"),
            scans,
            Classify(state=state, name="Classify"),
            SafeDo(state=state, name="SafeDo"),
            RiskyAdvise(state=state, name="RiskyAdvise"),
            Build(state=state, name="Build"),
        ],
        name="HRGovernanceSubtree",
    )


__all__ = ["build_hr_governance_subtree"]
