#!/usr/bin/env python3
"""UserPromptSubmit hook - thin MCP client."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _lib.event_io import read_event
from _lib.paths import project_root_from_cwd, mcp_sock_path
from _lib.mcp_client import McpClient


def main() -> int:
    event = read_event()
    cwd = event.get("cwd") or "."
    prompt = event.get("prompt", "") or ""
    transcript_path = event.get("transcript_path", "") or ""
    root = project_root_from_cwd(cwd)
    sock = mcp_sock_path(root)

    client = McpClient(sock)
    try:
        client.call("cc_status_set", {"state": "busy", "cwd": cwd})
        client.call(
            "session_log_append",
            {
                "kind": "user",
                "payload": {"prompt": prompt},
                "transcript_path": transcript_path,
                "cwd": cwd,
            },
        )
    finally:
        client.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
