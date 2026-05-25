"""arch_exec/state_check.py — StateCheck leaf: classify knowledge/code sync state."""

from __future__ import annotations

import json
from typing import Any

from engine.core.llm_leaf import LlmActionLeaf

from ._helpers import extract_json, render_guide, render_header

_VALID_STATES = {"missing", "in_sync", "code_ahead", "knowledge_ahead"}


def _build_prompt(bb) -> str:
    scan = getattr(bb, "arch_scan_summary", None)
    scan_block = json.dumps(scan, ensure_ascii=False) if scan else "(无)"
    return (
        "## Architect 执行子循环 · StateCheck\n\n"
        f"{render_header(bb)}\n"
        "### Scan 结果\n"
        f"{scan_block}\n\n"
        "### 节点指引\n"
        f"{render_guide('state_check')}\n\n"
        "### 输出（仅 JSON）——必须从 "
        f"{sorted(_VALID_STATES)} 中选一个\n"
        "```json\n"
        '{"state": "missing|in_sync|code_ahead|knowledge_ahead", "reason": "一句话理由"}\n'
        "```\n"
    )


def _parse(text: str) -> str | None:
    data = extract_json(text)
    if not isinstance(data, dict):
        return None
    state = data.get("state")
    if not isinstance(state, str) or state not in _VALID_STATES:
        return None
    return state


def build(llm_client: Any) -> LlmActionLeaf:
    # Tiny structured reply — default cap is plenty, but retry guards
    # against the rare malformed-fence case so a transient blip doesn't
    # sink the whole architect-execution chain into FallbackPlan.
    return LlmActionLeaf(
        name="StateCheck",
        llm_client=llm_client,
        prompt_builder=_build_prompt,
        response_parser=_parse,
        output_field="arch_state",
        retries=2,
    )
