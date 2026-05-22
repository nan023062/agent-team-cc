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

# Short user replies that aren't actual task descriptions — we use these to
# distinguish "the meaningful task in this session" from "user's last ack".
_ACK_PHRASES = {
    # English
    "ok", "okay", "k", "kk", "yes", "yeah", "yep", "yup", "no", "nope",
    "thanks", "thx", "ty", "thank you", "got it", "sounds good",
    "go", "go on", "next", "continue", "done", "good", "great", "nice", "sure",
    # 中文
    "好", "好的", "嗯", "对", "是", "是的", "对了", "没错", "知道", "明白",
    "了解", "谢谢", "谢", "继续", "下一步", "搞定", "可以", "行", "完成",
    "执行", "go", "ok", "嗯嗯", "嗯哼", "好嘞", "收到",
}
_ACK_MAX_LEN = 10  # treat a message as an ack only if short AND in the list


def _is_substantive(text: str) -> bool:
    """A user message is substantive if it isn't a short acknowledgment."""
    s = (text or "").strip()
    if not s:
        return False
    if len(s) > _ACK_MAX_LEN:
        return True
    # Normalize: lowercase, strip trailing punctuation
    norm = s.lower().rstrip(".!?。！？～~ ")
    return norm not in _ACK_PHRASES

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
    distill_cfg = cfg.get("session_distill", {})
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
    name = _slug(_task_summary(info), max_input=st["max_slug_input_chars"], max_output=st["max_slug_chars"])
    entry_path = short_dir / f"{ts}-main-{name}.md"

    if not _should_write(info, short_dir):
        return None

    if entry_path.exists():
        ms = now.strftime("%f")[:3]
        entry_path = short_dir / f"{ts}-{ms}-main-{name}.md"

    # LLM session distillation (rich structured analysis for the entry body).
    # Returns None on no-API-key, skipped chat-only sessions, or any error.
    distill = None
    if distill_cfg.get("enabled", True) and _should_distill(info, distill_cfg):
        distill = _llm_session_distill(messages, info, distill_cfg)

    entry_path.write_text(_build_entry(info, distill=distill), encoding="utf-8")
    engine.add(entry_path, SHORT)

    # Fill ## 信号 index: prefer signals regex-extracted from the distillation
    # (which already capture the four quadrants with full reasoning), falling
    # back to heuristic signals when distillation is empty/missing.
    signals: list[str] = []
    if distill:
        signals = _extract_signals_from_distill(distill)
    if not signals:
        signals = _heuristic_signals(info)
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
# Signal filling — Layer B: LLM session distillation
# ---------------------------------------------------------------------------
#
# Replaces the prior _llm_signals: instead of emitting ~10 bare signal lines,
# the LLM now produces a structured Markdown distillation of decisions,
# judgments, fact changes, corrections, and open items — used as the body of
# the short entry. Signal lines are then regex-extracted from this output to
# populate the ## 信号 index section.

def _get_api_key() -> str | None:
    import os
    return os.environ.get("ANTHROPIC_API_KEY", "").strip() or None


def _should_distill(info: dict, distill_cfg: dict) -> bool:
    """Skip LLM distillation when the turn produced no real work (chat only).

    Avoids LLM cost/latency on pure-conversation turns that have nothing
    architecturally interesting to distill.
    """
    if not distill_cfg.get("skip_if_no_work", True):
        return True
    return bool(info.get("agent_calls") or info.get("files_changed"))


