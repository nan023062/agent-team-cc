"""loops/architect_governance.py — Architect governance sub-loop descriptor.

Topology source: WORKFLOW-ARCHITECT.zh-CN.md §3 (八项扫描 → 分类 → 报告).

Runs inside the architect agent during governance mode (prompt header
carries the governance marker). Returns a governance report dict that
the dream-root CollectArchAdvice action consumes.
"""
from __future__ import annotations

import json
from typing import Any

from ._spec import NodeSpec


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


def compose_prompt(bb) -> str:
    """Render the governance NodeSpec list into the architect prompt.

    The header marker `## 治理模式` matches the dream-loop dispatch convention
    (see CLAUDE.md "## 治理模式" hint in dream_tick contract). The architect
    parses this marker to enter governance mode.
    """
    snapshot = getattr(bb, "dna_snapshot", None) or getattr(bb, "user_request", None) or ""

    lines = [
        "## 治理模式（Architect 治理子循环）",
        "",
        "你接到治理派工。回头式重构，不响应任何当前用户任务。",
        "按以下八项扫描顺序推进，再做归类，最后产出治理报告。",
        "",
    ]
    if snapshot:
        lines += ["### 输入上下文", str(snapshot)[:2000], ""]

    lines += ["### 流程节点（按序）"]
    for i, spec in enumerate(NODE_SPECS, start=1):
        marker = {"action": "·", "decision": "?", "terminal": "■"}[spec.role]
        lines.append(f"{i:>2}. [{marker}] {spec.label}")

    lines += [
        "",
        "### 回执格式",
        '{"arch_governance_report": {"safe_done": [...], "pending_advice": [...], "blockers": [...]}}',
        "若无法完成，回 JSON `{\"error\": \"原因\"}`。",
    ]
    return "\n".join(lines)


def parse_response(payload: str | dict | None) -> dict:
    """Normalize architect's governance response into a dict.

    Result shape:
      {"arch_governance_report": {...}, optional "error": "..."}
    """
    if payload is None or (isinstance(payload, str) and not payload.strip()):
        return {"arch_governance_report": None, "error": "empty response"}

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (ValueError, TypeError):
            return {"arch_governance_report": {"raw": payload}}

    if isinstance(payload, dict):
        if "error" in payload and "arch_governance_report" not in payload:
            return {"arch_governance_report": None, "error": str(payload["error"])}
        if "arch_governance_report" in payload:
            return {"arch_governance_report": payload["arch_governance_report"]}
        # Tolerate dict-only payload — wrap.
        return {"arch_governance_report": payload}

    if isinstance(payload, list):
        return {"arch_governance_report": {"items": payload}}

    return {"arch_governance_report": {"raw": repr(payload)}}


__all__ = ["NODE_SPECS", "compose_prompt", "parse_response"]
