"""
_body.py — Markdown body sub-object.

Wraps the section-splitting algorithm from cbi/_primitives/modules.py
(`_split_sections`, `_HEADING_RE`, `_FENCE_RE`) so resources can perform
H2/H3 surgical edits without depending on the CLI layer. The frontmatter
block is owned by the parent resource — Body deals with body text only.
"""

from __future__ import annotations

from .._primitives.modules import (
    _HEADING_RE,
    _FENCE_RE,
    _split_sections,
    _normalize_content_lines,
)


class Body:
    """Mutable markdown body with section-aware editing helpers."""

    def __init__(self, text: str = "", *, on_change=None):
        self._text = text
        self._on_change = on_change

    # ------------------------------------------------------------------
    # Whole-body access
    # ------------------------------------------------------------------

    def read(self) -> str:
        return self._text

    def write(self, content: str) -> None:
        if self._text == content:
            return
        self._text = content
        self._notify()

    # ------------------------------------------------------------------
    # Section queries
    # ------------------------------------------------------------------

    def list_sections(self) -> list[tuple[int, str]]:
        return [(s.level, s.heading) for s in _split_sections(self._text)]

    def has_section(self, heading: str, level: int = 2) -> bool:
        return any(
            s.level == level and s.heading == heading
            for s in _split_sections(self._text)
        )

    def get_section(self, heading: str, level: int = 2) -> str:
        """Return the section body (lines between the heading and the next
        sibling/parent heading). Raises LookupError when not found or
        ambiguous."""
        sections = _split_sections(self._text)
        matches = [s for s in sections if s.level == level and s.heading == heading]
        if not matches:
            raise LookupError(
                f"heading not found: '{heading}' at level {level}"
            )
        if len(matches) > 1:
            raise LookupError(
                f"ambiguous: {len(matches)} sections match '{heading}' at level {level}"
            )
        return "\n".join(matches[0].body_lines).strip("\n")

    # ------------------------------------------------------------------
    # Section edits — mirror cli.write_module_section semantics
    # ------------------------------------------------------------------

    _MODES = ("replace", "append", "insert-after", "delete")

    def write_section(
        self,
        heading: str,
        content: str | None,
        *,
        level: int = 2,
        mode: str = "replace",
        create_if_missing: bool = False,
    ) -> None:
        """Surgically edit a section of the body.

        See cli.write_module_section for the full semantics; this method is
        the in-memory equivalent (no filesystem touch, just mutates self._text
        and notifies on_change).
        """
        if mode not in self._MODES:
            raise ValueError(
                f"mode must be one of {self._MODES}, got: {mode!r}"
            )
        if level not in (2, 3):
            raise ValueError(f"level must be 2 or 3, got: {level!r}")
        if mode == "delete":
            if content is not None:
                raise ValueError("content is forbidden when mode='delete'")
        else:
            if content is None:
                raise ValueError(f"content is required when mode={mode!r}")

        body_lines = self._text.splitlines()
        sections = _split_sections(self._text)
        matches = [s for s in sections if s.level == level and s.heading == heading]

        if len(matches) > 1:
            raise LookupError(
                f"ambiguous: {len(matches)} sections match '{heading}' at level {level}"
            )

        if not matches:
            if mode == "delete":
                # No-op, silently.
                return
            if mode == "insert-after":
                raise LookupError(
                    f"heading not found: '{heading}' at level {level} "
                    f"(insert-after has no create-if-missing fallback)"
                )
            if not create_if_missing:
                raise LookupError(
                    f"heading not found: '{heading}' at level {level}"
                )
            content_lines = _normalize_content_lines(content or "")
            new_lines = list(body_lines)
            while new_lines and new_lines[-1].strip() == "":
                new_lines.pop()
            if new_lines:
                new_lines.append("")
            new_lines.append(f"{'#' * level} {heading}")
            new_lines.append("")
            new_lines.extend(content_lines)
        else:
            sec = matches[0]
            content_lines = (
                _normalize_content_lines(content) if content is not None else []
            )
            new_lines = list(body_lines)

            if mode == "replace":
                replacement = [""] + content_lines + [""]
                new_lines[sec.start + 1:sec.end] = replacement
            elif mode == "append":
                insertion: list[str] = []
                tail_blank = (sec.end - 1 >= sec.start + 1) and \
                    new_lines[sec.end - 1].strip() == ""
                if not tail_blank:
                    insertion.append("")
                insertion.extend(content_lines)
                insertion.append("")
                new_lines[sec.end:sec.end] = insertion
            elif mode == "insert-after":
                insertion = [""] + content_lines + [""]
                new_lines[sec.end:sec.end] = insertion
            elif mode == "delete":
                del new_lines[sec.start:sec.end]
                i = sec.start
                if 0 < i < len(new_lines):
                    if new_lines[i - 1].strip() == "" and new_lines[i].strip() == "":
                        del new_lines[i]

        while new_lines and new_lines[0].strip() == "":
            new_lines.pop(0)
        new_text = "\n".join(new_lines).rstrip() + "\n"
        if new_text != self._text:
            self._text = new_text
            self._notify()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _notify(self) -> None:
        if self._on_change is not None:
            self._on_change()


# Re-export the heading/fence regexes and section type at module level for
# any caller that wants raw access; this avoids a second import path.
__all__ = ["Body", "_HEADING_RE", "_FENCE_RE"]