def _build_distill_context(messages: list, info: dict, max_chars: int) -> str:
    """Build a compact but information-dense context from the full transcript.

    Includes every user text, assistant text reply, agent dispatch description,
    file write, and tool result preview — in time order. Long sessions are
    truncated keeping the head and tail (conclusion).
    """
    parts: list[str] = []

    if info.get("modules"):
        parts.append(f"涉及模块: {', '.join(info['modules'])}")
    if info.get("files_changed"):
        flist = "\n".join(f"  - {f}" for f in info["files_changed"][:20])
        parts.append(f"改动文件:\n{flist}")

    parts.append("\n--- 对话流（按时间顺序）---")
    for msg in messages:
        role, blocks = _extract_blocks(msg)
        for block in blocks:
            if not isinstance(block, dict):
                continue
            btype = block.get("type", "")
            if btype == "text":
                txt = (block.get("text") or "").strip()
                if not txt:
                    continue
                # Cap individual messages so one giant blob doesn't crowd out
                # the rest of the conversation.
                txt = txt[:2000]
                label = "用户" if role == "user" else "助手"
                parts.append(f"\n[{label}]\n{txt}")
            elif btype == "tool_use" and block.get("name") == "Agent":
                inp = block.get("input", {}) or {}
                desc = inp.get("description", "")
                subagent = inp.get("subagent_type", "")
                parts.append(f"\n[调度 → {subagent}] {desc}")
            elif btype == "tool_use" and block.get("name") in ("Write", "Edit"):
                inp = block.get("input", {}) or {}
                p = inp.get("file_path", "")
                if p:
                    parts.append(f"\n[写文件] {p}")
            elif btype == "tool_result":
                rc = block.get("content", "")
                if isinstance(rc, list):
                    rc = " ".join(
                        c.get("text", "") for c in rc
                        if isinstance(c, dict) and c.get("type") == "text"
                    )
                rc = str(rc).strip()
                if rc:
                    parts.append(f"\n[结果] {rc[:400]}")

    full = "\n".join(parts)
    if len(full) > max_chars:
        head = int(max_chars * 0.35)
        tail = max_chars - head - 60
        full = (
            full[:head]
            + "\n\n[...中间内容因长度截断，保留开头和结尾...]\n\n"
            + full[-tail:]
        )
    return full


_DISTILL_PROMPT = """你是 CBIM 项目的 session 蒸馏官。下面是一次 Claude Code session 的完整关键内容（用户对话、assistant 回复、agent 调度、文件改动）。

任务：把本次 session 中真正值得长期记下的"决策、判断、事实变更、纠正"提炼出来，作为后续蒸馏到 medium-term memory / .dna / agent soul 的源料。

---

{context}

---

## 输出格式（严格 Markdown，缺哪段就整段省略，不要写"无"）

### 决策与判断
每条以 `**WANT**` 或 `**HOW**` 开头：
- `**WANT** <模块或范围>: <选了什么 / 为什么 / 拒绝了什么 / 代价>` —— 项目特定的"为什么选 A 不选 B"
- `**HOW** <agent-id 或 模块>: <什么场景 / 步骤 / 验证有效在哪>` —— 流程模式

### 事实变更
每条以 `**IS**` 开头：
- `**IS** <模块>: <什么 从 A 变成 B>` —— 接口/规则/配置变更

### 纠正与教训
每条以 `**MUST**` 开头：
- `**MUST** <agent-id 或 范围>: <用户纠正了什么 / 今后必须如何>`

### 未决与遗留
不带前缀，直接描述：未回答的问题、阻塞、留给下次的工作。

---

## 严格要求
- 不要无中生有 —— session 里没观察到就不写
- 决策必须含"为什么"；事实变更必须有"从...到..."
- 用用户对话用的语言（中文项目就用中文）
- 整段控制在 600-1500 字
- 没有这类信号就整段省略；可以整体输出为空（不要写"无内容"或解释）"""


def _llm_session_distill(messages: list, info: dict,
                         distill_cfg: dict) -> str | None:
    """Call Anthropic API for structured session distillation.

    Returns the Markdown distillation text, or None if no API key / on error.
    Caller embeds the result in the entry body and regex-extracts signal lines.
    """
    api_key = _get_api_key()
    if not api_key:
        return None

    model = distill_cfg.get("model", "claude-haiku-4-5-20251001")
    max_tokens = distill_cfg.get("max_tokens", 2000)
    timeout = distill_cfg.get("timeout", 30)
    input_max_chars = distill_cfg.get("input_max_chars", 12000)

    context = _build_distill_context(messages, info, input_max_chars)
    prompt = _DISTILL_PROMPT.format(context=context)

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
            return text if text else None
    except Exception:
        return None


