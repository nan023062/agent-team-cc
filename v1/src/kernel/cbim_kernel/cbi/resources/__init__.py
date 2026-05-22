"""
cbi/resources — Resource object model for kernel-managed artifacts.

Each resource (Agent, DNAModule, Skill, Workflow, Memory) is a thin,
dirty-tracking, atomic-saving wrapper around the engine primitives in
cbi/_primitives/* and memory/engine/*. CLI handlers are expected to load an
object, mutate it, and call .save() — they should not poke at the
underlying files directly.

Strict dependency direction:
    engine/cli.py → cbi/resources/ → cbi/_primitives/{agents,modules} + memory/engine
    cbi/resources/ MUST NOT import cli; cbi/_primitives MUST NOT import resources.
"""

from .agent import Agent, AgentFrontmatter, SkillCollection
from .dna_module import (
    DNAModule, ModuleFrontmatter, Contract, WorkflowCollection,
)
from .memory import Memory
from .skill import ReadOnlyError, Skill
from .workflow import Workflow

__all__ = [
    "Agent",
    "AgentFrontmatter",
    "SkillCollection",
    "DNAModule",
    "ModuleFrontmatter",
    "Contract",
    "WorkflowCollection",
    "Memory",
    "ReadOnlyError",
    "Skill",
    "Workflow",
]
