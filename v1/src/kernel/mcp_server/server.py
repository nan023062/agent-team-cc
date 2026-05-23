"""
mcp_server/server.py — CBIM MCP server (FastMCP) + embedded scheduler.

Exposes core engine commands as MCP tools so the LLM can invoke them
through the standard Claude Code tool mechanism (rather than going through
`.cbim/run ...` Bash invocations). Also runs an async task scheduler in the
server's lifespan (Phase 2).

Run:
    .cbim/run mcp            # stdio transport (default)

Requires the `mcp` SDK (see kernel/requirements.txt):
    pip install -r kernel/requirements.txt

The directory is named `mcp_server` (not `mcp`) to avoid colliding with
the SDK's top-level `mcp` package on sys.path.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print(
        "ERROR: The `mcp` SDK is not installed.\n"
        "Install it with: pip install -r kernel/requirements.txt",
        file=sys.stderr,
    )
    sys.exit(1)

from context import cbim_dir
from .scheduler import Scheduler
from ._logging import patch_tool_logging


def _server_log(msg: str) -> None:
    try:
        from engine.session_log import append
        append("MCP", msg)
    except Exception:
        pass


def _uds_sock_path(project_root: Path) -> Path:
    """Mirror of hooks_src/_lib/paths.mcp_sock_path — kept in sync by contract.

    `~/.cache/cbim/<sha256(abs_project_root)[:12]>/mcp.sock`, honouring
    `XDG_CACHE_HOME` when set.
    """
    abs_str = str(Path(project_root).resolve())
    h = hashlib.sha256(abs_str.encode("utf-8")).hexdigest()[:12]
    cache_home = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(cache_home) / "cbim" / h / "mcp.sock"


async def _uds_dispatch(mcp_inst: "FastMCP", tool_name: str, args: dict):
    """Look up a registered tool by name and invoke it with `args`."""
    tool = mcp_inst._tool_manager.get_tool(tool_name)
    if tool is None:
        raise KeyError(f"unknown tool: {tool_name}")
    fn = tool.fn
    if tool.is_async or inspect.iscoroutinefunction(fn):
        return await fn(**(args or {}))
    return await asyncio.to_thread(fn, **(args or {}))


def _make_uds_handler(mcp_inst: "FastMCP"):
    async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while True:
                line = await reader.readline()
                if not line:
                    return
                try:
                    req = json.loads(line.decode("utf-8"))
                    tool_name = req["tool"]
                    args = req.get("args") or {}
                    result = await _uds_dispatch(mcp_inst, tool_name, args)
                    resp = {"ok": True, "result": result if isinstance(result, dict) else {"result": result}}
                except Exception as e:
                    resp = {"ok": False, "error": f"{type(e).__name__}: {e}"}
                try:
                    writer.write((json.dumps(resp, ensure_ascii=False) + "\n").encode("utf-8"))
                    await writer.drain()
                except (ConnectionError, OSError):
                    return
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
    return _handle


async def _start_uds_listener(mcp_inst: "FastMCP", project_root: Path) -> tuple[asyncio.base_events.Server, Path]:
    sock_path = _uds_sock_path(project_root)
    sock_dir = sock_path.parent
    sock_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(sock_dir, 0o700)
    except OSError:
        pass
    if sock_path.exists() or sock_path.is_symlink():
        try:
            sock_path.unlink()
        except OSError:
            pass
    server = await asyncio.start_unix_server(_make_uds_handler(mcp_inst), path=str(sock_path))
    try:
        os.chmod(sock_path, 0o600)
    except OSError:
        pass
    _server_log(f"UDS listener bound at {sock_path}")
    return server, sock_path


@asynccontextmanager
async def _lifespan(server):
    """Spin up the scheduler + UDS listener at start; clean both up on exit."""
    _server_log("server starting")
    scheduler = Scheduler(cbim_root=cbim_dir())
    # Inject into the scheduler-tools module so its MCP tools can use it.
    from .tools import scheduler as _sched_tool
    _sched_tool.set_scheduler(scheduler)
    scheduler.start()

    project_root = Path(cbim_dir()).parent
    try:
        uds_server, sock_path = await _start_uds_listener(mcp, project_root)
    except Exception as e:
        _server_log(f"UDS listener failed to bind: {e}")
        uds_server, sock_path = None, None

    try:
        yield {"scheduler": scheduler}
    finally:
        if uds_server is not None:
            uds_server.close()
            try:
                await uds_server.wait_closed()
            except Exception:
                pass
        if sock_path is not None:
            try:
                Path(sock_path).unlink(missing_ok=True)
            except OSError:
                pass
        await scheduler.stop()
        _server_log("server stopped")


mcp = FastMCP("cbim", lifespan=_lifespan)

# MUST patch BEFORE tool modules are imported — they decorate at import time.
patch_tool_logging(mcp)

# Import & register tool modules
from .tools import memory as _memory       # noqa: E402
from .tools import dna as _dna             # noqa: E402
from .tools import agent as _agent         # noqa: E402
from .tools import skill as _skill         # noqa: E402
from .tools import snapshot as _snap       # noqa: E402
from .tools import scheduler as _sched_t   # noqa: E402
from .tools import hook as _hook           # noqa: E402

_memory.register(mcp)
_dna.register(mcp)
_agent.register(mcp)
_skill.register(mcp)
_snap.register(mcp)
_sched_t.register(mcp)
_hook.register(mcp)


if __name__ == "__main__":
    mcp.run()  # stdio transport
