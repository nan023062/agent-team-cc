"""hr_exec/match.py — Match LlmActionLeaf.

Given:
  - bb.hr_current_task         (one dict from arch_plan: id / description /
                                required_capability / ...)
  - bb.hr_agent_inventory      (list[dict] from Scan)

Asks the LLM to grade each known agent against the task's
required_capability and pick the best one. Writes:

    bb.hr_current_match = {
        "kind":       "fit" | "weak" | "miss",
        "agent_file": str | None,
        "note":       str,
    }

Iron rule: at most one LLM call per tick (delegated to LlmActionLeaf).
"""

from __future__ import annotations

import json
from typing import Any

from engine.core.llm_leaf import LlmActionLeaf

from ._helpers import extract_json, render_header


_VALID_KINDS = ("fit", "weak", "miss")


def _build_prompt(bb) -> str:
    task = getattr(bb, "hr_current_task", None) or {}
    inventory = getattr(bb, "hr_agent_inventory", None) or []
    task_block = json.dumps(task, ensure_ascii=False, indent=2)[:1500]
    # Compact inventory — only what's needed for matching.
    compact_inv = [
        {
            "agent_id": a.get("agent_id"),
            "agent_file": a.get("agent_file"),
            "description": (a.get("description") or "")[:200],
            "capabilities": a.get("capabilities") or [],
        }
        for a in inventory
    ]
    inv_block = json.dumps(compact_inv, ensure_ascii=False, indent=2)[:3000]
    return (
        "## HR 执行子循环 · Match\n\n"
        f"{render_header(bb)}\n"
        "### 当前子任务（bb.hr_current_task）\n"
        f"{task_block}\n\n"
        "### 现有工作 agent 清单（bb.hr_agent_inventory）\n"
        f"{inv_block}\n\n"
        "### 任务说明\n"
        "对比 task.required_capability / task.description 与每个 agent 的 "
        "capabilities/description，给出最佳匹配。判定档位：\n"
        "  - fit  ：能力完全覆盖该子任务，直接承接。\n"
        "  - weak ：能力相关但偏弱，可以承接但建议后续训练。\n"
        "  - miss ：清单中没有合适的 agent。\n"
        "miss 时 agent_file 写 null；fit/weak 必须给出清单中已存在的 agent_file。\n\n"
        "### 输出（仅 JSON）\n"
        "```json\n"
        '{"kind": "fit", "agent_file": ".claude/agents/<...>.md",'
        ' "note": "一句话说明匹配依据或为什么 miss"}\n'
        "```\n"
    )


def _parse(text: str) -> dict | None:
    data = extract_json(text)
    if not isinstance(data, dict):
        return None
    kind = data.get("kind")
    if kind not in _VALID_KINDS:
        return None
    agent_file = data.get("agent_file")
    if kind == "miss":
        agent_file = None
    else:
        if not isinstance(agent_file, str) or not agent_file.strip():
            return None
    note = data.get("note")
    if not isinstance(note, str):
        note = ""
    return {"kind": kind, "agent_file": agent_file, "note": note}


def build(llm_client: Any) -> LlmActionLeaf:
    return LlmActionLeaf(
        name="Match",
        llm_client=llm_client,
        prompt_builder=_build_prompt,
        response_parser=_parse,
        output_field="hr_current_match",
    )
