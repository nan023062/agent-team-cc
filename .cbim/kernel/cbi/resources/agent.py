"""
agent.py — Agent resource.

Agents live at <project>/.claude/agents/<name>/<name>.md with an optional
sibling `skills/` directory holding per-agent skill markdown files. The
class is a thin wrapper around the engine primitives in cbi/_primitives/agents.py
plus the shared frontmatter/body sub-objects.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from ._base import Resource
from ._body import Body
from ._frontmatter import Frontmatter
from ._io import atomic_write_text
from .skill import Skill
from .._primitives import agents as _agents_eng
from services._fm import parse_frontmatter, strip_frontmatter


class AgentFrontmatter(Frontmatter):
    _SCHEMA = ("name", "description", "model", "tools")


class SkillCollection:
    """Lazy view over <agent_dir>/skills/*.md."""

    def __init__(self, agent_dir: Path):
        self._dir = agent_dir / "skills"

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def list(self) -> list[str]:
        if not self._dir.exists():
            return []
        return sorted(f.stem for f in self._dir.glob("*.md"))

    def get(self, name: str) -> Skill:
        path = self._dir / f"{name}.md"
        return Skill.load(path)

    def __contains__(self, name: str) -> bool:
        return (self._dir / f"{name}.md").is_file()

    def __iter__(self) -> Iterator[Skill]:
        for stem in self.list():
            yield Skill.load(self._dir / f"{stem}.md")

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def add(self, name: str, content: str) -> Skill:
        self._dir.mkdir(parents=True, exist_ok=True)
        return Skill.create(self._dir / f"{name}.md", content=content)

    def remove(self, name: str) -> None:
        path = self._dir / f"{name}.md"
        if path.is_file():
            path.unlink()


class Agent(Resource):
    """A single agent: its frontmatter, body, and skill catalog."""

    def __init__(
        self,
        agent_dir: Path,
        *,
        frontmatter: AgentFrontmatter,
        body: Body,
    ):
        self._agent_dir = agent_dir.resolve()
        self._path = (self._agent_dir / f"{self._agent_dir.name}.md").resolve()
        self._id = self._agent_dir.name
        self._dirty = False
        self.frontmatter = frontmatter
        self.body = body
        self.skills = SkillCollection(self._agent_dir)
        frontmatter._on_change = self._mark_dirty
        body._on_change = self._mark_dirty

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _agents_dir(root: Path | None) -> Path:
        if root is None:
            from context import project_root
            root = project_root()
        return root / ".claude" / "agents"

    # ------------------------------------------------------------------
    # Classmethods
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, name: str, *, root: Path | None = None) -> "Agent":
        agents_dir = cls._agents_dir(root)
        agent_dir = agents_dir / name
        md = agent_dir / f"{name}.md"
        if not md.is_file():
            raise FileNotFoundError(f"agent not found: {name} ({md})")
        raw = md.read_text(encoding="utf-8")
        return cls(
            agent_dir,
            frontmatter=AgentFrontmatter(parse_frontmatter(raw)),
            body=Body(strip_frontmatter(raw)),
        )

    @classmethod
    def create(
        cls,
        name: str,
        *,
        description: str = "",
        model: str = "claude-sonnet-4-6",
        tools: str = "Read, Write, Edit, Glob, Grep, Bash",
        root: Path | None = None,
    ) -> "Agent":
        agents_dir = cls._agents_dir(root)
        # Reuse the engine primitive for scaffolding (creates dir, skills/,
        # and the .md file with a templated body).
        _agents_eng.scaffold_agent(agents_dir, name, description, model)
        agent = cls.load(name, root=root)
        # If caller asked for a non-default tools string, persist it.
        if tools != "Read, Write, Edit, Glob, Grep, Bash":
            agent.frontmatter.set("tools", tools)
            agent.save()
        return agent

    @classmethod
    def exists(cls, name: str, *, root: Path | None = None) -> bool:
        return (cls._agents_dir(root) / name / f"{name}.md").is_file()

    @classmethod
    def list_all(cls, *, root: Path | None = None) -> list["Agent"]:
        agents_dir = cls._agents_dir(root)
        if not agents_dir.exists():
            return []
        out: list[Agent] = []
        for d in sorted(agents_dir.iterdir()):
            if not d.is_dir():
                continue
            md = d / f"{d.name}.md"
            if not md.is_file():
                continue
            try:
                out.append(cls.load(d.name, root=root))
            except FileNotFoundError:
                continue
        return out

    # ------------------------------------------------------------------
    # Save / Archive
    # ------------------------------------------------------------------

    def save(self) -> None:
        fm = self.frontmatter.render()
        body = self.body.read()
        # Body in the on-disk file conventionally starts after one blank line.
        if body and not body.startswith("\n"):
            text = fm + "\n" + body
        else:
            text = fm + body
        if not text.endswith("\n"):
            text += "\n"
        atomic_write_text(self._path, text)
        self._mark_clean()

    def archive(self) -> Path:
        return _agents_eng.archive_agent(self._agent_dir)

    def delete(self, *, force: bool = False) -> None:
        if not force:
            raise RuntimeError(
                "Agent.delete removes the entire agent directory; pass force=True"
            )
        import shutil
        shutil.rmtree(self._agent_dir)
