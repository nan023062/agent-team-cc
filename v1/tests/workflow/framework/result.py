"""Result of a single claude run captured by the runner."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Result:
    target_root: Path
    prompt: str
    exit_code: int
    stdout: str
    stderr: str
    wall_time_s: float
    session_log_path: Path | None
    session_log: str
    started_at: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    arch_metrics: dict = field(default_factory=dict)
