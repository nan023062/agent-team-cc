"""arch_exec/extract.py — Extract leaf: pull constraints from existing DNA."""

from __future__ import annotations

import json
from typing import Any

from engine.core.llm_leaf import LlmActionLeaf

from ._helpers import extract_json, render_guide, render_header


def _build_prompt(bb) -> str:
    scan = getattr(bb, "arch_scan_summary", None)
    scan_block = json.dumps(scan, ensure_ascii=False) if scan else "(无)"
    return (
        "## Architect 执行子循环 · Extract\n\n"
        f"{render_header(bb)}\n"
        "### Scan 结果\n"
        f"{scan_block}\n\n"
        "### 节点指引\n"
        f"{render_guide('extract')}\n\n"
        "### 输出（仅 JSON）——只挑与子任务直接相关的约束\n"
        "```json\n"
        '{"modules": [{"path": "...", "constraints": ["..."]}]}\n'
        "```\n"
    )


def _parse(text: str) -> Any | None:
    data = extract_json(text)
    if not isinstance(data, dict):
        return None
    mods = data.get("modules")
    if not isinstance(mods, list):
        return None
    return data


def build(llm_client: Any) -> LlmActionLeaf:
    return LlmActionLeaf(
        name="Extract",
        llm_client=llm_client,
        prompt_builder=_build_prompt,
        response_parser=_parse,
        output_field="arch_context_extracted",
    )
