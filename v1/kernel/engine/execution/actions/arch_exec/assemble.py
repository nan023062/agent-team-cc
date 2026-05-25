"""arch_exec/assemble.py — Assemble leaf: finalize arch_plan."""

from __future__ import annotations

import json
from typing import Any

from engine.core.llm_leaf import LlmActionLeaf

from ._helpers import extract_json, render_guide, render_header

_VALID_CAPS = {"programmer", "tester", "doc_writer", "generalist"}


def _build_prompt(bb) -> str:
    draft = getattr(bb, "arch_plan_draft", None) or []
    draft_block = json.dumps(draft, ensure_ascii=False, indent=2)[:2000]
    return (
        "## Architect 执行子循环 · Assemble\n\n"
        f"{render_header(bb)}\n"
        "### 任务草稿（来自 Map）\n"
        f"{draft_block}\n\n"
        "### 节点指引\n"
        f"{render_guide('assemble')}\n\n"
        "### 输出（仅 JSON）——arch_plan 是 list[dict]，每条含"
        " id / description / required_capability / params / arch_context\n"
        "```json\n"
        '{"arch_plan": [{"id": "t1", "description": "...", "required_capability":'
        ' "programmer", "params": {}, "arch_context": "..."}]}\n'
        "```\n"
    )


def _parse(text: str) -> list | None:
    data = extract_json(text)
    if not isinstance(data, dict):
        return None
    plan = data.get("arch_plan")
    if not isinstance(plan, list):
        return None
    normalized: list[dict] = []
    for item in plan:
        if not isinstance(item, dict):
            return None
        # Required keys — fail-fast if structure is wrong.
        if not all(k in item for k in ("id", "description", "required_capability",
                                       "params", "arch_context")):
            return None
        cap = item.get("required_capability")
        if cap not in _VALID_CAPS:
            item = dict(item)
            item["required_capability"] = "generalist"
        normalized.append(item)
    return normalized


def build(llm_client: Any) -> LlmActionLeaf:
    # Assemble emits the final arch_plan — up to 8 tasks × ~150 tokens of
    # JSON each, plus framing — so the default 1024-token cap on the shared
    # AnthropicLLM truncates the reply mid-array, extract_json returns None,
    # the leaf FAILUREs, and the outer Selector falls through to
    # FallbackPlan (losing all ContextPack content). 4096 leaves headroom
    # for the maximum-size plan plus arch_context strings; retries=2 covers
    # the rare transient malformed-fence case without bloating cost.
    return LlmActionLeaf(
        name="Assemble",
        llm_client=llm_client,
        prompt_builder=_build_prompt,
        response_parser=_parse,
        output_field="arch_plan",
        max_tokens=4096,
        retries=2,
    )
