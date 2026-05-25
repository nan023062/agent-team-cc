"""arch_exec/scan.py — Scan leaf: summarize intent + relevant modules."""

from __future__ import annotations

from typing import Any

from engine.core.llm_leaf import LlmActionLeaf

from ._helpers import extract_json, render_guide, render_header


def _build_prompt(bb) -> str:
    return (
        "## Architect 执行子循环 · Scan\n\n"
        f"{render_header(bb)}\n"
        "### 节点指引\n"
        f"{render_guide('scan')}\n\n"
        "### 输出（仅 JSON）\n"
        "```json\n"
        '{"intent": "一句话用户意图", "modules": ["可能受影响的模块路径"], "notes": "可选补充"}\n'
        "```\n"
    )


def _parse(text: str) -> Any | None:
    data = extract_json(text)
    if not isinstance(data, dict):
        return None
    intent = data.get("intent")
    if not isinstance(intent, str) or not intent.strip():
        return None
    return data


def build(llm_client: Any) -> LlmActionLeaf:
    # Scan emits intent + modules list + notes — usually small but the
    # modules list can balloon when the user_request touches many files.
    # 2048 covers the realistic upper bound; retries=2 absorbs transient
    # JSON-fence flakiness.
    return LlmActionLeaf(
        name="Scan",
        llm_client=llm_client,
        prompt_builder=_build_prompt,
        response_parser=_parse,
        output_field="arch_scan_summary",
        max_tokens=2048,
        retries=2,
    )
