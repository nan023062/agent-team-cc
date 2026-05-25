"""hr_gov/safe_do.py — SafeDo deterministic leaf.

Executes the "safe" bucket of HR-governance findings. Currently the only
recognized safe action is filling a missing frontmatter field on an agent
(ScanBroken with bucket_hint=safe), wired through
`services.agent_service.update_agent`.

Behavior:
  - For `scan_broken` findings that carry both `field` and `value`,
    call `update_agent(name=<agent>, target="frontmatter",
                       payload={"field": ..., "value": ...}, cwd=None)`.
    The kernel write is idempotent on identical inputs.
  - For `scan_broken` findings without `field` / `value`, the scan
    currently only knows the agent is broken — degrade to advisory.
  - Non-broken safe findings degrade to advisory.
  - Per-finding error isolation: service exceptions land in
    `advice_pending`; the leaf still returns SUCCESS so the rest of the
    governance tick can proceed.
"""
from __future__ import annotations

from engine.core.node import Node, Status


class SafeDo(Node):
    def __init__(self, *, state: dict, name: str = "SafeDo") -> None:
        self.name = name
        self._state = state

    def tick(self, bb) -> Status:
        safe = (self._state.get("buckets") or {}).get("safe") or []
        applied: list[str] = []
        advice: list[str] = list(self._state.get("advice_pending") or [])

        for item in safe:
            kind = item.get("kind", "?")
            subject = item.get("subject", "?")
            detail = item.get("detail", "")

            if kind != "scan_broken":
                advice.append(
                    f"safe action on {subject!r}: no handler wired ({detail})"
                )
                continue

            field = item.get("field")
            value = item.get("value")
            if not field or value is None:
                advice.append(
                    f"agent_edit advisory on {subject!r}: "
                    f"missing field/value to补 ({detail})"
                )
                continue

            try:
                from services.agent_service import update_agent

                update_agent(
                    name=subject,
                    target="frontmatter",
                    payload={"field": field, "value": value},
                    cwd=None,
                )
            except Exception as exc:  # noqa: BLE001 — isolate every failure
                advice.append(
                    f"agent_edit failed on {subject!r} "
                    f"(field={field!r}): {type(exc).__name__}: {exc}"
                )
            else:
                applied.append(
                    f"agent_edit on {subject!r}: set frontmatter "
                    f"{field}={value!r} ({detail})"
                )

        self._state["safe_actions_applied"] = applied
        self._state["advice_pending"] = advice
        return Status.SUCCESS
