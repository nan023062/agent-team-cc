"""
check.py — Deterministic architecture governance checks.

Scriptable factors: #1 #2 #3 #4 #10 #14 #15 #17 #19 #20 #21 #WF1 #WF2
Remaining factors require LLM analysis (see SKILL.md).

Supports dual format:
  - New: .dna/module.md (YAML frontmatter + markdown body)
  - Legacy: .dna/module.json + .dna/architecture.md (deprecated)

Usage:
  python cbim/knowledge/skills/arch-governance/check.py [--root <path>] [--json]
Exit code: 0 = all MUST pass, 1 = MUST issues found.
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
from knowledge.engine.modules import (
    list_modules, read_index, _SCAN_SKIP_DIRS, _scan_modules,
)

_CONFIG_FILE = Path(__file__).resolve().parent / "config.json"
_cfg = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
PLACEHOLDER_MIN_REAL_LINES   = _cfg["placeholder_min_real_lines"]
LEAF_ARCH_MAX_LINES          = _cfg["leaf_arch_max_lines"]
LEAF_WORKFLOW_MAX_COUNT      = _cfg["leaf_workflow_max_count"]
LEAF_CONTRACT_MAX_ITEMS      = _cfg["leaf_contract_max_items"]
WORKFLOW_REQUIRED_SECTIONS   = _cfg["workflow_required_sections"]

# Placeholder: freshly initialized files have only these headers with no body
_PLACEHOLDER_ARCH_HEADERS = {"## Overview", "## Structure", "## Key Decisions",
                             "## Positioning", "## Class Diagram"}
_PLACEHOLDER_CONTRACT_HEADERS = {"## Interfaces", "## Events"}

# History/modification record markers
_HISTORY_RE = re.compile(
    r"(^##\s*(修改记录|变更(历史|记录)|历史记录|Changelog|Change\s*Log))"
    r"|(^\|\s*20\d{2}[-年])"           # table row starting with a date
    r"|(^-\s+20\d{2}-\d{2}-\d{2}\b)"  # bullet + ISO date
    r"|(^v\d+\.\d+[\s:])",             # version tag like "v1.2 ..."
    re.IGNORECASE,
)

_KEBAB_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")

# Mermaid graph node extraction: NODE_ID["label"] or NODE_ID[label] or NODE_ID(label)
_GRAPH_NODE_RE = re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*)\s*[\[\(]\s*[\"']?([^\"'\]\)]+)[\"']?\s*[\]\)]"
)


# ---------------------------------------------------------------------------
# Per-file checks
# ---------------------------------------------------------------------------

def _is_placeholder(content: str, placeholder_headers: set[str]) -> bool:
    """True if the file contains only template section headers and no real body."""
    real_lines = [
        l for l in content.splitlines()
        if l.strip()
        and not l.strip().startswith("#")
        and l.strip() not in placeholder_headers
    ]
    return len(real_lines) < PLACEHOLDER_MIN_REAL_LINES


def _history_markers(content: str) -> list[str]:
    """Return lines that look like modification history."""
    hits = []
    for line in content.splitlines():
        if _HISTORY_RE.search(line.strip()):
            hits.append(line.strip())
    return hits


def _list_workflows(mod_dir: Path) -> list[Path]:
    """Return paths to all workflow.md files under this module."""
    wf_dir = mod_dir / ".dna" / "workflows"
    if not wf_dir.exists():
        return []
    return [d / "workflow.md" for d in sorted(wf_dir.iterdir())
            if d.is_dir() and (d / "workflow.md").exists()]


def _count_workflows(mod_dir: Path) -> int:
    return len(_list_workflows(mod_dir))


def _check_workflow(wf_file: Path) -> list[str]:
    """Return list of issues for one workflow.md (empty = OK)."""
    issues = []
    try:
        content = wf_file.read_text(encoding="utf-8")
    except (FileNotFoundError, PermissionError):
        issues.append("unreadable")
        return issues

    # #WF1 — not placeholder
    real_lines = [l for l in content.splitlines()
                  if l.strip() and not l.strip().startswith("#")]
    if len(real_lines) < PLACEHOLDER_MIN_REAL_LINES:
        issues.append("placeholder (no real content)")

    # #WF2 — required sections present
    headers = {l.strip() for l in content.splitlines() if l.strip().startswith("## ")}
    for required in WORKFLOW_REQUIRED_SECTIONS:
        if required not in headers:
            issues.append(f"missing required section '{required}'")

    return issues


def _count_contract_items(content: str) -> int:
    """Heuristic: count ### headers and top-level bullet items as interface entries."""
    count = 0
    for line in content.splitlines():
        s = line.strip()
        if s.startswith("### ") or (s.startswith("- ") and len(s) > 4):
            count += 1
    return count


