"""
write-memory.py — Stop hook: parse session transcript and write a short-term
memory entry to memory/store/short/, then index it via the memory engine.

Receives JSON via stdin (Claude Code Stop event):
  { "transcript_path": "...", "cwd": "...", "session_id": "..." }
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def _load_config(cwd: Path) -> dict:
    defaults = {
        "short_term": {
            "max_request_chars": 300,
            "max_result_chars": 600,
            "max_slug_input_chars": 50,
            "max_slug_chars": 30,
        },
        "hooks": {"timeout_seconds": 30},
    }
    config_path = cwd / "memory" / "config.json"
    if config_path.exists():
        try:
            user = json.loads(config_path.read_text(encoding="utf-8"))
            for section, values in user.items():
                if section in defaults and isinstance(values, dict):
                    defaults[section].update(values)
        except Exception:
            pass
    return defaults


def find_python(cwd: Path) -> str | None:
    for candidate in [
        cwd / ".venv" / "bin" / "python",
        cwd / ".venv" / "Scripts" / "python.exe",
    ]:
        if candidate.exists():
            return str(candidate)
    return None


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


def parse_transcript(messages: list, max_request_chars: int = 300,
                     max_result_chars: int = 600) -> dict:
    user_request = ""
    agent_calls = {}
    files_changed = []
    modules: set[str] = set()

    for msg in messages:
        role, blocks = extract_content_blocks(msg)
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
                    # Infer module names from paths like .aimodule/ directories
                    m = re.search(r"[/\\]([^/\\]+)[/\\]\.aimodule[/\\]", p)
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


def slug(text: str, max_input: int = 50, max_output: int = 30) -> str:
    s = re.sub(r"[^\w一-鿿]+", "-", text[:max_input])
    return s.strip("-")[:max_output] or "session"


def build_entry(info: dict) -> str:
    req = info["user_request"] or "（未能提取）"
    modules_line = " ".join(info["modules"]) if info["modules"] else ""
    frontmatter_extra = f"\nmodules: {modules_line}" if modules_line else ""

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


def main():
    raw = sys.stdin.read().strip()
    if not raw:
        sys.exit(0)

    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)

    transcript_path = event.get("transcript_path", "")
    cwd = Path(event.get("cwd", os.getcwd()))
    cfg = _load_config(cwd)
    st = cfg["short_term"]

    if not transcript_path:
        sys.exit(0)

    messages = read_transcript(transcript_path)
    if not messages:
        sys.exit(0)

    info = parse_transcript(
        messages,
        max_request_chars=st["max_request_chars"],
        max_result_chars=st["max_result_chars"],
    )
    if not info["user_request"] and not info["agent_calls"]:
        sys.exit(0)

    store_dir = cwd / "memory" / "store" / "short"
    store_dir.mkdir(parents=True, exist_ok=True)

    date = datetime.now().strftime("%Y-%m-%d")
    name = slug(info["user_request"],
                max_input=st["max_slug_input_chars"],
                max_output=st["max_slug_chars"])
    entry_path = store_dir / f"{date}-main-{name}.md"

    if entry_path.exists():
        import time
        ts = str(int(time.time()))[-4:]
        entry_path = store_dir / f"{date}-main-{name}-{ts}.md"

    entry_path.write_text(build_entry(info), encoding="utf-8")
    print(f"[memory] wrote {entry_path.name}", file=sys.stderr)

    # Index the new entry via the engine CLI
    python = find_python(cwd)
    if python:
        try:
            subprocess.run(
                [python, "-m", "memory.engine.cli", "add", str(entry_path), "--tier", "short"],
                cwd=str(cwd),
                timeout=cfg["hooks"]["timeout_seconds"],
                check=False,
            )
        except Exception:
            pass

    sys.exit(0)


if __name__ == "__main__":
    main()
