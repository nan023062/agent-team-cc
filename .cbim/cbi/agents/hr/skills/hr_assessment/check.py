"""
check.py — Deterministic HR agent assessment checks.

Scriptable factors: #1 #3 #3b(skill content) #7
Remaining factors require LLM analysis (see skill.py).

Usage:
  python .cbim/cbi/skills/hr_assessment/check.py [--root <path>] [--json]
Exit code: 0 = all MUST pass, 1 = MUST issues found.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
from cbi.engine.agents import list_agents
from cbi.skills.hr_assessment.config import CONFIG as _cfg

SKILLS_VOLUME_THRESHOLD      = _cfg["skills_volume_threshold"]
SKILL_MIN_REAL_LINES         = _cfg["skill_placeholder_min_real_lines"]

_REQUIRED_FRONTMATTER = {"name", "description", "model", "tools"}
_SKILL_PATH_RE = re.compile(r"`([^`]+SKILL\.md)`")


def run_checks(root: Path) -> dict[str, list[str]]:
    agents_dir = root / ".claude" / "agents"
    agents = list_agents(agents_dir)
    issues: dict[str, list[str]] = {"MUST": [], "SUGGEST": []}

    for a in agents:
        aid = a["id"]

        # #1 — frontmatter completeness
        missing = [f for f in _REQUIRED_FRONTMATTER if not a.get(f)]
        if missing:
            issues["MUST"].append(
                f"[#1] {aid}: frontmatter missing fields: {', '.join(sorted(missing))}"
            )

        # #3 — skill paths valid + content not placeholder
        body = a.get("body", "")
        for match in _SKILL_PATH_RE.finditer(body):
            skill_path = match.group(1)
            full = root / skill_path
            if not full.exists():
                issues["MUST"].append(f"[#3] {aid}: skill path not found: {skill_path}")
                continue
            # #3b — skill content not placeholder
            try:
                skill_content = full.read_text(encoding="utf-8")
                real_lines = [l for l in skill_content.splitlines()
                              if l.strip() and not l.strip().startswith("#")]
                if len(real_lines) < SKILL_MIN_REAL_LINES:
                    issues["MUST"].append(
                        f"[#3] {aid}: {skill_path} has no real content (placeholder)"
                    )
            except (FileNotFoundError, PermissionError):
                pass

        # #7 — skills count
        skill_count = len(a.get("skills", []))
        if skill_count >= SKILLS_VOLUME_THRESHOLD:
            issues["SUGGEST"].append(
                f"[#7] {aid}: has {skill_count} skills (≥{SKILLS_VOLUME_THRESHOLD})"
                " — consider splitting into more focused agents"
            )

    return issues


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deterministic HR agent assessment checks (#1 #3 #7)"
    )
    parser.add_argument("--root", default=".", help="Project root directory (default: .)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    issues = run_checks(root)

    must = issues["MUST"]
    suggest = issues["SUGGEST"]

    if args.json:
        print(json.dumps(issues, ensure_ascii=False, indent=2))
    else:
        print(f"HR Agent 脚本检查 — {root.name}")
        print(f"MUST: {len(must)}  SUGGEST: {len(suggest)}\n")
        if must:
            print("── MUST（必须修复）─────────────────────────────")
            for item in must:
                print(f"  {item}")
        if suggest:
            print("\n── SUGGEST（建议改进）──────────────────────────")
            for item in suggest:
                print(f"  {item}")
        if not must and not suggest:
            print("  ✓ 所有脚本检查通过")

    sys.exit(1 if must else 0)


if __name__ == "__main__":
    main()
