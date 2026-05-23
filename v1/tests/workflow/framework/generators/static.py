"""Static prompt generator — reads a .md file. Default for the CLI `run` path."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..target import TestTarget


@dataclass
class StaticPromptFile:
    """Returns the contents of a .md file. Path is mutable so the CLI can
    set it after construction (the registry stores a single shared instance)."""

    name: str = "static"
    path: Path | None = None
    description: str = "Read prompt from a .md file (set via CLI `--prompt`)."

    def generate(self, target: TestTarget) -> str:
        if self.path is None:
            raise ValueError(
                "StaticPromptFile.path is unset; use --prompt to point at a .md file"
            )
        return Path(self.path).read_text(encoding="utf-8")


_default = StaticPromptFile()

from . import register  # noqa: E402  (avoid circular import at module top)

register(_default)
