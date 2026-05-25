"""loops/memory_distill_governance.py — Memory distill governance descriptor.

Topology source: ``cbim/skills/memory_distill/skill.py`` semantic compression
contract. The MemDistill triad inside MemoryGovernanceStep yields to the
coordinator (main agent) — distillation is a memory-source responsibility
and is not outsourced. Semantic short→medium compression is LLM-driven,
but the canonical executor is the main agent itself (the ``memory_distill``
skill explicitly declares "Main agent only", and HR's MCP surface lacks
``memory_get`` so it cannot read short-term entry bodies).

Runs inside the coordinator during governance mode with
``subtask_id="governance_memory_distill"``. The coordinator reads the
skill via ``cbim skill show memory_distill`` and posts back a structured
report the dream-root CollectMemDistill action consumes.

This module owns:
  - ``compose_prompt(bb, store_dir)`` — renders the per-tick distill prompt
    embedding the current health snapshot;
  - ``parse_response(payload)`` — normalizes the reply into
    ``{"mem_distill_report": {...}}`` for CollectMemDistill.

Pairs with ``loops/hr_governance.py`` — same governance step container,
different executor (HR for capability scans, main agent for distillation).
"""
from __future__ import annotations

import json
from typing import Any


def compose_prompt(bb, store_dir: str) -> str:
    """Render the memory-distill governance prompt.

    Header marker ``## 治理模式`` matches the dream-loop dispatch convention.
    The coordinator (main agent) is the executor here — it reads the
    ``memory_distill`` skill and runs the compression itself using its
    ``memory_*`` MCP tools (including ``memory_get``, which HR does not
    have). The ``subtask_id`` ``governance_memory_distill`` discriminates
    this yield from the capability-governance yield routed to HR.
    """
    health = bb.mem_health or {}
    indicators = health.get("indicators") or {}
    breaches = health.get("breaches") or []

    short_count = indicators.get("short_count")
    short_bytes = indicators.get("short_bytes")
    oldest_age_days = indicators.get("oldest_age_days")
    medium_count = indicators.get("medium_count")

    lines: list[str] = [
        "## 治理模式（主 agent 记忆蒸馏子循环）",
        "",
        "你（主 agent）接到治理子任务。**唯一任务**：执行 `memory_distill` skill —— ",
        "把 `.cbim/memory/short/` 里达成蒸馏条件的条目压缩进 `.cbim/memory/medium/`。",
        "**不要做能力册扫描**（那是 `governance_capability` 子任务，会派给 HR）。",
        "**不要调** `dna_*` / `agent_*` 工具；只动 `.cbim/memory/`，全程走 `memory_*` MCP 工具。",
        "",
        "### 操作步骤（按序）",
        "1. 调 `skill_show` MCP 工具读 `memory_distill` 拿完整 skill 指令（等价旧 CLI `cbim skill show memory_distill`）。",
        "2. 按 skill 规则用 `memory_list` / `memory_query` / `memory_get` 扫 short 候选并读取正文，",
        "   按语义分类蒸馏成 medium 条目（用 `memory_create` 落盘）。",
        "3. 已蒸馏的 short 条目按 skill 规则在 frontmatter 打 `distilled: true` 标记，",
        "   等下一轮 compact / sweep 清理；不要直接 unlink。",
        "4. 装配下方 schema 回执，调 `dream_tick_resume(run_id, dispatch_result=<json>)` 回交。",
        "",
        "### 记忆库根目录（绝对路径，**只在此根下操作**）",
        f"`{store_dir}`",
        "",
        "### 本轮健康快照（来自 MemHealthScan）",
        f"- short_count: `{short_count}`",
        f"- short_bytes: `{short_bytes}`",
        f"- medium_count: `{medium_count}`",
        f"- oldest_age_days: `{oldest_age_days}`",
        f"- breaches: `{breaches}`",
        "",
        "### 回执 schema（严格 JSON，键名钉死）",
        "```json",
        "{",
        '  "mem_distill_report": {',
        '    "shorts_scanned": 0,',
        '    "shorts_marked_distilled": 0,',
        '    "medium_written":  [{"path": "<store_dir 下相对路径>", "type": "capability|decision|business", "sources": 0}],',
        '    "medium_updated":  [{"path": "<store_dir 下相对路径>", "type": "capability|decision|business", "sources": 0}],',
        '    "skipped_shorts":  [{"path": "<store_dir 下相对路径>", "reason": "signals_pending|context_specific"}],',
        '    "summary": "<一段话人类可读的本轮蒸馏摘要>"',
        "  }",
        "}",
        "```",
        "",
        "数组允许为空，但所有字段必须存在。",
        "`medium_written` / `medium_updated` 里每条 `path` **必须**指向真实落盘的文件",
        "（CollectMemDistill 会做存在性校验，缺失会被判 FAILURE）。",
        "若整轮无法完成（环境异常 / 工具失败），回 JSON `{\"error\": \"原因\"}`。",
        "",
        "### 铁律（必读）",
        "- 只动 `.cbim/memory/`，不调 `dna_*` / `agent_*`；",
        "- 只蒸馏短期，不删；删交给 compact / sweep；",
        "- 不发明内容；medium 条目必须来自 short 的真实痕迹。",
    ]
    return "\n".join(lines)


def parse_response(payload: str | dict | None) -> dict:
    """Normalize the distill response into ``{"mem_distill_report": ...}``.

    Same tolerance shape as ``architect_governance.parse_response`` /
    ``hr_governance.parse_response``:
      - dict with the expected wrapper key → unwrapped and returned
      - dict carrying ``error`` → returned as error sentinel
      - bare dict → wrapped as the report payload
      - str → JSON-parsed if possible, else wrapped raw
    """
    if payload is None or (isinstance(payload, str) and not payload.strip()):
        return {"mem_distill_report": None, "error": "empty response"}

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (ValueError, TypeError):
            return {"mem_distill_report": {"raw": payload}}

    if isinstance(payload, dict):
        if "error" in payload and "mem_distill_report" not in payload:
            return {"mem_distill_report": None, "error": str(payload["error"])}
        if "mem_distill_report" in payload:
            return {"mem_distill_report": payload["mem_distill_report"]}
        return {"mem_distill_report": payload}

    if isinstance(payload, list):
        return {"mem_distill_report": {"items": payload}}

    return {"mem_distill_report": {"raw": repr(payload)}}


__all__ = [
    "compose_prompt",
    "parse_response",
]
