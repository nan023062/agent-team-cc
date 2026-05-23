#!/usr/bin/env python3
"""SessionStart phase 2 - ensure dashboard server is running."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _lib.event_io import read_event
from _lib.paths import project_root_from_cwd, mcp_sock_path
from _lib.mcp_client import McpClient


def main() -> int:
    event = read_event()
    cwd = event.get("cwd") or "."
    root = project_root_from_cwd(cwd)
    sock = mcp_sock_path(root)

    client = McpClient(sock)
    try:
        client.call("dashboard_ensure_running", {"cwd": cwd})
    finally:
        client.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
