"""arch_gov — Architect governance subtree (Python BT, in-process).

Replaces the legacy "dispatch architect once, parse a big JSON" pattern with
a real BT subtree where each scan / decision is its own leaf. Control flow
is encoded in the Sequence topology and statically auditable.

Subtree contract:
  build_architect_governance_subtree(llm) -> Node
    Returns a Sequence rooted at "ArchGovernanceSubtree". Run it on a
    DreamBlackboard inside the dream root (t6 will wire it in; not yet
    mounted in dream/tree/dream_loop.py).

Side-effects (single-writer ownership per node):
  LoadAll        → state["inventory"]
  Scan*          → state["findings"][<scan_id>]
  Classify       → state["buckets"] = {"safe": [...], "risky": [...]}
  SafeApply      → state["safe_actions_applied"]
  RiskyAdvise    → state["advice_pending"]
  Report         → bb.arch_governance_report = {safe_actions_applied, advice_pending}

`state` is a plain dict held by reference by every leaf in the subtree —
not a bb field (DreamBlackboard __slots__ forbids ad-hoc attrs). Whole
subtree runs in one tick (no yields), so per-tick scratch lives on the
shared dict; nothing leaks to the next tick.
"""
from __future__ import annotations

from engine.core.composite import Sequence
from engine.core.node import Node

from .load_all import LoadAll
from .scans import (
    ScanCycle,
    ScanDrift,
    ScanMerge,
    ScanOrphan,
    ScanPromote,
    ScanRestructure,
    ScanSplit,
    ScanStale,
)
from .classify import Classify
from .safe_apply import SafeApply
from .risky_advise import RiskyAdvise
from .report import Report


def build_architect_governance_subtree(llm) -> Node:
    """Construct the 13-node architect-governance Sequence.

    `llm` is the in-process LLM client that LlmActionLeaf-based scans use.
    Passed through to every Scan* leaf at construction time so no leaf
    needs to look it up from bb. Deterministic leaves (Load/Classify/
    Safe/Risky/Report) ignore it.
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
            ScanOrphan(llm=llm, state=state, name="ScanOrphan"),
            ScanStale(llm=llm, state=state, name="ScanStale"),
            ScanCycle(llm=llm, state=state, name="ScanCycle"),
            ScanDrift(llm=llm, state=state, name="ScanDrift"),
            ScanPromote(llm=llm, state=state, name="ScanPromote"),
            ScanSplit(llm=llm, state=state, name="ScanSplit"),
            ScanMerge(llm=llm, state=state, name="ScanMerge"),
            ScanRestructure(llm=llm, state=state, name="ScanRestructure"),
        ],
        name="ArchGovScans",
    )

    return Sequence(
        [
            LoadAll(state=state, name="LoadAll"),
            scans,
            Classify(state=state, name="Classify"),
            SafeApply(state=state, name="SafeApply"),
            RiskyAdvise(state=state, name="RiskyAdvise"),
            Report(state=state, name="Report"),
        ],
        name="ArchGovernanceSubtree",
    )


__all__ = ["build_architect_governance_subtree"]
