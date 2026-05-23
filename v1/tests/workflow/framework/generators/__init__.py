"""Prompt generators — registry + Protocol.

A generator turns a TestTarget into a prompt string. The static generator
just reads a .md file. Future generators (Phase 14b A/B benchmark) can scan
the target for module shape, dependency rules, etc.

Registry is module-global; register() is idempotent on name conflict (later
wins) so test code can swap.
"""

from __future__ import annotations

from typing import Protocol

from ..target import TestTarget


class PromptGenerator(Protocol):
    name: str
    description: str

    def generate(self, target: TestTarget) -> str: ...


_GENERATORS: dict[str, PromptGenerator] = {}


def register(g: PromptGenerator) -> None:
    _GENERATORS[g.name] = g


def get(name: str) -> PromptGenerator:
    if name not in _GENERATORS:
        raise KeyError(f"no generator registered with name={name!r}; known: {list(_GENERATORS)}")
    return _GENERATORS[name]


def list_all() -> list[PromptGenerator]:
    return sorted(_GENERATORS.values(), key=lambda g: g.name)


# Eager-register the default static generator so `list-generators` always has
# at least one entry.
from . import static as _static  # noqa: E402,F401  (side-effect: register)
