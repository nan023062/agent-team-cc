"""loops/hr_governance.py — HR governance sub-loop descriptor.

Topology source: WORKFLOW-HR.zh-CN.md §2 (六类扫描 → 分类 → 安全|危险 → 报告).

Runs inside the HR agent during governance mode. Returns a governance
report dict the dream-root CollectHRAdvice action consumes.

This module owns:
  - ``NODE_SPECS`` — design-doc-aligned flat node list, pinned by topology
    tests as the single source of truth for sub-loop shape;
  - ``compose_prompt(bb)`` — renders the NodeSpec list + per-scan judging
    criteria into HR's governance prompt;
  - ``parse_response(payload)`` — normalizes HR's reply into
    ``{"hr_governance_report": {...}}`` for CollectHRAdvice.
"""
from __future__ import annotations

import json
from typing import Any

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


def compose_prompt(bb) -> str:
    """Render the HR governance NodeSpec list into a prompt.

    Header marker ``## 治理模式`` matches the dream-loop dispatch
    convention. HR agent parses this marker to enter governance mode.

    Output schema is aligned with ``parse_response`` and consumed by
    ``CollectHRAdvice.on_resume`` —— ``safe_actions_applied`` /
    ``advice_pending`` are the two recognized keys, mirroring the
    architect-governance schema for unified parsing.
    """
    snapshot = getattr(bb, "agent_snapshot", None) or ""

    lines = [
        "## 治理模式（HR 治理子循环）",
        "",
        "你接到治理派工。回头式重构能力册，不响应任何当前用户任务。",
        "唯一真源：design/WORKFLOW-HR.zh-CN.md §2、.claude/agents/hr/hr.md 治理章节。",
        "",
        "执行节奏：先 load，再按下方六类扫描产出候选动作清单，",
        "然后归类为 safe / risky，safe 立即落地、risky 只入 advice_pending，最后装配回执。",
        "",
    ]
    if snapshot:
        lines += ["### 输入上下文", str(snapshot)[:2000], ""]

    lines += [
        "### 流程节点（按序，钉死不可重排）",
    ]
    for i, spec in enumerate(NODE_SPECS, start=1):
        marker = {"action": "·", "decision": "?", "terminal": "■"}[spec.role]
        lines.append(f"{i:>2}. [{marker}] {spec.label}")

    lines += [
        "",
        "### 六类扫描的最小判据",
        "",
        "**扫闲置** — agent 最近 14 天无任何 task 派工记录，且当前无 active session；",
        "  判据满足即列为闲置候选（动作建议：归档；归档属 risky）。",
        "",
        "**扫失能** — agent 文件 frontmatter 缺必填字段（name / description / tools）",
        "  或文件本体无法被 agent loader 解析；判据满足即列为损坏候选",
        "  （动作建议：缺字段可补 = safe；结构性损坏 = risky）。",
        "",
        "**扫累计能力缺口** — 在近期 bt_tick / hr_execution 日志中连续出现",
        "  `agent_gap: <capability>` ≥ 3 次，且当前能力册中无任何 agent 覆盖该 capability；",
        "  判据满足即列为缺口候选（动作建议：招募新 agent = risky）。",
        "",
        "**扫声明与表现漂移** — agent 定义中的 Positioning / Stance 与其实际承接的",
        "  task 类型严重不符（如声明为后端实现 agent，过去 N 次实际承接均为文档任务）；",
        "  判据满足即列为漂移候选（动作建议：改写定义 = risky）。",
        "",
        "**扫能力重复** — 两个 agent 的 description 关键词重叠 > 70%，",
        "  或近期承接 task 类型高度相同；判据满足即列为重复候选",
        "  （动作建议：合并 = risky）。",
        "",
        "**扫职责过宽** — 单个 agent 连续承接 ≥ 3 类不同 capability 的任务，",
        "  无法用单一定位概括；判据满足即列为过宽候选（动作建议：裂变 = risky）。",
        "",
        "### safe / risky 分类",
        "",
        "**safe（立即执行，幂等）**：",
        "  - 补 frontmatter 缺失字段",
        "  - 更新 agent 的 last_seen / last_active 元数据",
        "  - 写治理日志、登记缺口记录",
        "",
        "**risky（只产建议，进 advice_pending，不执行）**：",
        "  - 招募新 agent",
        "  - 归档 / 删除 agent",
        "  - 合并两个 agent",
        "  - 裂变一个 agent 为多个",
        "  - 改写 agent 的 Positioning / Stance",
        "",
        "### 回执格式（严格 JSON，键名钉死）",
        "",
        "```json",
        "{",
        '  "hr_governance_report": {',
        '    "safe_actions_applied": [',
        '      "<已执行的安全操作描述，每条一句话>"',
        "    ],",
        '    "advice_pending": [',
        '      "<需用户确认的高影响建议，每条一句话>"',
        "    ]",
        "  }",
        "}",
        "```",
        "",
        "两个数组均必填；无内容则给空数组 `[]`，不要省略键。",
        "若整体无法完成，回 JSON `{\"error\": \"原因\"}`。",
    ]
    return "\n".join(lines)


def parse_response(payload: str | dict | None) -> dict:
    """Normalize HR's governance response into ``{"hr_governance_report": ...}``.

    Same shape rules as architect_governance.parse_response.
    """
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


__all__ = [
    "NODE_SPECS",
    "compose_prompt",
    "parse_response",
]
