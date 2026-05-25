"""arch_exec/map_tasks.py — Map leaf: turn analysis into a task-list draft."""

from __future__ import annotations

import json
from typing import Any

from engine.core.llm_leaf import LlmActionLeaf

from ._helpers import extract_json, render_guide, render_header


def _gather_upstream(bb) -> dict[str, Any]:
    """Collect whichever per-state outputs were produced upstream."""
    out: dict[str, Any] = {}
    for field in (
        "arch_scan_summary",
        "arch_state",
        "arch_worth",
        "arch_draft",
        "arch_context_extracted",
        "arch_diff_summary",
        "arch_validation_result",
    ):
        val = getattr(bb, field, None)
        if val is not None:
            out[field] = val
    return out


def _build_prompt(bb) -> str:
    upstream = json.dumps(_gather_upstream(bb), ensure_ascii=False, indent=2)[:2000]
    return (
        "## Architect 执行子循环 · Map\n\n"
        f"{render_header(bb)}\n"
        "### 上游分析结果\n"
        f"{upstream}\n\n"
        "### 节点指引\n"
        f"{render_guide('map')}\n\n"
        "### 输出（仅 JSON）——plan_draft 是 list；总数 ≤ 8\n"
        "```json\n"
        '{"plan_draft": [{"id": "t1", "description": "...", "required_capability": "...",'
        ' "params": {}, "arch_context": "..."}]}\n'
        "```\n"
    )


def _parse(text: str) -> list | None:
    data = extract_json(text)
    if not isinstance(data, dict):
        return None
    draft = data.get("plan_draft")
    if not isinstance(draft, list):
        return None
    return draft


def build(llm_client: Any) -> LlmActionLeaf:
    return LlmActionLeaf(
        name="Map",
        llm_client=llm_client,
        prompt_builder=_build_prompt,
        response_parser=_parse,
        output_field="arch_plan_draft",
    )
