"""
write-memory.py — Stop hook: parse session transcript and write a memory entry.

Receives JSON via stdin (Claude Code Stop event):
  { "transcript_path": "...", "cwd": "...", "session_id": "..." }

Parses the JSONL transcript to extract subagent dispatches and their results,
then writes memory/entries/YYYY-MM-DD-main-<slug>.md automatically.
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path


def read_transcript(path: str) -> list:
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


def extract_content_blocks(msg: dict) -> tuple[str, list]:
    """Return (role, list_of_content_blocks) from various transcript formats."""
    # Format A: {"role": "...", "content": ...}
    role = msg.get("role", "")
    content = msg.get("content", None)

    # Format B: {"type": "...", "message": {"role": "...", "content": ...}}
    if not role and "message" in msg:
        inner = msg["message"] or {}
        role = inner.get("role", "")
        content = inner.get("content", None)

    if isinstance(content, str):
        return role, [{"type": "text", "text": content}]
    if isinstance(content, list):
        return role, content
    return role, []


def parse_transcript(messages: list) -> dict:
    user_request = ""
    agent_calls = {}   # id -> {description, result}
    files_changed = []

    for msg in messages:
        role, blocks = extract_content_blocks(msg)

        for block in blocks:
            if not isinstance(block, dict):
                continue
            btype = block.get("type", "")

            # Capture first user text as the session request
            if btype == "text" and role == "user" and not user_request:
                user_request = block.get("text", "")[:300]

            # Agent tool dispatches
            elif btype == "tool_use" and block.get("name") == "Agent":
                bid = block.get("id", "")
                inp = block.get("input", {}) or {}
                agent_calls[bid] = {
                    "description": inp.get("description", ""),
                    "subagent_type": inp.get("subagent_type", ""),
                    "result": "",
                }

            # File writes/edits
            elif btype == "tool_use" and block.get("name") in ("Write", "Edit"):
                inp = block.get("input", {}) or {}
                p = inp.get("file_path", "")
                if p:
                    files_changed.append(p)

            # Tool results — match back to agent calls
            elif btype == "tool_result":
                tid = block.get("tool_use_id", "")
                if tid in agent_calls:
                    rc = block.get("content", "")
                    if isinstance(rc, list):
                        rc = " ".join(
                            c.get("text", "") for c in rc
                            if isinstance(c, dict) and c.get("type") == "text"
                        )
                    agent_calls[tid]["result"] = str(rc)[:600]

    return {
        "user_request": user_request,
        "agent_calls": list(agent_calls.values()),
        "files_changed": list(dict.fromkeys(files_changed)),  # dedupe, preserve order
    }


def slug(text: str) -> str:
    s = re.sub(r"[^\w一-鿿]+", "-", text[:50])
    return s.strip("-")[:30] or "session"


def build_entry(info: dict) -> str:
    req = info["user_request"] or "（未能提取）"

    # Subagent section
    calls = info["agent_calls"]
    if calls:
        agents_lines = []
        for c in calls:
            label = c["description"] or c["subagent_type"] or "subagent"
            agents_lines.append(f"### {label}")
            if c["result"]:
                agents_lines.append(f"结果：{c['result']}")
        agents_section = "\n".join(agents_lines)
    else:
        agents_section = "（本次 session 未调度 subagent）"

    # Files section
    files = info["files_changed"]
    files_section = "\n".join(f"- {f}" for f in files) if files else "（无文件写入）"

    return f"""---
tags: session
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


def main():
    raw = sys.stdin.read().strip()
    if not raw:
        sys.exit(0)

    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)

    transcript_path = event.get("transcript_path", "")
    cwd = event.get("cwd", os.getcwd())

    if not transcript_path:
        sys.exit(0)

    messages = read_transcript(transcript_path)
    if not messages:
        sys.exit(0)

    info = parse_transcript(messages)

    # Skip trivial sessions (no user request and no agent calls)
    if not info["user_request"] and not info["agent_calls"]:
        sys.exit(0)

    entries_dir = Path(cwd) / "memory" / "entries"
    entries_dir.mkdir(parents=True, exist_ok=True)

    date = datetime.now().strftime("%Y-%m-%d")
    name = slug(info["user_request"])
    entry_path = entries_dir / f"{date}-main-{name}.md"

    # Don't overwrite if already exists (e.g. hook fired twice)
    if entry_path.exists():
        import time
        ts = str(int(time.time()))[-4:]
        entry_path = entries_dir / f"{date}-main-{name}-{ts}.md"

    entry_path.write_text(build_entry(info), encoding="utf-8")
    print(f"[memory] wrote {entry_path.name}", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
