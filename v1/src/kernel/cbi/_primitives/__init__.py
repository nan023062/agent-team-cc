"""cbi._primitives — knowledge-engine primitives (INTERNAL).

Internal primitives — external code MUST NOT import this package directly.
Use the resource object model in `cbi.resources` instead.

Layer in the strict dependency direction:
    engine/cli.py → cbi/resources/ → cbi/_primitives/{agents,modules} → services/_fm

This package exposes the low-level primitive functions (file-level reads,
writes, scaffolding, indexing). The resource object model in cbi/resources
wraps them with dirty-tracking and atomic-save semantics; new callers should
prefer the resource model. The primitive exports here remain for:
  - the resource layer itself (cbi/resources/* imports from here)
  - the deprecated `dna write-doc` / `dna write-section` CLI paths that need
    surgical frontmatter-preserving writes the object model intentionally
    does not duplicate
  - existing call sites in services/, hooks/, and skills/check.py that
    already use these names

New code should use:
    from ..resources import Agent, DNAModule, Skill, Workflow, Memory
"""

from .agents import (
    archive_agent,
    list_agents,
    load_agent,
    scaffold_agent,
)
from .modules import (
    init_module,
    list_modules,
    load_module,
    update_index,
    update_module_meta,
    write_module_doc,
    write_module_section,
)

__all__ = [
    # agents
    "list_agents", "load_agent", "scaffold_agent", "archive_agent",
    # modules
    "list_modules", "load_module", "init_module",
    "update_index", "update_module_meta",
    "write_module_doc", "write_module_section",
]
