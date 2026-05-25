"""arch_exec/worth.py — Worth leaf: decide whether to lazily create knowledge."""

from __future__ import annotations

import json
from typing import Any

from engine.core.llm_leaf import LlmActionLeaf

from ._helpers import extract_json, render_guide, render_header


def _build_prompt(bb) -> str:
    scan = getattr(bb, "arch_scan_summary", None)
    scan_block = json.dumps(scan, ensure_ascii=False) if scan else "(无)"
    return (
        "## Architect 执行子循环 · Worth\n\n"
        f"{render_header(bb)}\n"
        "### Scan 结果\n"
        f"{scan_block}\n\n"
        "### 节点指引\n"
        f"{render_guide('worth')}\n\n"
        "### 输出（仅 JSON）\n"
        "```json\n"
        '{"worth": true, "reason": "一句话理由"}\n'
        "```\n"
    )


def _parse(text: str) -> bool | None:
    data = extract_json(text)
    if not isinstance(data, dict):
        return None
    worth = data.get("worth")
    if isinstance(worth, bool):
        return worth
    return None


def build(llm_client: Any) -> LlmActionLeaf:
    # Boolean + one-sentence reason — tiny reply, default cap is fine; the
    # retry is a cheap guard against malformed-fence outliers.
    return LlmActionLeaf(
        name="Worth",
        llm_client=llm_client,
        prompt_builder=_build_prompt,
        response_parser=_parse,
        output_field="arch_worth",
        retries=2,
    )
