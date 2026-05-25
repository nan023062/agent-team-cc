"""arch_exec/diff.py — Diff leaf: locate code/knowledge drift (state code_ahead)."""

from __future__ import annotations

import json
from typing import Any

from engine.core.llm_leaf import LlmActionLeaf

from ._helpers import extract_json, render_guide, render_header


def _build_prompt(bb) -> str:
    scan = getattr(bb, "arch_scan_summary", None)
    scan_block = json.dumps(scan, ensure_ascii=False) if scan else "(无)"
    return (
        "## Architect 执行子循环 · Diff\n\n"
        f"{render_header(bb)}\n"
        "### Scan 结果\n"
        f"{scan_block}\n\n"
        "### 节点指引\n"
        f"{render_guide('diff')}\n\n"
        "### 输出（仅 JSON）——列出变更点与待补齐的知识条目\n"
        "```json\n"
        '{"diffs": [{"module": "...", "change": "...", "doc_gap": "..."}]}\n'
        "```\n"
    )


def _parse(text: str) -> Any | None:
    data = extract_json(text)
    if not isinstance(data, dict):
        return None
    diffs = data.get("diffs")
    if not isinstance(diffs, list):
        return None
    return data


def build(llm_client: Any) -> LlmActionLeaf:
    # Diff list (module/change/doc_gap per drift point) can span several
    # entries. 2048 covers it; retries=2 absorbs transient flakiness.
    return LlmActionLeaf(
        name="Diff",
        llm_client=llm_client,
        prompt_builder=_build_prompt,
        response_parser=_parse,
        output_field="arch_diff_summary",
        max_tokens=2048,
        retries=2,
    )
