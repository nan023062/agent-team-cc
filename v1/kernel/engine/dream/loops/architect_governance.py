"""loops/architect_governance.py — Architect governance sub-loop descriptor.

Topology source: WORKFLOW-ARCHITECT.zh-CN.md §3 (八项扫描 → 分类 → 报告).

The governance sub-loop now runs as an in-process Python BT subtree mounted
directly inside DreamRoot — no Architect agent yield is involved. This
module retains:

  - `NODE_SPECS` — the design-doc-aligned flat node list, pinned by topology
    tests as the single source of truth for sub-loop shape;
  - `build_architect_governance_subtree(llm)` — thin re-export of the real
    subtree builder in `engine.dream.actions.arch_gov`.
"""
from __future__ import annotations

from engine.core.loop_spec import NodeSpec


NODE_SPECS: list[NodeSpec] = [
    NodeSpec("load_all",         "加载全量模块索引/读近期执行日志与中期记忆候选", "action"),
    NodeSpec("scan_orphan",      "扫孤立模块",          "action"),
    NodeSpec("scan_stale",       "扫过期模块",          "action"),
    NodeSpec("scan_cycle",       "扫依赖冲突",          "action"),
    NodeSpec("scan_drift",       "扫已发约束与代码背离", "action"),
    NodeSpec("scan_promote",     "扫记忆提升候选",      "action"),
    NodeSpec("scan_split",       "扫模块裂变需求",      "action"),
    NodeSpec("scan_merge",       "扫模块合并冗余",      "action"),
    NodeSpec("scan_restructure", "扫依赖重组需求",      "action"),
    NodeSpec("classify",         "按动作类别归类",      "decision"),
    NodeSpec("safe_apply",       "立即执行/计入已落动作", "action"),
    NodeSpec("risky_advise",     "只产建议/计入待裁决建议", "action"),
    NodeSpec("report",           "装配治理报告",        "action"),
]


def build_architect_governance_subtree(llm):
    """Construct the Python-BT architect-governance subtree.

    Delegates to engine.dream.actions.arch_gov. Kept here as a thin
    re-export so callers that already import this descriptor module
    (e.g. dream/tree/dream_loop.py) can get the subtree builder without
    a second import path.
    """
    from engine.dream.actions.arch_gov import build_architect_governance_subtree as _build
    return _build(llm)


__all__ = [
    "NODE_SPECS",
    "build_architect_governance_subtree",
]
