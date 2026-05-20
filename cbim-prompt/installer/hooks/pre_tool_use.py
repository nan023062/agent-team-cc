#!/usr/bin/env python3
import sys, json
from pathlib import Path
from datetime import datetime

def _logs_dir() -> Path:
    # __file__ is .cbim-prompt/installer/hooks/pre_tool_use.py
    # parents[2] = .cbim-prompt/
    d = Path(__file__).resolve().parents[2] / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d

def _extract_param(tool_name: str, tool_input: dict) -> str:
    if tool_name in ("Read", "Write", "Edit"):
        return f"path={tool_input.get('file_path', '?')}"
    if tool_name == "Glob":
        return f"pattern={tool_input.get('pattern', '?')}"
    if tool_name == "Grep":
        return f"pattern={tool_input.get('pattern', '?')} path={tool_input.get('path', '')}"
    if tool_name == "Bash":
        cmd = tool_input.get("command", "?")[:200]
        return f"cmd={cmd}"
    return f"params={len(tool_input)} keys"

def _is_bypass(tool_name: str, tool_input: dict) -> bool:
    if tool_name not in ("Read", "Glob", "Grep", "Write", "Edit"):
        return False
    path = tool_input.get("file_path") or tool_input.get("path") or tool_input.get("pattern") or ""
    return ".cbim-prompt" in str(path)

def main():
    try:
        data = json.load(sys.stdin)
        tool_name = data.get("tool_name", "Unknown")
        tool_input = data.get("tool_input", {})
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        param = _extract_param(tool_name, tool_input)
        if _is_bypass(tool_name, tool_input):
            line = f"[TOL]{ts} [WARN]: tool={tool_name} | {param} | reason=bypass-engine\n"
        else:
            line = f"[TOL]{ts}: tool={tool_name} | {param}\n"
        (_logs_dir() / "tools.txt").open("a", encoding="utf-8").write(line)
    except Exception:
        pass

main()
sys.exit(0)
