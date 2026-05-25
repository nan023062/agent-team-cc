"""loops/hr_governance.py — HR governance sub-loop descriptor.

Topology source: WORKFLOW-HR.zh-CN.md §2 (六类扫描 → 分类 → 安全|危险 → 报告).

The governance sub-loop now runs as an in-process Python BT subtree mounted
directly inside DreamRoot — no HR agent yield is involved. This module
retains:

  - `NODE_SPECS` — the design-doc-aligned flat node list, pinned by topology
    tests as the single source of truth for sub-loop shape;
  - `build_hr_governance_subtree(llm)` — thin re-export of the real subtree
    builder in `engine.dream.actions.hr_gov`.
"""
from __future__ import annotations

from engine.core.loop_spec import NodeSpec


NODE_SPECS: list[NodeSpec] = [
    NodeSpec("load",          "加载能力册与近期派工/评估痕迹", "action"),
    NodeSpec("scan_idle",     "扫闲置",                       "action"),
    NodeSpec("scan_failing",  "扫失能",                       "action"),
    NodeSpec("scan_gap",      "扫累计能力缺口",                "action"),
    NodeSpec("scan_drift",    "扫声明与表现漂移",              "action"),
    NodeSpec("scan_dup",      "扫能力重复",                   "action"),
    NodeSpec("scan_wide",     "扫职责过宽",                   "action"),
    NodeSpec("classify",      "按动作类别归类",                "decision"),
    NodeSpec("safe_do",       "立即执行（幂等）",              "action"),
    NodeSpec("risky_advise",  "只产建议/不执行",               "action"),
    NodeSpec("build",         "装配治理报告",                  "action"),
]


def build_hr_governance_subtree(llm):
    """Construct the Python-BT HR-governance subtree.

    Delegates to engine.dream.actions.hr_gov. Same re-export pattern as
    architect_governance.build_architect_governance_subtree.
    """
    from engine.dream.actions.hr_gov import build_hr_governance_subtree as _build
    return _build(llm)


__all__ = [
    "NODE_SPECS",
    "build_hr_governance_subtree",
]
