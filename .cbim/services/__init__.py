"""
services - shared CBIM service layer.

Stable, dependency-light functions that return structured Python data
(no HTTP, no MCP SDK, no formatting for LLM consumption). Both the
dashboard HTTP server and the MCP tool layer consume this package as
their single source of truth.

Dependency direction (single, hard rule):
    mcp_server.tools --> services <-- dashboard.server
The dashboard layer MUST NOT import from mcp_server; MCP tools MUST NOT
import from dashboard. If either direction shows up, the boundary is broken.
"""

from .memory_service import list_entries
from .agent_service import list_agents
from .knowledge_service import list_modules
from .log_service import read_log

__all__ = ["list_entries", "list_agents", "list_modules", "read_log"]
