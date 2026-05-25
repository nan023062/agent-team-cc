"""loops/hr_governance.py — HR governance sub-loop descriptor.

Topology source: WORKFLOW-HR.zh-CN.md §2 (六类扫描 → 分类 → 安全|危险 → 报告).

Runs inside the HR agent during governance mode. Returns a governance
report dict the dream-root CollectHRAdvice action consumes.
"""
from __future__ import annotations

import json
from typing import Any

from ._spec import NodeSpec


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


def compose_prompt(bb) -> str:
    """Render the HR governance NodeSpec list into a prompt.

    Header marker `## 治理模式` matches the dream-loop dispatch convention.
    HR agent parses this marker to enter governance mode.
    """
    snapshot = getattr(bb, "agent_snapshot", None) or getattr(bb, "user_request", None) or ""

    lines = [
        "## 治理模式（HR 治理子循环）",
        "",
        "你接到治理派工。回头式重构，不响应任何当前用户任务。",
        "按六类扫描顺序推进，再做归类，最后产出治理报告。",
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
        '{"hr_governance_report": {"safe_done": [...], "pending_advice": [...], "blockers": [...]}}',
        "若无法完成，回 JSON `{\"error\": \"原因\"}`。",
    ]
    return "\n".join(lines)


def parse_response(payload: str | dict | None) -> dict:
    """Normalize HR's governance response into a dict with hr_governance_report."""
    if payload is None or (isinstance(payload, str) and not payload.strip()):
        return {"hr_governance_report": None, "error": "empty response"}

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (ValueError, TypeError):
            return {"hr_governance_report": {"raw": payload}}

    if isinstance(payload, dict):
        if "error" in payload and "hr_governance_report" not in payload:
            return {"hr_governance_report": None, "error": str(payload["error"])}
        if "hr_governance_report" in payload:
            return {"hr_governance_report": payload["hr_governance_report"]}
        return {"hr_governance_report": payload}

    if isinstance(payload, list):
        return {"hr_governance_report": {"items": payload}}

    return {"hr_governance_report": {"raw": repr(payload)}}


__all__ = ["NODE_SPECS", "compose_prompt", "parse_response"]
