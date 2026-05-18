"""
writer.py — Session entry writer.

Encapsulates transcript parsing, entry formatting, file writing, and indexing.
Called by CLI write-session command; hooks are not aware of this logic.
"""

import json
import re
from datetime import datetime
from pathlib import Path

from .engine import MemoryEngine, SHORT


def write_session(transcript_path: str, store_dir: Path,
                  engine: MemoryEngine, cfg: dict) -> Path | None:
    """Parse transcript, write short-term entry, index it.

    Returns the entry path on success, None if session is trivial or unreadable.
    """
    messages = _read_transcript(transcript_path)
    if not messages:
        return None

    st = cfg["short_term"]
    info = _parse_transcript(
        messages,
        max_request_chars=st["max_request_chars"],
        max_result_chars=st["max_result_chars"],
    )
    if not info["user_request"] and not info["agent_calls"]:
        return None

    short_dir = store_dir / SHORT
    short_dir.mkdir(parents=True, exist_ok=True)

    date = datetime.now().strftime("%Y-%m-%d")
    name = _slug(
        info["user_request"],
        max_input=st["max_slug_input_chars"],
        max_output=st["max_slug_chars"],
    )
    entry_path = short_dir / f"{date}-main-{name}.md"

    if entry_path.exists():
        import time
        ts = str(int(time.time()))[-4:]
        entry_path = short_dir / f"{date}-main-{name}-{ts}.md"

    entry_path.write_text(_build_entry(info), encoding="utf-8")
    engine.add(entry_path, SHORT)
    _write_last_session(info, store_dir)
    return entry_path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _read_transcript(path: str) -> list:
    messages = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        messages.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    except (FileNotFoundError, PermissionError):
        pass
    return messages


def _extract_blocks(msg: dict) -> tuple[str, list]:
    role = msg.get("role", "")
    content = msg.get("content", None)
    if not role and "message" in msg:
        inner = msg["message"] or {}
        role = inner.get("role", "")
        content = inner.get("content", None)
    if isinstance(content, str):
        return role, [{"type": "text", "text": content}]
    if isinstance(content, list):
        return role, content
    return role, []


def _parse_transcript(messages: list, max_request_chars: int,
                      max_result_chars: int) -> dict:
    user_request = ""
    agent_calls: dict = {}
    files_changed: list = []
    modules: set = set()

    for msg in messages:
        role, blocks = _extract_blocks(msg)
        for block in blocks:
            if not isinstance(block, dict):
                continue
            btype = block.get("type", "")

            if btype == "text" and role == "user" and not user_request:
                user_request = block.get("text", "")[:max_request_chars]

            elif btype == "tool_use" and block.get("name") == "Agent":
                bid = block.get("id", "")
                inp = block.get("input", {}) or {}
                agent_calls[bid] = {
                    "description": inp.get("description", ""),
                    "subagent_type": inp.get("subagent_type", ""),
                    "result": "",
                }

            elif btype == "tool_use" and block.get("name") in ("Write", "Edit"):
                inp = block.get("input", {}) or {}
                p = inp.get("file_path", "")
                if p:
                    files_changed.append(p)
                    m = re.search(r"[/\\]([^/\\]+)[/\\]\.dna[/\\]", p)
                    if m:
                        modules.add(m.group(1))

            elif btype == "tool_result":
                tid = block.get("tool_use_id", "")
                if tid in agent_calls:
                    rc = block.get("content", "")
                    if isinstance(rc, list):
                        rc = " ".join(
                            c.get("text", "") for c in rc
                            if isinstance(c, dict) and c.get("type") == "text"
                        )
                    agent_calls[tid]["result"] = str(rc)[:max_result_chars]

    return {
        "user_request": user_request,
        "agent_calls": list(agent_calls.values()),
        "files_changed": list(dict.fromkeys(files_changed)),
        "modules": sorted(modules),
    }


def _write_last_session(info: dict, store_dir: Path) -> None:
    """Write last-session.md — a structured recovery note for the next session."""
    lines = [
        "## 上次 Session 恢复点",
        "",
        f"**任务**: {info['user_request'] or '（未能提取）'}",
        "",
    ]

    calls = info["agent_calls"]
    if calls:
        lines.append("**执行记录**:")
        for c in calls:
            label = c["description"] or c["subagent_type"] or "subagent"
            result = c["result"]
            preview = (result[:120] + "…") if len(result) > 120 else result
            lines.append(f"- {label}" + (f" → {preview}" if preview else ""))
        lines.append("")

    files = info["files_changed"]
    if files:
        lines.append("**改动文件**:")
        for f in files[:10]:
            lines.append(f"- {f}")
        if len(files) > 10:
            lines.append(f"- …共 {len(files)} 个文件")
        lines.append("")

    modules = info["modules"]
    if modules:
        lines.append(f"**涉及模块**: {', '.join(modules)}")
        lines.append("")

    lines.append("*如需接续上次工作，告知助手即可。*")

    last = store_dir / "last-session.md"
    store_dir.mkdir(parents=True, exist_ok=True)
    last.write_text("\n".join(lines), encoding="utf-8")


def _slug(text: str, max_input: int, max_output: int) -> str:
    s = re.sub(r"[^\w一-鿿]+", "-", text[:max_input])
    return s.strip("-")[:max_output] or "session"


def _build_entry(info: dict) -> str:
    req = info["user_request"] or "（未能提取）"
    modules_line = " ".join(info["modules"])
    frontmatter_extra = f"\nmodules: {modules_line}" if modules_line else ""

    calls = info["agent_calls"]
    if calls:
        lines = []
        for c in calls:
            label = c["description"] or c["subagent_type"] or "subagent"
            lines.append(f"### {label}")
            if c["result"]:
                lines.append(f"结果：{c['result']}")
        agents_section = "\n".join(lines)
    else:
        agents_section = "（本次 session 未调度 subagent）"

    files = info["files_changed"]
    files_section = "\n".join(f"- {f}" for f in files) if files else "（无文件写入）"

    return f"""---
tier: short
tags: session{frontmatter_extra}
---

## 任务概述
{req}

## Subagent 执行记录
{agents_section}

## 写入/修改文件
{files_section}

## 信号
- [ ] 能力缺口：
- [ ] 优秀模式：
- [ ] 知识更新候选：
"""
