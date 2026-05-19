"""
writer.py — Session entry writer.

Encapsulates transcript parsing, entry formatting, file writing, and signal filling.
Called by CLI write-session command; hooks are not aware of this logic.

Signal filling strategy (two-tier):
  A. Heuristic: deterministic patterns from transcript structure (zero latency, no API)
  B. LLM: claude-haiku call with session summary (semantic, ~1-2s, falls back to A on error)
"""

import json
import re
from datetime import datetime
from pathlib import Path

from .engine import MemoryEngine, SHORT

_CORRECTION_PATTERNS = [
    "不对", "错了", "不应该", "不要", "你不能", "应该改", "重新做",
    "incorrect", "wrong", "don't do", "shouldn't", "stop doing",
]

_FORCE_WRITE_KEYWORDS = [
    # 显式记忆请求
    "记住", "记下", "保存", "remember", "save this",
    # 对错判断
    "对了", "正确", "没错", "就是这样", "exactly", "correct", "confirmed",
    # 下决策
    "决定", "定了", "就用", "采用", "改成", "换成", "decided", "we'll go with",
    # 是什么 / 不是什么（精确短语，避免"不是"误触发）
    "应该是", "不是而是", "而不是", "指的是", "定义",
    # 怎么做 / 规则
    "规则是", "约定", "原则", "以后都", "每次都", "不再", "统一",
]


def _should_write(info: dict, short_dir: Path) -> bool:
    req = info["user_request"]
    req_lower = req.lower()
    if any(kw in req_lower for kw in _FORCE_WRITE_KEYWORDS):
        return True

    try:
        candidates = list(short_dir.glob("*.md"))
        if not candidates:
            return True
        latest = max(candidates, key=lambda p: p.stat().st_mtime)
        text = latest.read_text(encoding="utf-8")

        task_match = re.search(r"## 任务概述\n(.*?)(?=\n##|\Z)", text, re.DOTALL)
        prev_request = task_match.group(1).strip() if task_match else ""

        files_match = re.search(r"## 写入/修改文件\n(.*?)(?=\n##|\Z)", text, re.DOTALL)
        prev_files: set[str] = set()
        if files_match:
            for line in files_match.group(1).splitlines():
                line = line.strip().lstrip("- ").strip()
                if line:
                    prev_files.add(line)

        current_files = set(info["files_changed"])
        if req == prev_request and current_files == prev_files:
            return False
    except Exception:
        return True

    return True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def write_session(transcript_path: str, store_dir: Path,
                  engine: MemoryEngine, cfg: dict) -> Path | None:
    """Parse transcript, write short-term entry, auto-fill signals.

    Returns the entry path on success, None if session is trivial or unreadable.
    """
    messages = _read_transcript(transcript_path)
    if not messages:
        return None

    st = cfg["short_term"]
    sig_cfg = cfg.get("signals", {})
    ls_cfg = cfg.get("last_session", {})
    info = _parse_transcript(
        messages,
        max_request_chars=st["max_request_chars"],
        max_result_chars=st["max_result_chars"],
    )
    if not info["user_request"] and not info["agent_calls"]:
        return None

    short_dir = store_dir / SHORT
    short_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    ts = now.strftime("%Y-%m-%d-%H%M%S")
    name = _slug(
        info["user_request"],
        max_input=st["max_slug_input_chars"],
        max_output=st["max_slug_chars"],
    )
    entry_path = short_dir / f"{ts}-main-{name}.md"

    if not _should_write(info, short_dir):
        return None

    if entry_path.exists():
        ms = now.strftime("%f")[:3]
        entry_path = short_dir / f"{ts}-{ms}-main-{name}.md"

    entry_path.write_text(_build_entry(info), encoding="utf-8")
    engine.add(entry_path, SHORT)
    _write_last_session(info, store_dir, ls_cfg)

    # Auto-fill signals: A (heuristic) → B (LLM supplements A; falls back to A on error)
    heuristic = _heuristic_signals(info)
    llm = _llm_signals(info, heuristic, sig_cfg)
    signals = llm if llm else heuristic
    if signals:
        _fill_signals(entry_path, signals)

    return entry_path


# ---------------------------------------------------------------------------
# Signal filling — Layer A: heuristics
# ---------------------------------------------------------------------------

def _heuristic_signals(info: dict) -> list[str]:
    """Extract deterministic signals from structured transcript data. No LLM needed."""
    signals = []

    for f in info["files_changed"]:
        norm = f.replace("\\", "/")
        in_dna = "/.dna/" in norm or norm.startswith(".dna/")
        if not in_dna:
            continue
        m = re.search(r"/([^/]+)/\.dna/", norm)
        mod = m.group(1) if m else (info["modules"][0] if info["modules"] else "unknown")
        if norm.endswith("contract.md"):
            signals.append(f"IS: {mod}: contract.md 已修改")
        elif norm.endswith("module.md"):
            signals.append(f"WANT: {mod}: module.md 已修改（决策待补充）")
        elif norm.endswith("architecture.md"):
            signals.append(f"WANT: {mod}: architecture.md 已修改（决策待补充）")

    # MUST: user correction
    req = info["user_request"].lower()
    if any(kw in req for kw in _CORRECTION_PATTERNS):
        signals.append("MUST: assistant: 用户发起了纠正（见任务概述）")

    return signals


