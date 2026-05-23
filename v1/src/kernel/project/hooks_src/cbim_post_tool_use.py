#!/usr/bin/env python3
"""PostToolUse hook - thin MCP client."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _lib.event_io import read_event
from _lib.paths import project_root_from_cwd, mcp_sock_path
from _lib.mcp_client import McpClient


def main() -> int:
    event = read_event()
    cwd = event.get("cwd") or "."
    tool = event.get("tool_name", "?") or "?"
    tool_input = event.get("tool_input", {}) or {}
    tool_response = event.get("tool_response", {}) or {}
    transcript_path = event.get("transcript_path", "") or ""
    root = project_root_from_cwd(cwd)
    sock = mcp_sock_path(root)

    client = McpClient(sock)
    try:
        client.call(
            "tool_call_log",
            {
                "phase": "post",
                "tool": tool,
                "tool_input": tool_input,
                "tool_response": tool_response,
                "transcript_path": transcript_path,
                "cwd": cwd,
            },
        )
    finally:
        client.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
