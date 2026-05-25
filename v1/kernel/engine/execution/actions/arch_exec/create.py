"""arch_exec/create.py — Create leaf: draft a new module design."""

from __future__ import annotations

import json
from typing import Any

from engine.core.llm_leaf import LlmActionLeaf

from ._helpers import extract_json, render_guide, render_header


def _build_prompt(bb) -> str:
    scan = getattr(bb, "arch_scan_summary", None)
    scan_block = json.dumps(scan, ensure_ascii=False) if scan else "(无)"
    return (
        "## Architect 执行子循环 · Create\n\n"
        f"{render_header(bb)}\n"
        "### Scan 结果\n"
        f"{scan_block}\n\n"
        "### 节点指引\n"
        f"{render_guide('create')}\n\n"
        "### 输出（仅 JSON）——draft 字段说明新模块的边界 / 契约 / 依赖\n"
        "```json\n"
        '{"draft": {"module_path": "...", "boundary": "...", "contract": "...", "depends_on": []}}\n'
        "```\n"
    )


def _parse(text: str) -> Any | None:
    data = extract_json(text)
    if not isinstance(data, dict):
        return None
    draft = data.get("draft")
    if not isinstance(draft, dict):
        return None
    return draft


def build(llm_client: Any) -> LlmActionLeaf:
    # Module draft (boundary/contract/depends_on) can run a few hundred
    # tokens; 2048 covers it. retries=2 absorbs transient flakiness.
    return LlmActionLeaf(
        name="Create",
        llm_client=llm_client,
        prompt_builder=_build_prompt,
        response_parser=_parse,
        output_field="arch_draft",
        max_tokens=2048,
        retries=2,
    )