_SIGNAL_LINE_RE = re.compile(
    r"\*\*(MUST|WANT|HOW|IS)\*\*\s+([^:：]+?)[:：]\s*(.+)"
)


def _extract_signals_from_distill(distill_text: str) -> list[str]:
    """Regex-extract quadrant signals from the LLM distillation text.

    The prompt format produces bullets like:
        - **WANT** combat-module: 选 ECS 而非 OOP，因为 …
    Returns canonical 'WANT: combat-module: …' strings that _fill_signals
    knows how to write into the ## 信号 section.
    """
    out: list[str] = []
    for line in distill_text.splitlines():
        m = _SIGNAL_LINE_RE.search(line)
        if not m:
            continue
        quadrant = m.group(1)
        subject = m.group(2).strip()
        body = m.group(3).strip()
        if len(body) > 120:
            body = body[:120].rstrip() + "…"
        out.append(f"{quadrant}: {subject}: {body}")
    return out


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
    all_user_texts: list = []
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
                txt = block.get("text", "")
                if txt:
                    all_user_texts.append(txt)

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

    # The "task" of this session = first substantive (non-ack) user message.
    # Falls back to the very first user text if everything was an ack.
    substantive = [t for t in all_user_texts if _is_substantive(t)]
    if substantive:
        user_request = substantive[0][:max_request_chars]
    elif all_user_texts:
        user_request = all_user_texts[0][:max_request_chars]
    else:
        user_request = ""

    # Last raw user message — preserves "how the session ended"
    # (e.g. "继续" tells you the user wanted to keep going).
    last_user_message = all_user_texts[-1][:max_request_chars] if all_user_texts else ""

    # All substantive topics (capped) — useful when one session covered
    # several distinct requests.
    topics = [t[:max_request_chars] for t in substantive]

    return {
        "user_request": user_request,
        "last_user_message": last_user_message,
        "topics": topics,
        "user_turn_count": len(all_user_texts),
        "agent_calls": list(agent_calls.values()),
        "files_changed": list(dict.fromkeys(files_changed)),
        "modules": sorted(modules),
    }


# ---------------------------------------------------------------------------
# Entry formatting
# ---------------------------------------------------------------------------

def _slug(text: str, max_input: int, max_output: int) -> str:
    s = re.sub(r"[^\w一-鿿]+", "-", text[:max_input])
    return s.strip("-")[:max_output] or "session"


def _task_summary(info: dict) -> str:
    calls = info.get("agent_calls") or []
    if calls:
        desc = (calls[0].get("description") or "").strip()
        if desc:
            return desc
    return info.get("user_request", "")


def _build_entry(info: dict, distill: str | None = None) -> str:
    """Build the short-entry markdown.

    If `distill` (LLM session analysis) is provided, it's embedded as the
    `## 本次决策与提炼` section — the highest-density part of the entry,
    intended as primary source for short→medium→knowledge distillation.

    The `## 信号` section at the bottom is the indexable four-quadrant tag
    list — extracted from `distill` (or from heuristics when LLM is absent).
    """
    req = info["user_request"] or "（未能提取）"
    modules_line = " ".join(info["modules"])
    frontmatter_extra = f"\nmodules: {modules_line}" if modules_line else ""

    distill_section = ""
    if distill and distill.strip():
        distill_section = (
            "\n## 本次决策与提炼（LLM）\n\n"
            f"{distill.strip()}\n"
        )

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
{distill_section}
## Subagent 执行记录
{agents_section}

## 写入/修改文件
{files_section}

## 信号
"""
