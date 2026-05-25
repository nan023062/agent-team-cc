"""loops/architect_governance.py — Architect governance sub-loop descriptor.

Topology source: WORKFLOW-ARCHITECT.zh-CN.md §3 (八项扫描 → 分类 → 报告).

Runs inside the architect agent during governance mode (prompt header
carries the governance marker). Returns a governance report dict that
the dream-root CollectArchAdvice action consumes.
"""
from __future__ import annotations

import json
from typing import Any

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


def compose_prompt(bb) -> str:
    """Render the governance NodeSpec list into the architect prompt.

    The header marker `## 治理模式` matches the dream-loop dispatch convention
    (see CLAUDE.md "## 治理模式" hint in dream_tick contract). The architect
    parses this marker to enter governance mode (see
    `.claude/agents/architect/architect.md` 治理模式章节).

    Output schema is aligned with
    `engine.dream.actions.collect_advice._parse_advice_report`:
    `safe_actions_applied` / `advice_pending` are the two recognized keys.
    """
    snapshot = getattr(bb, "dna_snapshot", None) or getattr(bb, "user_request", None) or ""

    # Per-spec hint, keyed by NodeSpec.id. Each line explains *what to do*
    # inside that node and which bucket (safe / risky) findings fall into.
    # NODE_SPECS itself remains the source of truth for labels & order;
    # we only attach an annotation here.
    hints: dict[str, str] = {
        "load_all": (
            "读 .dna/ 全量模块索引 + 最近一轮 medium-tier 记忆（架构决策痕迹）。"
            "建立本轮扫描的模块清单与历史决策上下文，不做任何修改。"
        ),
        "scan_orphan": (
            "有 .dna/module.md 但目录已不存在的幽灵模块 → safe（dna_reindex 可清掉）。"
        ),
        "scan_stale": (
            "status=implemented 但近期无提交、或 contract.md 超过 30 天未更新 → "
            "risky（可能需降级为 spec，请人工裁决）。"
        ),
        "scan_cycle": (
            "dependencies 列表里出现反向依赖（子→父）或平级循环 → risky（影响存亡，进 advice_pending）。"
        ),
        "scan_drift": (
            "已发布契约（contract.md）与当前代码行为出现明显背离 → risky（修契约 = 改公开接口）。"
        ),
        "scan_promote": (
            "近期 memory 里出现可固化为知识的反复决策 → risky（提升 = 写知识，需人工确认主张）。"
        ),
        "scan_split": (
            "单一模块 body 描述了明显属于另一职责域的内容 → risky（裂变改边界，需人工裁决）。"
        ),
        "scan_merge": (
            "两个模块职责高度重叠、接口几乎重合 → risky（合并删模块，需人工裁决）。"
        ),
        "scan_restructure": (
            "整片依赖图层级不清、需要重组分层 → risky（结构性改动，进 advice_pending）。"
        ),
        "classify": (
            "把所有发现分入两桶：safe（幂等、可逆、不改公开契约接口、不影响模块存亡）/ "
            "risky（改契约、改存亡、改边界，任何 '建议人工判断' 的）。"
        ),
        "safe_apply": (
            "对 safe 桶里的发现立即调用 MCP 工具落地："
            "frontmatter 缺字段 → dna_edit 补；幽灵模块 → dna_reindex；"
            "kebab-case 违规 → dna_edit 改名。每条记入 safe_actions_applied。"
        ),
        "risky_advise": (
            "对 risky 桶里的发现只写一句建议，不动 .dna/。每条记入 advice_pending，"
            "用户 / HR / 后续会话再裁决。"
        ),
        "report": (
            "按下方 JSON schema 装配回执。两个数组都为空也要返回，不要省略字段。"
        ),
    }

    lines = [
        "## 治理模式（Architect 治理子循环）",
        "",
        "你接到治理派工。这是回头式重构 —— 扫已落成的 .dna/ 与代码，",
        "找问题、分类、落 safe 的、提 risky 的。不响应任何当前用户任务。",
        "完整角色规则见 `.claude/agents/architect/architect.md` 治理模式章节。",
        "",
        "### safe vs risky 分类标准",
        "- **safe（直接执行）**：幂等、可逆、不改公开契约接口、不影响模块存亡。",
        "  例：补 frontmatter 字段、dna_reindex、内部名称 kebab-case 改名。",
        "- **risky（进 advice_pending）**：修改契约接口、标记模块废弃 / 降级、",
        "  合并 / 拆分模块、任何 '建议人工判断' 的事项。",
        "",
    ]
    if snapshot:
        lines += ["### 输入上下文", str(snapshot)[:2000], ""]

    lines += ["### 流程节点（按序，冒号后为每节点的执行说明）"]
    for i, spec in enumerate(NODE_SPECS, start=1):
        marker = {"action": "·", "decision": "?", "terminal": "■"}[spec.role]
        hint = hints.get(spec.id, "")
        if hint:
            lines.append(f"{i:>2}. [{marker}] {spec.label} —— {hint}")
        else:
            lines.append(f"{i:>2}. [{marker}] {spec.label}")

    lines += [
        "",
        "### 回执 schema（严格遵守，键名不可改）",
        "```json",
        "{",
        '  "arch_governance_report": {',
        '    "safe_actions_applied": ["简述每条已落动作，例：dna_edit src/foo 补 owner 字段"],',
        '    "advice_pending":       ["简述每条待裁决建议，例：src/bar 与 src/baz 接口重叠，建议合并"]',
        "  }",
        "}",
        "```",
        "两个数组都允许为空，但字段必须存在。",
        "若整轮无法完成（环境异常 / 工具失败），回 JSON `{\"error\": \"原因\"}`。",
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
