"""checks/_agent_skill_parser.py — fragile skill-count heuristic for agents.

Two strategies tried in order:
  1. Look for a `## Skills` heading; count pipe-delimited markdown table rows
     under it (skip header + separator).
  2. Fallback: count occurrences of `cbim skill show <agent>.` markers in the
     body.

This is intentionally heuristic — agent body conventions are still drifting.
Lifted into its own file so future structural skill metadata can swap it out.
"""

from __future__ import annotations

import re

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_TABLE_ROW_RE = re.compile(r"^\s*\|.+\|\s*$")
_SEPARATOR_RE = re.compile(r"^\s*\|\s*:?-{3,}.*\|\s*$")


def count_skills(body: str, agent_id: str) -> int:
    table_count = _count_from_skills_table(body)
    if table_count > 0:
        return table_count
    grep_pattern = re.compile(
        rf"cbim\s+skill\s+show\s+{re.escape(agent_id)}\.[A-Za-z0-9_.\-]+"
    )
    return len(grep_pattern.findall(body))


def _count_from_skills_table(body: str) -> int:
    lines = body.splitlines()
    in_section = False
    section_level = 0
    rows = 0
    saw_separator = False
    for line in lines:
        m = _HEADING_RE.match(line)
        if m:
            heading_text = m.group(2).strip().lower()
            level = len(m.group(1))
            if in_section and level <= section_level:
                break
            if heading_text == "skills":
                in_section = True
                section_level = level
                rows = 0
                saw_separator = False
            continue
        if not in_section:
            continue
        if _SEPARATOR_RE.match(line):
            saw_separator = True
            continue
        if _TABLE_ROW_RE.match(line):
            if saw_separator:
                rows += 1
    return rows
