"""
.cbim/mcp_server/server.py — CBIM MCP server (FastMCP) + embedded scheduler.

Exposes core engine commands as MCP tools so the LLM can invoke them
through the standard Claude Code tool mechanism (rather than going through
`python .cbim/engine ...` Bash invocations). Also runs an async task
scheduler in the server's lifespan (Phase 2).

Run:
    python .cbim/mcp_server/server.py            # stdio transport (default)

Register in .claude/settings.json:
    "mcpServers": {
      "cbim": { "command": "python", "args": [".cbim/mcp_server/server.py"] }
    }

Requires the `mcp` SDK (see .cbim/mcp_server/requirements.txt):
    pip install -r .cbim/mcp_server/requirements.txt

The directory is named `mcp_server` (not `mcp`) to avoid colliding with
the SDK's top-level `mcp` package on sys.path.
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Add .cbim/ to sys.path so engine / memory / cbi / mcp_server packages import cleanly.
_CBIM = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_CBIM))

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print(
        "ERROR: The `mcp` SDK is not installed.\n"
        "Install it with: pip install -r .cbim/mcp_server/requirements.txt",
        file=sys.stderr,
    )
    sys.exit(1)

from mcp_server.scheduler import Scheduler
from mcp_server._logging import patch_tool_logging


def _server_log(msg: str) -> None:
    try:
        from engine.session_log import append
        append("MCP", msg)
    except Exception:
        pass


@asynccontextmanager
async def _lifespan(server):
    """Spin up the scheduler at server start; stop it cleanly on exit."""
    _server_log("server starting")
    scheduler = Scheduler(cbim_root=_CBIM)
    # Inject into the scheduler-tools module so its MCP tools can use it.
    from mcp_server.tools import scheduler as _sched_tool
    _sched_tool.set_scheduler(scheduler)
    scheduler.start()
    try:
        yield {"scheduler": scheduler}
    finally:
        await scheduler.stop()
        _server_log("server stopped")


mcp = FastMCP("cbim", lifespan=_lifespan)

# MUST patch BEFORE tool modules are imported — they decorate at import time.
patch_tool_logging(mcp)

# Import & register tool modules
from mcp_server.tools import memory as _memory       # noqa: E402
from mcp_server.tools import dna as _dna             # noqa: E402
from mcp_server.tools import agent as _agent         # noqa: E402
from mcp_server.tools import skill as _skill         # noqa: E402
from mcp_server.tools import snapshot as _snap       # noqa: E402
from mcp_server.tools import scheduler as _sched_t   # noqa: E402

_memory.register(mcp)
_dna.register(mcp)
_agent.register(mcp)
_skill.register(mcp)
_snap.register(mcp)
_sched_t.register(mcp)


if __name__ == "__main__":
    mcp.run()  # stdio transport
