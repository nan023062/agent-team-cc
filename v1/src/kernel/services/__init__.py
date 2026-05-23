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

from .memory_service import (
    list_entries,
    reindex as memory_reindex,
    cleanup as memory_cleanup,
)
from .agent_service import (
    list_agents,
    scaffold_agent,
    update_agent,
    add_skill_to_agent,
    archive_agent,
)
from .knowledge_service import (
    list_modules,
    init_module,
    edit_module,
    split_module,
    write_doc,
    write_section,
)
from .log_service import read_log

__all__ = [
    "list_entries",
    "list_agents",
    "list_modules",
    "read_log",
    # writes
    "scaffold_agent",
    "update_agent",
    "add_skill_to_agent",
    "archive_agent",
    "init_module",
    "edit_module",
    "split_module",
    "write_doc",
    "write_section",
    "memory_reindex",
    "memory_cleanup",
]