def _read_arch_content(mod_dir: Path) -> str:
    """Read architecture content: module.md body (new format) or architecture.md (legacy)."""
    dna_dir = mod_dir / ".dna"
    module_md = dna_dir / "module.md"
    if module_md.exists():
        raw = module_md.read_text(encoding="utf-8")
        # Strip frontmatter to get just the body
        if raw.startswith("---"):
            end = raw.find("\n---", 3)
            if end != -1:
                return raw[end + 4:].strip()
        return raw.strip()

    # Legacy fallback
    arch_file = dna_dir / "architecture.md"
    if arch_file.exists():
        return arch_file.read_text(encoding="utf-8")
    return ""


# ---------------------------------------------------------------------------
# Graph helpers
# ---------------------------------------------------------------------------

def _detect_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    """DFS cycle detection. Returns each cycle as a list of node IDs."""
    visited: set[str] = set()
    on_stack: set[str] = set()
    cycles: list[list[str]] = []

    def _dfs(node: str, path: list[str]) -> None:
        visited.add(node)
        on_stack.add(node)
        for nb in graph.get(node, []):
            if nb not in graph:
                continue
            if nb not in visited:
                _dfs(nb, path + [nb])
            elif nb in on_stack:
                idx = next((i for i, n in enumerate(path) if n == nb), 0)
                cycles.append(path[idx:] + [nb])
        on_stack.discard(node)

    for node in list(graph):
        if node not in visited:
            _dfs(node, [node])
    return cycles


def _is_leaf(path: str, all_paths: set[str]) -> bool:
    prefix = (path + "/") if path != "." else ""
    return not any(p != path and p.startswith(prefix) for p in all_paths)


def _detect_phantom_subnodes(arch: str, parent_path: str, parent_dir: Path,
                             all_paths: set[str]) -> list[str]:
    """For a parent module's body, scan mermaid `graph` blocks. For each node
    whose ID or label matches an actual sub-directory of this module, check
    whether that sub-directory has a .dna/. Return labels lacking .dna/."""

    # Extract graph blocks
    blocks = []
    in_block = False
    cur: list[str] = []
    for line in arch.splitlines():
        stripped = line.strip()
        if stripped.startswith("```mermaid"):
            in_block = True
            cur = []
            continue
        if in_block and stripped.startswith("```"):
            in_block = False
            blocks.append("\n".join(cur))
            cur = []
            continue
        if in_block:
            cur.append(line)

    # Only inspect blocks that declare a 'graph' (not classDiagram/sequenceDiagram/etc.)
    graph_blocks = [b for b in blocks if re.search(r"^\s*graph\s+", b, re.MULTILINE)
                    or re.search(r"^\s*flowchart\s+", b, re.MULTILINE)]
    if not graph_blocks:
        return []

    # Collect immediate sub-directories of the parent module, applying the
    # same skip-list used by module discovery so that framework/vendor dirs
    # (cbim/, node_modules/, dist/, ...) don't get reported as phantoms when
    # referenced in the root graph.
    try:
        sub_dirs = {
            d.name for d in parent_dir.iterdir()
            if d.is_dir()
            and not d.name.startswith(".")
            and d.name not in _SCAN_SKIP_DIRS
        }
    except (FileNotFoundError, PermissionError):
        return []

    # Build set of sub-paths that DO have .dna/
    base_prefix = "" if parent_path == "." else parent_path + "/"
    have_dna = {p[len(base_prefix):].split("/")[0]
                for p in all_paths
                if p != parent_path and p.startswith(base_prefix)}

    phantom = []
    seen: set[str] = set()
    for block in graph_blocks:
        for node_id, label in _GRAPH_NODE_RE.findall(block):
            for token in (node_id, label):
                # Match against sub_dirs (case-sensitive; tolerate `name/` and `name<br/>`)
                clean = token.split("<")[0].split("/")[0].strip().lower()
                for sub in sub_dirs:
                    if sub.lower() == clean and sub not in have_dna and sub not in seen:
                        seen.add(sub)
                        phantom.append(sub)
                        break
    return phantom


