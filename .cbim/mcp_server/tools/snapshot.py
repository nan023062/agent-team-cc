"""
mcp_server/tools/snapshot.py — Project knowledge snapshot tool.
"""

from __future__ import annotations

from pathlib import Path


def register(mcp) -> None:
    @mcp.tool()
    def project_snapshot(cwd: str = "") -> str:
        """Generate the project knowledge snapshot: module tree, registered agents,
        recent activity. Equivalent to `python .cbim/engine snapshot`.

        Args:
            cwd: Project directory (default: current working dir of the MCP server).
        """
        from cbi.engine.snapshot import build_snapshot
        root = Path(cwd).resolve() if cwd else Path.cwd().resolve()
        return build_snapshot(root)
