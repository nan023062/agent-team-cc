"""Workflow framework CLI.

    python -m v1.tests.workflow.cli run [--project PATH] (--prompt PATH | --generator NAME) [--output PATH]
    python -m v1.tests.workflow.cli generate --project PATH --generator NAME
    python -m v1.tests.workflow.cli list-generators

Two target modes:
  * default                 — fresh CBIM install in a tempdir (idempotent, slow first run)
  * --project PATH          — an existing on-disk project (no install, no cleanup)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..framework import runner as _runner
from ..framework import reporter as _reporter
from ..framework.generators import get as _get_gen, list_all as _list_gen
from ..framework.generators.static import StaticPromptFile
from ..framework.target import ExternalProject, TmpProject


def _build_target(project_arg: str | None):
    if project_arg:
        return ExternalProject(Path(project_arg).resolve())
    return TmpProject()


def _resolve_prompt(args, target) -> str:
    if args.prompt:
        gen = StaticPromptFile(path=Path(args.prompt).resolve())
        return gen.generate(target)
    if args.generator:
        gen = _get_gen(args.generator)
        return gen.generate(target)
    sys.exit("error: provide --prompt <path> or --generator <name>")


def cmd_run(args) -> int:
    target = _build_target(args.project)
    prompt = _resolve_prompt(args, target)
    result = _runner.run(target, prompt, timeout=args.timeout)
    sys.stdout.write(_reporter.render_stdout(result) + "\n")
    if args.output:
        Path(args.output).write_text(
            _reporter.render_markdown_single(result), encoding="utf-8"
        )
        sys.stdout.write(f"wrote {args.output}\n")
    return 0 if result.exit_code == 0 else result.exit_code


def cmd_generate(args) -> int:
    target = _build_target(args.project)
    gen = _get_gen(args.generator)
    # If user picked the default static generator without --prompt, fail fast.
    if isinstance(gen, StaticPromptFile) and gen.path is None:
        sys.exit("error: `static` generator needs a path; use --prompt or pick another generator")
    sys.stdout.write(gen.generate(target))
    return 0


def cmd_list_generators(_args) -> int:
    for g in _list_gen():
        sys.stdout.write(f"  {g.name:<20} {g.description}\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m v1.tests.workflow.cli")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("run", help="Run a prompt against a project")
    pr.add_argument("--project", help="Path to existing project (default: fresh tmp install)")
    pr.add_argument("--prompt", help="Path to a prompt .md file")
    pr.add_argument("--generator", help="Generator name (alternative to --prompt)")
    pr.add_argument("--timeout", type=int, default=300, help="Per-run timeout in seconds")
    pr.add_argument("--output", help="Path to save a markdown report of this run")
    pr.set_defaults(func=cmd_run)

    pg = sub.add_parser("generate", help="Generate a prompt for a project (does not run claude)")
    pg.add_argument("--project", required=True, help="Path to an existing project")
    pg.add_argument("--generator", required=True, help="Generator name (see list-generators)")
    pg.set_defaults(func=cmd_generate)

    pl = sub.add_parser("list-generators", help="List registered prompt generators")
    pl.set_defaults(func=cmd_list_generators)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
