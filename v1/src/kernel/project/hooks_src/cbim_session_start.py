#!/usr/bin/env python3
"""SessionStart hook - thin MCP client."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _lib.event_io import read_event, write_additional_context
from _lib.paths import project_root_from_cwd, mcp_sock_path
from _lib.mcp_client import McpClient


def main() -> int:
    event = read_event()
    cwd = event.get("cwd") or "."
    session_id = event.get("session_id", "") or ""
    root = project_root_from_cwd(cwd)
    sock = mcp_sock_path(root)

    client = McpClient(sock)
    try:
        result = client.call(
            "snapshot_for_session_start",
            {"session_id": session_id, "cwd": cwd},
        )
    finally:
        client.close()

    if result is None:
        return 0

    text = result.get("additionalContext", "") or ""
    if text:
        write_additional_context(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
