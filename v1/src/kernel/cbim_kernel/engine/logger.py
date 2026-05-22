"""
logger.py — CBIM session logger (dedicated log module).

All session log writes flow through this module. Centralises:
  - Session file lifecycle (create, pointer, finalise)
  - Tag definitions and high-level write helpers
  - Transcript extraction (assistant response)

Signal tags written to .cbim/logs/session_<ts>_<id>.log:
  [USER]        Full user prompt — written at UserPromptSubmit
  [ASSIST]      Full assistant text — written at Stop (from transcript JSONL)
  [CBIM:<dom>]  cbim CLI call — dom = dna | agent | skill | memory | workflow | …
  [CBIM:skill]  Skill tool invocation
  [CBIM:agent]  Agent tool dispatch
  [MCP]         MCP tool call (always-on; these ARE CBIM operations)
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

_MAX_ENTRY_CHARS = 3000  # per-entry cap; prompts/responses can be large


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _ctx_cbim_dir() -> Path:
    from cbim_kernel.context import cbim_dir
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
    """Collapse text to a single line (replace newlines with the literal \\n)."""
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n")


def append(tag: str, message: str, cbim: Path | None = None, log_path: Path | None = None) -> None:
    """Append one timestamped line to the current session log.

    Creates an orphan session log on the fly if no session has started yet,
    so no messages are lost. Swallows all exceptions — logging must never
    crash the host process.
    """
    try:
        cbim = cbim or cbim_root_from_cwd() or _ctx_cbim_dir()
        path = log_path or current_log_path(cbim)
        if path is None:
            path = _create_session_file("orphan", os.getcwd(), cbim)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] [{tag}] {_escape(message)}\n"
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

def _create_session_file(session_id: str, cwd: str, cbim: Path) -> Path:
    """Create the log file and write the .current pointer. No tags written here."""
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    short = (session_id or "anon").replace("/", "_").replace("\\", "_")[:8]
    log_path = logs_dir(cbim) / f"session_{ts}_{short}.log"
    log_path.touch(exist_ok=True)
    _pointer_path(cbim).write_text(str(log_path), encoding="utf-8")
    return log_path


def start_session(session_id: str = "", cwd: str = "", cbim: Path | None = None) -> Path:
    """Open a new session log file and write the .current pointer.

    Returns the new log file path. No [SESSION] tag is written — the
    conversation flow ([USER] / [ASSIST]) already marks session boundaries.
    """
    cbim = cbim or cbim_root_from_cwd() or _ctx_cbim_dir()
    return _create_session_file(session_id, cwd, cbim)


def end_session(session_id: str = "", reason: str = "", cbim: Path | None = None) -> Path | None:
    """Clear the .current pointer to finalise the session log.

    Returns the finalised log path, or None if no active session.
    No [SESSION] tag is written — session end is implicit from [ASSIST] being
    the last entry before the next [USER] in a new file.
    """
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
# High-level write helpers — called by hooks
# ---------------------------------------------------------------------------

def log_user(prompt: str, cbim: Path | None = None) -> None:
    """Log the full user prompt [USER]."""
    text = (prompt or "").strip()
    if len(text) > _MAX_ENTRY_CHARS:
        text = text[:_MAX_ENTRY_CHARS] + "…"
    append("USER", text, cbim=cbim)


def log_cbim_call(tag: str, message: str, cbim: Path | None = None) -> None:
    """Log a CBIM-specific operation [CBIM:<domain>], [CBIM:skill], [CBIM:agent]."""
    append(tag, message, cbim=cbim)


def log_assist(transcript_path: str, cbim: Path | None = None) -> None:
    """Extract the last assistant text from the JSONL transcript and log [ASSIST]."""
    text = _last_assistant_text(transcript_path)
    if not text:
        return
    if len(text) > _MAX_ENTRY_CHARS:
        text = text[:_MAX_ENTRY_CHARS] + "…"
    append("ASSIST", text, cbim=cbim)


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
            # Handle both direct {role, content} and wrapped {message: {role, content}}
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
