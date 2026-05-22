"""
_frontmatter.py — YAML frontmatter sub-object for resource files.

Wraps the permissive parse_frontmatter helper from services/_fm.py with
a mutable, dirty-tracking API. Rendering preserves a stable field order
(schema first, then any extras in insertion order) and emits lists in
block style — matching the format produced by modules._build_module_md.
"""

from __future__ import annotations

from typing import Any, Iterable

from cbim_kernel.services._fm import parse_frontmatter


class Frontmatter:
    """Mutable view over a single YAML frontmatter block.

    Edits flip the owning resource's dirty flag via the optional `_on_change`
    callback; render() produces the `---\\n...\\n---\\n` block ready to prepend
    to a body.
    """

    # Subclasses override _SCHEMA to fix field ordering for known keys.
    _SCHEMA: tuple[str, ...] = ()

    def __init__(self, data: dict | None = None, *, on_change=None):
        self._data: dict = dict(data) if data else {}
        self._on_change = on_change

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def parse(cls, text: str, *, on_change=None) -> "Frontmatter":
        """Build from a raw markdown string (frontmatter + body or body alone)."""
        return cls(parse_frontmatter(text), on_change=on_change)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get(self, field: str, default: Any = None) -> Any:
        return self._data.get(field, default)

    def has(self, field: str) -> bool:
        return field in self._data

    def to_dict(self) -> dict:
        return dict(self._data)

    # ------------------------------------------------------------------
    # Write — all mutations notify on_change
    # ------------------------------------------------------------------

    def set(self, field: str, value: Any) -> None:
        if self._data.get(field) == value and field in self._data:
            return
        self._data[field] = value
        self._notify()

    def update(self, **fields: Any) -> None:
        changed = False
        for k, v in fields.items():
            if v is None:
                continue
            if self._data.get(k) != v or k not in self._data:
                self._data[k] = v
                changed = True
        if changed:
            self._notify()

    def delete(self, field: str) -> None:
        if field in self._data:
            del self._data[field]
            self._notify()

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def render(self) -> str:
        """Render as `---\\n...\\n---\\n` block.

        Field order: schema fields first (in declared order, only if present),
        then any remaining fields in insertion order. Lists render block-style
        when populated, `[]` when empty.
        """
        if not self._data:
            return "---\n---\n"
        lines: list[str] = ["---"]
        emitted: set[str] = set()
        for key in self._SCHEMA:
            if key in self._data:
                lines.extend(self._render_field(key, self._data[key]))
                emitted.add(key)
        for key, val in self._data.items():
            if key in emitted:
                continue
            lines.extend(self._render_field(key, val))
        lines.append("---")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _render_field(key: str, val: Any) -> Iterable[str]:
        if isinstance(val, list):
            if val:
                out = [f"{key}:"]
                for item in val:
                    out.append(f"  - {item}")
                return out
            return [f"{key}: []"]
        return [f"{key}: {val}"]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _notify(self) -> None:
        if self._on_change is not None:
            self._on_change()
