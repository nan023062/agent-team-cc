"""
skill.py — Skill resource.

A skill is a single markdown file (optionally with frontmatter) living under
an agent's `skills/` directory, or anywhere else a skill catalog references.

Built-in skills are a second flavour: they ship as Python string constants
(`SKILL`) inside `cbim_kernel.cbi.agents.<agent>.skills.<name>.skill` and
`cbim_kernel.cbi.skills.<name>.skill`. `list_builtin` / `load_builtin`
discover and wrap them as read-only Skill objects.
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

from ._base import Resource
from ._body import Body
from ._frontmatter import Frontmatter
from ._io import atomic_write_text
from cbim_kernel.services._fm import strip_frontmatter


class ReadOnlyError(RuntimeError):
    """Raised when save() is called on a read-only Skill (e.g. built-in)."""


class Skill(Resource):

    def __init__(
        self,
        path: Path,
        *,
        frontmatter: Frontmatter,
        body: Body,
        read_only: bool = False,
    ):
        self._path = path.resolve() if path.exists() else path
        self._id = path.stem
        self._dirty = False
        self._read_only = read_only
        self.frontmatter = frontmatter
        self.body = body
        # Wire dirty propagation now that the resource exists.
        frontmatter._on_change = self._mark_dirty
        body._on_change = self._mark_dirty

    # ------------------------------------------------------------------
    # Classmethods
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: Path | str, *, root: Path | None = None) -> "Skill":
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"skill not found: {p}")
        raw = p.read_text(encoding="utf-8")
        return cls(
            p,
            frontmatter=Frontmatter.parse(raw),
            body=Body(strip_frontmatter(raw)),
        )

    @classmethod
    def create(cls, path: Path | str, *, content: str = "", **kwargs) -> "Skill":
        p = Path(path)
        if p.exists():
            raise FileExistsError(f"skill already exists: {p}")
        p.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(p, content)
        return cls.load(p)

    @classmethod
    def exists(cls, path: Path | str, *, root: Path | None = None) -> bool:
        return Path(path).is_file()

    # ------------------------------------------------------------------
    # Built-in skill discovery
    # ------------------------------------------------------------------

    @classmethod
    def _discover_builtin(
        cls,
        *,
        agent: str | None = None,
        trigger: str | None = None,
    ) -> dict[str, str]:
        """Walk cbim_kernel.cbi.agents.<agent>.skills.* and (when agent is
        None) cbim_kernel.cbi.skills.*. Returns {key: SKILL_string}.

        Keys are '<agent>.<skill_name>' for agent-scoped skills and
        '<skill_name>' for top-level coordinator skills.
        """
        # Local import to defer log_import dependency until actually needed.
        try:
            from cbim_kernel.engine.import_log import log_import
        except ImportError:
            def log_import(*a, **kw): pass

        skills: dict[str, str] = {}

        try:
            import cbim_kernel.cbi.agents as agents_pkg
        except ImportError:
            agents_pkg = None

        if agents_pkg is not None:
            for agent_info in pkgutil.iter_modules(agents_pkg.__path__):
                if agent is not None and agent_info.name != agent:
                    continue
                try:
                    agent_skills_pkg = importlib.import_module(
                        f"{agents_pkg.__name__}.{agent_info.name}.skills"
                    )
                except ModuleNotFoundError:
                    continue
                for skill_info in pkgutil.iter_modules(agent_skills_pkg.__path__):
                    module_path = (
                        f"{agent_skills_pkg.__name__}.{skill_info.name}.skill"
                    )
                    try:
                        mod = importlib.import_module(module_path)
                        if trigger is not None:
                            log_import(module_path, "ok", trigger)
                        if hasattr(mod, "SKILL"):
                            key = f"{agent_info.name}.{skill_info.name}"
                            skills[key] = mod.SKILL
                    except ModuleNotFoundError:
                        if trigger is not None:
                            log_import(module_path, "miss", trigger)

        # Top-level coordinator skills only when no agent filter is set.
        if agent is None:
            try:
                import cbim_kernel.cbi.skills as coord_skills_pkg
                for skill_info in pkgutil.iter_modules(coord_skills_pkg.__path__):
                    module_path = (
                        f"{coord_skills_pkg.__name__}.{skill_info.name}.skill"
                    )
                    try:
                        mod = importlib.import_module(module_path)
                        if trigger is not None:
                            log_import(module_path, "ok", trigger)
                        if hasattr(mod, "SKILL"):
                            skills[skill_info.name] = mod.SKILL
                    except ModuleNotFoundError:
                        if trigger is not None:
                            log_import(module_path, "miss", trigger)
            except ModuleNotFoundError:
                pass

        return skills

    @classmethod
    def list_builtin(
        cls,
        *,
        agent: str | None = None,
        trigger: str | None = None,
    ) -> list[str]:
        """List all built-in skill keys.

        When `agent` is None, returns every key (agent-scoped like
        'architect.arch_modules' plus top-level coordinator skills like
        'memory_write'). When `agent` is set, only that agent's keys are
        returned. `trigger`, when given, is forwarded to import_log so
        the discovery walk shows up in the structured import log.
        """
        return sorted(cls._discover_builtin(agent=agent, trigger=trigger).keys())

    @classmethod
    def load_builtin(cls, key: str, *, trigger: str | None = None) -> "Skill":
        """Load a built-in skill by key as a read-only Skill object.

        Accepted key formats:
            '<agent>.<skill_name>'  — agent-scoped skill
            '<skill_name>'          — top-level coordinator skill

        The returned object's body holds the SKILL markdown; calling save()
        raises ReadOnlyError because built-ins are shipped in code, not on
        disk.
        """
        effective_trigger = trigger if trigger is not None else "skill.load_builtin"
        agent_filter: str | None = None
        if "." in key:
            agent_filter = key.split(".", 1)[0]
        skills = cls._discover_builtin(agent=agent_filter, trigger=effective_trigger)
        if key not in skills:
            # Fall back to full scan in case the key shape is unusual.
            skills = cls._discover_builtin(trigger=effective_trigger)
            if key not in skills:
                raise FileNotFoundError(f"built-in skill not found: {key}")
        raw = skills[key]
        # Virtual path: <key>.md, never created on disk.
        virtual_path = Path(f"<builtin>/{key}.md")
        # Built-in SKILL constants are plain markdown bodies (no frontmatter
        # in practice). Preserve the raw string verbatim so CLI output is
        # byte-identical to the legacy `_load_skills` path.
        return cls(
            virtual_path,
            frontmatter=Frontmatter.parse(raw),
            body=Body(raw),
            read_only=True,
        )

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save(self) -> None:
        if self._read_only:
            raise ReadOnlyError(
                f"skill is read-only (built-in): {self._id}"
            )
        fm = self.frontmatter.render() if self.frontmatter.to_dict() else ""
        body = self.body.read()
        if fm:
            text = fm + "\n" + body if not body.startswith("\n") else fm + body
        else:
            text = body
        if not text.endswith("\n"):
            text += "\n"
        atomic_write_text(self._path, text)
        self._mark_clean()
