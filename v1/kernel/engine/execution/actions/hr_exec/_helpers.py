"""hr_exec/_helpers.py — shared prompt/parser helpers for hr_exec leaves.

Mirrors arch_exec/_helpers.py in spirit: render a shared header block at
the top of every LLM prompt; tolerant JSON extractor that returns None
on parse failure so LlmActionLeaf can FAILURE-and-retry.
"""

from __future__ import annotations

import json
from typing import Any

# Re-export the arch_exec JSON extractor — same fenced/loose JSON rules.
from engine.execution.actions.arch_exec._helpers import extract_json  # noqa: F401


def render_header(bb) -> str:
    """Render the user_request + arch_plan summary block shared by all
    hr_exec sub-prompts."""
    user_request = (getattr(bb, "user_request", None) or "").strip() or "(空)"
    arch_plan = getattr(bb, "arch_plan", None)
    if arch_plan is None:
        plan_block = "(无)"
    else:
        try:
            plan_block = json.dumps(arch_plan, ensure_ascii=False, indent=2)[:2000]
        except (TypeError, ValueError):
            plan_block = repr(arch_plan)[:2000]
    return (
        "### 用户请求\n"
        f"{user_request}\n\n"
        "### Architect 任务清单（bb.arch_plan）\n"
        f"{plan_block}\n"
    )