# ---------------------------------------------------------------------------
# Signal filling — Layer B: LLM
# ---------------------------------------------------------------------------

def _get_api_key() -> str | None:
    import os
    return os.environ.get("ANTHROPIC_API_KEY", "").strip() or None


def _llm_signals(info: dict, heuristic: list[str], sig_cfg: dict) -> list[str]:
    """Call Anthropic API (claude-haiku) to extract signals from session summary.

    Returns [] on any error — caller falls back to heuristic signals.
    """
    api_key = _get_api_key()
    if not api_key:
        return []

    model = sig_cfg.get("model", "claude-haiku-4-5-20251001")
    max_tokens = sig_cfg.get("max_tokens", 300)
    timeout = sig_cfg.get("timeout", 20)
    max_files = sig_cfg.get("max_files_in_prompt", 10)

    agent_descs = [c["description"] or c["subagent_type"] for c in info["agent_calls"]]
    heuristic_note = (
        "已通过启发式检测到：" + "；".join(heuristic)
        if heuristic else "无启发式结果"
    )

    prompt = f"""根据以下 session 摘要，提取值得记录的信号。

## Session 摘要
任务：{info['user_request']}
调用的 Agent：{', '.join(agent_descs) or '无'}
改动文件：{'; '.join(info['files_changed'][:max_files]) or '无'}
涉及模块：{', '.join(info['modules']) or '无'}
启发式参考（{heuristic_note}）

## 四象限定义
MUST（跨项目原则）：什么绝对不能违反？如 agent 越位、用户纠正行为、不可逆操作缺少确认
WANT（项目决策）：为什么选这个方案？如技术选型、架构取舍、接口设计的主动决策
HOW（执行流程）：哪个方法/顺序显著有效或有问题？
IS（当前事实）：接口签名、业务规则定义、配置值等有什么变更？

## 输出规则
- 每行一条，格式严格为：象限: 主体: 描述（主体用 agent-id 或模块名）
- 只输出有实质内容的信号行，没有就不输出任何内容
- 不要解释，不要多余文字"""

    import urllib.request as _req
    import json as _json

    payload = _json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()

    request = _req.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    try:
        with _req.urlopen(request, timeout=timeout) as resp:
            data = _json.loads(resp.read())
            text = data["content"][0]["text"].strip()
            return [
                line for line in text.splitlines()
                if re.match(r"^(MUST|WANT|HOW|IS):\s*.+:\s*.+", line)
            ]
    except Exception:
        return []


def _fill_signals(entry_path: Path, signals: list[str]) -> None:
    """Overwrite the ## 信号 section with filled signal lines."""
    content = entry_path.read_text(encoding="utf-8")
    marker = "\n## 信号\n"
    idx = content.find(marker)
    if idx == -1:
        return
    prefix = content[:idx + len(marker)]
    body = "\n".join(f"- [x] {s}" for s in signals) + "\n"
    entry_path.write_text(prefix + body, encoding="utf-8")


# ---------------------------------------------------------------------------
# Transcript parsing
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

            if btype == "text" and role == "user":
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


# ---------------------------------------------------------------------------
# Entry and recovery note formatting
# ---------------------------------------------------------------------------

def _write_last_session(info: dict, store_dir: Path, ls_cfg: dict | None = None) -> None:
    """Write last-session.md — a structured recovery note for the next session."""
    ls_cfg = ls_cfg or {}
    preview_chars = ls_cfg.get("result_preview_chars", 120)
    max_files = ls_cfg.get("max_files", 10)

    ended_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "## 上次 Session 恢复点",
        "",
        f"**结束时间**: {ended_at}",
        f"**最后任务**: {info['user_request'] or '（未能提取）'}",
        "",
    ]

    calls = info["agent_calls"]
    if calls:
        lines.append("**执行记录**:")
        for c in calls:
            label = c["description"] or c["subagent_type"] or "subagent"
            result = c["result"]
            preview = (result[:preview_chars] + "…") if len(result) > preview_chars else result
            lines.append(f"- {label}" + (f" → {preview}" if preview else ""))
        lines.append("")

    files = info["files_changed"]
    if files:
        lines.append("**改动文件**:")
        for f in files[:max_files]:
            lines.append(f"- {f}")
        if len(files) > max_files:
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
"""