# ---------------------------------------------------------------------------
# Main check runner
# ---------------------------------------------------------------------------

def run_checks(root: Path) -> dict[str, list[str]]:
    # Use a fresh filesystem scan for validation so we can detect drift
    # between what's actually on disk and what the registry claims.
    modules = _scan_modules(root)
    issues: dict[str, list[str]] = {"MUST": [], "SUGGEST": []}

    if not modules:
        return issues

    mod_map = {m["path"]: m for m in modules}
    all_paths = set(mod_map)
    dep_graph = {m["path"]: [d for d in m.get("dependencies", [])] for m in modules}

    # Module registry lives at cbim/.dna/index.md (framework-managed). This
    # replaces the old <project-root>/.dna/index.md location.
    index_paths: set[str] = set(read_index(root))

    # ── Per-module checks ─────────────────────────────────────────────────
    for m in modules:
        path = m["path"]
        mod_dir = root / path if path != "." else root
        dna_dir = mod_dir / ".dna"

        # Read architecture content (module.md body or legacy architecture.md)
        arch = _read_arch_content(mod_dir)
        contract_file = dna_dir / "contract.md"
        contract = contract_file.read_text(encoding="utf-8") if contract_file.exists() else ""

        # #1 — kebab-case name
        raw_name = m["name"]
        if not _KEBAB_RE.match(raw_name.replace(" ", "-").lower()):
            # Actual check is on the directory-component (the path leaf)
            leaf_dir = Path(path).name if path != "." else "."
            if leaf_dir != "." and not _KEBAB_RE.match(leaf_dir):
                issues["MUST"].append(
                    f"[#1] {path}: directory name '{leaf_dir}' is not kebab-case"
                )

        # #2 — not placeholder (contract.md is optional; only check if present)
        if arch and _is_placeholder(arch, _PLACEHOLDER_ARCH_HEADERS):
            issues["MUST"].append(f"[#2] {path}: module.md body has no real content (still a template)")
        elif not arch:
            issues["MUST"].append(f"[#2] {path}: module.md body is empty")
        if contract_file.exists() and contract and _is_placeholder(contract, _PLACEHOLDER_CONTRACT_HEADERS):
            issues["MUST"].append(f"[#2] {path}: contract.md has no real content (still a template)")

        # #3 — no modification history (contract.md checked only if present)
        check_pairs = [(arch, "module.md")]
        if contract_file.exists():
            check_pairs.append((contract, "contract.md"))
        for content, fname in check_pairs:
            hits = _history_markers(content)
            if hits:
                issues["MUST"].append(
                    f"[#3] {path}/{fname}: contains modification history — \"{hits[0]}\""
                )

        # #WF1 #WF2 — workflow checks (all modules that have workflows)
        for wf_file in _list_workflows(mod_dir):
            wf_name = wf_file.parent.name
            wf_issues = _check_workflow(wf_file)
            for wi in wf_issues:
                issues["MUST"].append(f"[#WF] {path}/.dna/workflows/{wf_name}: {wi}")

        # Parent-specific structural smells (#19 #20)
        if not _is_leaf(path, all_paths):
            # #19 — parent module body uses leaf-shaped diagram
            if arch and "classDiagram" in arch:
                issues["MUST"].append(
                    f"[#19] {path}: parent module body contains 'classDiagram' — "
                    f"should use 'graph' showing sub-modules. Sub-module internals "
                    f"belong in their own .dna/module.md."
                )

            # #20 — graph nodes reference sub-paths that have no .dna/
            if arch:
                phantom = _detect_phantom_subnodes(arch, path, mod_dir, all_paths)
                for label in phantom:
                    issues["SUGGEST"].append(
                        f"[#20] {path}: component diagram references '{label}' "
                        f"but no .dna/ exists there — promote to sub-module or "
                        f"remove from diagram."
                    )

        # Leaf-specific structural smells (#21)
        if _is_leaf(path, all_paths) and arch:
            mermaid_blocks = re.findall(
                r"```mermaid\s*\n(.*?)```", arch, re.DOTALL
            )
            has_class = any("classDiagram" in b for b in mermaid_blocks)
            graph_blocks = [
                b for b in mermaid_blocks
                if re.search(r"^\s*(?:graph|flowchart)\s", b, re.MULTILINE)
            ]
            if graph_blocks and not has_class:
                # Count distinct nodes across all graph blocks
                node_ids: set[str] = set()
                for gb in graph_blocks:
                    for node_id, _label in _GRAPH_NODE_RE.findall(gb):
                        node_ids.add(node_id)
                if len(node_ids) >= 3:
                    issues["MUST"].append(
                        f"[#21] {path}: leaf module body uses graph/flowchart "
                        f"mermaid with {len(node_ids)} internal nodes — this is "
                        f"a parent-in-disguise pattern. Either (a) promote those "
                        f"components to real sub-modules (each with its own .dna/), "
                        f"or (b) replace with a real 'classDiagram' showing "
                        f"classes/interfaces only — renaming the section header is "
                        f"not enough."
                    )

        # Leaf-specific
        if _is_leaf(path, all_paths):
            # #17 — volume check
            arch_lines = len([l for l in arch.splitlines() if l.strip()]) if arch else 0
            wf_count = _count_workflows(mod_dir)
            reasons = []
            if arch_lines > LEAF_ARCH_MAX_LINES:
                reasons.append(f"module.md body {arch_lines} non-empty lines (>{LEAF_ARCH_MAX_LINES})")
            if wf_count >= LEAF_WORKFLOW_MAX_COUNT:
                reasons.append(f"{wf_count} workflows (>={LEAF_WORKFLOW_MAX_COUNT})")
            if contract_file.exists() and contract:
                ci_count = _count_contract_items(contract)
                if ci_count >= LEAF_CONTRACT_MAX_ITEMS:
                    reasons.append(f"contract has {ci_count} items (>={LEAF_CONTRACT_MAX_ITEMS})")
            if reasons:
                issues["SUGGEST"].append(
                    f"[#17] {path}: leaf volume too large ({'; '.join(reasons)}) — consider splitting"
                )

    # ── Index checks ──────────────────────────────────────────────────────

    # #4 — index.md sync (all actual modules present)
    for p in sorted(all_paths - index_paths):
        issues["MUST"].append(f"[#4] index.md missing module: {p}")
    for p in sorted(index_paths - all_paths):
        issues["MUST"].append(f"[#4] index.md lists non-existent module: {p}")

    # #15 — index covers all leaf modules
    leaf_paths = {p for p in all_paths if _is_leaf(p, all_paths)}
    for p in sorted(leaf_paths - index_paths):
        issues["MUST"].append(f"[#15] index.md missing leaf module: {p}")

    # ── Dependency graph checks ───────────────────────────────────────────

    # #14 — global cycle detection
    global_cycles = _detect_cycles(dep_graph)
    seen_cycles: set[frozenset] = set()
    for cycle in global_cycles:
        key = frozenset(cycle)
        if key not in seen_cycles:
            seen_cycles.add(key)
            issues["MUST"].append(f"[#14] circular dependency: {' → '.join(cycle)}")

    # #10 — same-level cycle detection (among siblings only)
    siblings: dict[str, list[str]] = defaultdict(list)
    for path in all_paths:
        parent = str(Path(path).parent) if path != "." else "__root__"
        siblings[parent].append(path)

    for sibling_list in siblings.values():
        sibling_set = set(sibling_list)
        sub_graph = {
            s: [d for d in dep_graph.get(s, []) if d in sibling_set]
            for s in sibling_list
        }
        sub_graph = {k: v for k, v in sub_graph.items() if v}
        if sub_graph:
            for cycle in _detect_cycles(sub_graph):
                key = frozenset(cycle)
                if key not in seen_cycles:
                    seen_cycles.add(key)
                    issues["MUST"].append(
                        f"[#10] same-level circular dependency: {' → '.join(cycle)}"
                    )

    return issues


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deterministic architecture governance checks (#1 #2 #3 #4 #10 #14 #15 #17)"
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
        print(f"架构治理脚本检查 — {root.name}")
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
            print("  All script checks passed")

    sys.exit(1 if must else 0)


if __name__ == "__main__":
    main()
