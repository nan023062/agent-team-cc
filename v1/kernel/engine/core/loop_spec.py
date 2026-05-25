"""loops/_spec.py — NodeSpec descriptor for agent-side sub-loops.

Agent-side sub-loops (architect_*, hr_*) do NOT run as Python BT trees —
they execute inside the LLM agent's mind. We describe their topology as
flat NodeSpec lists so:

  - the design-doc Mermaid labels are checked in (single source of truth);
  - compose_prompt() can render the list into a prompt the agent follows;
  - test_loops_topology.py can assert label sets without spinning up an LLM.

The `id` field is a short ASCII handle used by the parser to route response
fields; the `label` field is the Mermaid label (Chinese) shown to the agent
and asserted in topology tests; the `role` field separates action / decision
/ terminal nodes for prompt formatting.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NodeSpec:
    id: str        # short ASCII id, used as dict key in parse_response output
    label: str     # Mermaid label from the design doc (Chinese)
    role: str      # "action" | "decision" | "terminal"

    def __post_init__(self) -> None:
        if self.role not in ("action", "decision", "terminal"):
            raise ValueError(
                f"NodeSpec.role must be action|decision|terminal, got {self.role!r}"
            )
