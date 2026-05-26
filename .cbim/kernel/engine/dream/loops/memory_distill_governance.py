"""loops/memory_distill_governance.py — Memory distill governance descriptor.

v2: the prompt now embeds the list of mature transcript paths that
``TranscriptScan`` collected on ``bb.transcript_paths``, not health
indicators. Distillation reads transcripts in-place via the main
agent's ``memory_distill`` skill; the dispatch is a self-yield
(``agent_type="main"``) so the coordinator executes the skill rather
than spawning a sub-agent.

This module owns:
  - ``compose_prompt(bb, store_dir)`` — renders the per-tick distill
    prompt, listing the transcript paths to ingest.
  - ``parse_response(payload)`` — normalizes the reply into
    ``{"mem_distill_report": {...}}`` for CollectMemDistill. The
    skill's reply schema (per cbi/skills/memory_distill/skill.py §步骤 8):

        {
          "distilled_paths":         ["<absolute path>", ...],
          "medium_entries_written":  ["<absolute path>", ...],
          "skipped_paths":           [{"path": "...", "reason": "..."}],
          "errors":                  ["..."]
        }

    Empty arrays are legal. ``TranscriptDelete`` consumes
    ``distilled_paths`` exclusively (skipped / errors files stay live
    for the next tick to retry).
"""
from __future__ import annotations

import json
from typing import Any


def compose_prompt(bb, store_dir: str) -> str:
    """Render the memory-distill governance prompt.

    Header marker ``## 治理模式`` matches the dream-loop dispatch
    convention. The coordinator is the executor — it reads the
    ``memory_distill`` skill (via ``cbim skill show memory_distill`` or
    the MCP ``skill_show`` tool) and runs the compression itself using
    its ``memory_*`` MCP tools.
    """
    paths = bb.transcript_paths or []
    paths_json = json.dumps(paths, ensure_ascii=False, indent=2)

    lines: list[str] = [
        "## 治理模式（主 agent 记忆蒸馏子循环）",
        "",
        "你（主 agent）接到治理子任务。**唯一任务**：执行 `memory_distill` skill —— ",
        "把下方 transcript JSONL 文件（mtime 超过 1 天的 Claude Code 会话流）",
        "蒸馏进 `.cbim/memory/medium/` 的四象限条目。",
        "**不要做能力册扫描**（那是 `governance_capability` 子任务，会派给 HR）。",
        "**不要调** `dna_*` / `agent_*` 工具；只动 `.cbim/memory/`，全程走 `memory_*` MCP 工具。",
        "",
        "### 操作步骤（按序）",
        "1. 调 `skill_show` MCP 工具读 `memory_distill` 拿完整 skill 指令",
        "   （等价旧 CLI `cbim skill show memory_distill`）。",
        "2. 按 skill 步骤 3-6 用 `Read` 工具逐文件读取 transcript，",
        "   按语义提炼 MUST / WANT / HOW / IS 四象限。",
        "3. 用 `memory_create` 落盘 medium 条目（tier=\"medium\"，已存在则更新）。",
        "4. **不要删 transcript、不要改 transcript、不要加任何标记**——",
        "   删除是治理循环 `TranscriptDelete` 节点的职责，它依赖你回报的 `distilled_paths`。",
        "5. 装配下方 schema 回执，调 `dream_tick_resume(run_id, dispatch_result=<json>)` 回交。",
        "",
        "### 记忆库根目录（绝对路径）",
        f"`{store_dir}`",
        "",
        f"### 本轮待蒸馏 transcript 列表（共 {len(paths)} 个，按 mtime 升序）",
        "```json",
        paths_json,
        "```",
        "",
        "### 回执 schema（严格 JSON，键名钉死）",
        "```json",
        "{",
        '  "distilled_paths":         ["<已蒸馏的 transcript 绝对路径>", ...],',
        '  "medium_entries_written":  ["<本轮写入或更新的 medium 文件绝对路径>", ...],',
        '  "skipped_paths":           [{"path": "<跳过的 transcript>", "reason": "no-signal|too-short|parse-error"}],',
        '  "errors":                  ["<人类可读错误描述>", ...]',
        "}",
        "```",
        "",
        "数组允许为空，但所有 4 个键必须存在。",
        "`distilled_paths` 必须只包含**确实已经成功提炼并写入 medium 的 transcript**——",
        "`TranscriptDelete` 会无条件删除其中每条路径。**蒸馏失败的不要放进 `distilled_paths`**；",
        "放进 `skipped_paths` 或 `errors`，下一轮 mtime 仍 > 1 天会再次入选重试。",
        "",
        "### 铁律（必读）",
        "- 只动 `.cbim/memory/`，不调 `dna_*` / `agent_*`；",
        "- 不删 transcript（删交给 TranscriptDelete）；",
        "- 不发明内容；medium 条目必须来自 transcript 的真实痕迹。",
    ]
    return "\n".join(lines)


def parse_response(payload: str | dict | None) -> dict:
    """Normalize the distill response into ``{"mem_distill_report": ...}``.

    Tolerance:
      - dict with the expected ``distilled_paths`` etc. shape → wrapped
      - dict with the explicit ``mem_distill_report`` wrapper key → unwrapped
      - dict carrying ``error`` (no report) → returned as error sentinel
      - str → JSON-parsed if possible, else treated as raw text error
    """
    if payload is None or (isinstance(payload, str) and not payload.strip()):
        return {"mem_distill_report": None, "error": "empty response"}

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (ValueError, TypeError):
            return {
                "mem_distill_report": None,
                "error": f"non-json response: {payload[:200]!r}",
            }

    if isinstance(payload, dict):
        # Skill emits the report at the top level (per skill.py §步骤 8);
        # explicit ``mem_distill_report`` wrapper is also accepted for
        # backward compatibility with the v1 schema.
        if "mem_distill_report" in payload:
            inner = payload["mem_distill_report"]
            if isinstance(inner, dict):
                return {"mem_distill_report": _coerce_report(inner)}
            return {
                "mem_distill_report": None,
                "error": "mem_distill_report must be a dict",
            }
        if "error" in payload and not any(
            k in payload for k in (
                "distilled_paths", "medium_entries_written",
                "skipped_paths", "errors",
            )
        ):
            return {"mem_distill_report": None, "error": str(payload["error"])}
        # Top-level schema.
        return {"mem_distill_report": _coerce_report(payload)}

    if isinstance(payload, list):
        return {
            "mem_distill_report": None,
            "error": "response was a list, expected JSON object",
        }

    return {
        "mem_distill_report": None,
        "error": f"unsupported response type {type(payload).__name__}",
    }


def _coerce_report(d: dict) -> dict:
    """Fill missing keys with empty defaults so downstream consumers
    don't need to .get() everywhere."""
    return {
        "distilled_paths": _as_str_list(d.get("distilled_paths")),
        "medium_entries_written": _as_str_list(d.get("medium_entries_written")),
        "skipped_paths": _as_list_of_dicts(d.get("skipped_paths")),
        "errors": _as_str_list(d.get("errors")),
    }


def _as_str_list(v: Any) -> list[str]:
    if not isinstance(v, list):
        return []
    return [str(x) for x in v if isinstance(x, (str, int, float))]


def _as_list_of_dicts(v: Any) -> list[dict]:
    if not isinstance(v, list):
        return []
    return [dict(x) for x in v if isinstance(x, dict)]


__all__ = [
    "compose_prompt",
    "parse_response",
]
