"""
logger.py — CBIM session logger (dedicated log module).

All session log writes flow through this module. Centralises:
  - Session file lifecycle (create, pointer, finalise)
  - Tag definitions and high-level write helpers
  - Transcript extraction (assistant final text)

Signal tags written to .cbim/logs/session_<ts>_<id>.log:

  Conversation flow (real-time via hooks):
    [USER]        Full user prompt — UserPromptSubmit hook
    [CALL]        Tool invocation — PreToolUse hook
    [CBIM:<dom>]  cbim CLI call (dom = dna|agent|skill|memory|…) — PreToolUse
    [CBIM:skill]  Skill tool invocation — PreToolUse
    [CBIM:agent]  Agent tool dispatch — PreToolUse
    [RET]         Tool result preview — PostToolUse hook

  End-of-turn (Stop hook + transcript):
    [ASSIST]      Full assistant text — extracted from transcript JSONL

  Infrastructure (always-on):
    [MCP]         MCP tool call
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from functools import lru_cache
from pathlib import Path

_MAX_ENTRY_CHARS = 3000   # [USER] / [ASSIST] cap
_MAX_CMD_CHARS   = 400    # Bash command preview
_MAX_RET_CHARS   = 300    # tool result preview (regular tools)
_MAX_RET_AGENT   = 600    # tool result preview (Agent — important output)


# ---------------------------------------------------------------------------
# Agent identity — derived from the hook event's transcript_path.
#
# Claude Code transcript layout:
#   Main session : <project_slug>/<session_id>.jsonl
#   Subagent     : <project_slug>/<session_id>/subagents/agent-<aid>.jsonl
#                  + sibling agent-<aid>.meta.json containing {"agentType": ...}
#
# Only transcript_path carries reliable agent identity in hook payloads;
# session_id / cwd / tool_name do not.
# ---------------------------------------------------------------------------

@lru_cache(maxsize=128)
def _agent_label(transcript_path: str) -> str:
    """Return '[agent:<name>] ' for subagent transcripts, '' for main session."""
    if not transcript_path:
        return ""
    try:
        p = Path(transcript_path)
        if p.parent.name != "subagents":
            return ""
        meta = p.with_suffix(".meta.json")
        if not meta.exists():
            return ""
        data = json.loads(meta.read_text(encoding="utf-8"))
        name = (data.get("agentType") or "").strip()
        return f"[agent:{name}] " if name else ""
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _ctx_cbim_dir() -> Path:
    from context import cbim_dir
    return cbim_dir()


def cbim_root_from_cwd() -> Path | None:
    """Walk up from cwd to find a .cbim/ directory."""
    p = Path.cwd().resolve()
    for _ in range(6):
        if (p / ".cbim").is_dir():
            return p / ".cbim"
        if p.parent == p:
            break
        p = p.parent
    return None


def logs_dir(cbim: Path | None = None) -> Path:
    """Return .cbim/logs/, creating it if missing."""
    cbim = cbim or cbim_root_from_cwd() or _ctx_cbim_dir()
    d = cbim / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _pointer_path(cbim: Path | None = None) -> Path:
    return logs_dir(cbim) / ".current"


def current_log_path(cbim: Path | None = None) -> Path | None:
    """Return the active session log, or most-recent session log as fallback."""
    pointer = _pointer_path(cbim)
    if pointer.exists():
        try:
            target = Path(pointer.read_text(encoding="utf-8").strip())
            if target.exists():
                return target
        except OSError:
            pass
    candidates = sorted(logs_dir(cbim).glob("session_*.log"))
    return candidates[-1] if candidates else None


# ---------------------------------------------------------------------------
# Low-level write
# ---------------------------------------------------------------------------

def _escape(text: str) -> str:
    """Collapse text to a single line (replace newlines with literal \\n)."""
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n")


def append(
    tag: str,
    message: str,
    cbim: Path | None = None,
    log_path: Path | None = None,
    transcript_path: str = "",
) -> None:
    """Append one timestamped line to the current session log.

    When transcript_path points to a subagent transcript, the line is tagged
    with [agent:<name>] between the tag and the message. Main-session lines
    carry no agent label.

    Creates an orphan session log on the fly if no session has started yet.
    Swallows all exceptions — logging must never crash the host process.
    """
    try:
        cbim = cbim or cbim_root_from_cwd() or _ctx_cbim_dir()
        path = log_path or current_log_path(cbim)
        if path is None:
            path = _create_session_file("orphan", os.getcwd(), cbim)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        agent = _agent_label(transcript_path)
        line = f"[{ts}] [{tag}] {agent}{_escape(message)}\n"
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

def _create_session_file(session_id: str, cwd: str, cbim: Path) -> Path:
    """Create the log file and write the .current pointer."""
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    short = (session_id or "anon").replace("/", "_").replace("\\", "_")[:8]
    log_path = logs_dir(cbim) / f"session_{ts}_{short}.log"
    log_path.touch(exist_ok=True)
    _pointer_path(cbim).write_text(str(log_path), encoding="utf-8")
    return log_path


def start_session(session_id: str = "", cwd: str = "", cbim: Path | None = None) -> Path:
    """Open a new session log file. No tag written — [USER] marks turn starts."""
    cbim = cbim or cbim_root_from_cwd() or _ctx_cbim_dir()
    return _create_session_file(session_id, cwd, cbim)


def end_session(session_id: str = "", reason: str = "", cbim: Path | None = None) -> Path | None:
    """Clear the .current pointer to finalise the session log."""
    cbim = cbim or cbim_root_from_cwd() or _ctx_cbim_dir()
    path = current_log_path(cbim)
    if path is None:
        return None
    pointer = _pointer_path(cbim)
    try:
        if pointer.exists():
            pointer.unlink()
    except OSError:
        pass
    return path


# ---------------------------------------------------------------------------
# Tool call formatting — shared by PreToolUse and PostToolUse hooks
# ---------------------------------------------------------------------------

def format_tool_call(tool: str, inp: dict) -> tuple[str, str]:
    """Return (tag, message) for a tool invocation.

    CBIM-specific tools get [CBIM:*] tags; everything else gets [CALL].
    """
    if tool == "Bash":
        cmd = str(inp.get("command", "")).strip()
        if cmd == "cbim" or cmd.startswith("cbim "):
            parts = cmd.split()
            domain = parts[1] if len(parts) > 1 else ""
            tag = f"CBIM:{domain}" if domain else "CBIM"
            display = cmd if len(cmd) <= _MAX_CMD_CHARS else cmd[:_MAX_CMD_CHARS] + "…"
            return tag, display
        preview = cmd if len(cmd) <= _MAX_CMD_CHARS else cmd[:_MAX_CMD_CHARS] + "…"
        return "CALL", f"Bash | {preview}"

    if tool == "Skill":
        skill = inp.get("skill", "?")
        args = (inp.get("args", "") or "").strip()
        msg = f"skill={skill!r}" + (f" args={args!r}" if args else "")
        return "CBIM:skill", msg

    if tool == "Agent":
        subagent = inp.get("subagent_type", "default")
        desc = str(inp.get("description", "") or "")[:120]
        return "CBIM:agent", f"subagent={subagent} desc={desc!r}"

    if tool in ("Read", "Write", "Edit", "MultiEdit"):
        return "CALL", f"{tool} | {inp.get('file_path', '?')}"

    if tool == "Glob":
        pat = inp.get("pattern", "?")
        path = inp.get("path", "")
        return "CALL", f"Glob | {pat}" + (f" in {path}" if path else "")

    if tool == "Grep":
        pat = inp.get("pattern", "?")
        path = inp.get("path", "")
        return "CALL", f"Grep | {pat!r}" + (f" in {path}" if path else "")

    if tool == "WebFetch":
        return "CALL", f"WebFetch | {inp.get('url', '?')}"

    if tool == "WebSearch":
        return "CALL", f"WebSearch | {inp.get('query', '?')!r}"

    if tool in ("TaskCreate", "TaskUpdate", "TaskList", "TaskGet", "TaskStop"):
        subject = inp.get("subject", "") or inp.get("taskId", "") or ""
        return "CALL", f"{tool}" + (f" | {subject}" if subject else "")

    return "CALL", f"{tool} | {len(inp)} params"


# ---------------------------------------------------------------------------
# High-level write helpers — called by hooks
# ---------------------------------------------------------------------------

def log_user(prompt: str, cbim: Path | None = None, transcript_path: str = "") -> None:
    """[USER] full user prompt."""
    text = (prompt or "").strip()
    if len(text) > _MAX_ENTRY_CHARS:
        text = text[:_MAX_ENTRY_CHARS] + "…"
    append("USER", text, cbim=cbim, transcript_path=transcript_path)


def log_call(tool: str, inp: dict, cbim: Path | None = None, transcript_path: str = "") -> None:
    """[CALL] / [CBIM:*] tool invocation — called from PreToolUse hook."""
    tag, message = format_tool_call(tool, inp)
    append(tag, message, cbim=cbim, transcript_path=transcript_path)


def log_ret(
    tool: str,
    inp: dict,
    response: dict,
    cbim: Path | None = None,
    transcript_path: str = "",
) -> None:
    """[RET] tool result preview — called from PostToolUse hook."""
    is_error = bool(response.get("is_error") or response.get("error"))
    status = "ERR" if is_error else "ok"

    out = response.get("content") or response.get("stdout") or ""
    if isinstance(out, list):
        out = " ".join(
            x.get("text", "") for x in out
            if isinstance(x, dict) and x.get("type") == "text"
        )
    out = str(out).strip()

    cap = _MAX_RET_AGENT if tool == "Agent" else _MAX_RET_CHARS
    preview = out if len(out) <= cap else out[:cap] + "…"

    # For CBIM bash, tag the result to match the call tag
    if tool == "Bash":
        cmd = str((inp or {}).get("command", "")).strip()
        if cmd == "cbim" or cmd.startswith("cbim "):
            parts = cmd.split()
            domain = parts[1] if len(parts) > 1 else ""
            tag = f"RET:{domain}" if domain else "RET"
            append(
                tag,
                f"{status} | {preview}" if preview else status,
                cbim=cbim,
                transcript_path=transcript_path,
            )
            return

    append(
        "RET",
        f"{tool} | {status}" + (f" | {preview}" if preview else ""),
        cbim=cbim,
        transcript_path=transcript_path,
    )


def log_assist(transcript_path: str, cbim: Path | None = None) -> None:
    """[ASSIST] final assistant text — extracted from transcript at Stop."""
    text = _last_assistant_text(transcript_path)
    if not text:
        return
    if len(text) > _MAX_ENTRY_CHARS:
        text = text[:_MAX_ENTRY_CHARS] + "…"
    append("ASSIST", text, cbim=cbim, transcript_path=transcript_path)


# ---------------------------------------------------------------------------
# Transcript extraction
# ---------------------------------------------------------------------------

def _last_assistant_text(transcript_path: str) -> str:
    """Read the JSONL transcript and return the last assistant turn's text."""
    try:
        messages: list = []
        with open(transcript_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        messages.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

        for msg in reversed(messages):
            role = msg.get("role", "")
            content = msg.get("content", None)
            if not role and "message" in msg:
                inner = msg.get("message") or {}
                role = inner.get("role", "")
                content = inner.get("content", None)

            if role != "assistant":
                continue

            texts: list[str] = []
            if isinstance(content, str):
                texts.append(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        t = block.get("text", "")
                        if t:
                            texts.append(t)

            full = "\n".join(texts).strip()
            if full:
                return full
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# Deprecated helpers — kept for any remaining callers
# ---------------------------------------------------------------------------

def log_cbim_call(tag: str, message: str, cbim: Path | None = None) -> None:
    append(tag, message, cbim=cbim)
