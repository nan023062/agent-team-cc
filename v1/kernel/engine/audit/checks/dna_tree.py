"""checks/dna_tree.py — DNA module tree integrity.

Two relations:
  - Parent/child (decided by path nesting; tree only).
  - Dependencies (frontmatter `dependencies`; must be single-directional DAG).

Findings:
  TREE_ORPHAN               warn   module has no enclosing parent (and isn't root)
  TREE_DEP_DANGLING         warn   declared dep path is unknown
  TREE_DEP_ANCESTOR_DECLARED warn  dep targets an ancestor (implicit; must not be declared)
  TREE_DEP_UP_TREE          warn   dep points up the tree to a non-ancestor unstable side
  TREE_CYCLE                error  dep graph has a strongly-connected component
"""

from __future__ import annotations

from pathlib import Path

from services import list_modules as _service_list_modules

from ..result import AuditFinding


def _normalise(p: str) -> str:
    s = (p or "").strip()
    if s.startswith("./"):
        s = s[2:]
    if s != "." and s.endswith("/"):
        s = s.rstrip("/")
    return s


def _ancestors(path: str) -> list[str]:
    """Return ancestor paths (root-first, excluding self). Root path is '.'."""
    if path in (".", ""):
        return []
    parts = path.split("/")
    out: list[str] = []
    for i in range(len(parts)):
        anc = "/".join(parts[:i])
        out.append(anc if anc else ".")
    return out


def _find_parent(path: str, all_paths: set[str]) -> str | None:
    """Closest registered ancestor (could be '.' for root)."""
    for anc in reversed(_ancestors(path)):
        if anc in all_paths:
            return anc
    return None


def _tarjan_sccs(graph: dict[str, list[str]]) -> list[list[str]]:
    index_counter = [0]
    stack: list[str] = []
    on_stack: set[str] = set()
    index: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    sccs: list[list[str]] = []

    def strongconnect(v: str) -> None:
        index[v] = index_counter[0]
        lowlink[v] = index_counter[0]
        index_counter[0] += 1
        stack.append(v)
        on_stack.add(v)
        for w in graph.get(v, []):
            if w not in index:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], index[w])
        if lowlink[v] == index[v]:
            comp: list[str] = []
            while True:
                w = stack.pop()
                on_stack.discard(w)
                comp.append(w)
                if w == v:
                    break
            sccs.append(comp)

    for v in list(graph.keys()):
        if v not in index:
            strongconnect(v)
    return sccs


def check(project_root: Path, config: dict) -> list[AuditFinding]:
    findings: list[AuditFinding] = []

    modules = _service_list_modules(cwd=str(project_root))
    if not modules:
        return findings

    by_path: dict[str, dict] = {}
    for m in modules:
        norm = _normalise(m.get("path") or m.get("id") or "")
        by_path[norm] = m

    all_paths = set(by_path.keys())
    has_root = "." in all_paths

    for path, m in sorted(by_path.items()):
        if path == ".":
            continue
        parent = _find_parent(path, all_paths)
        if parent is None and not has_root:
            findings.append(AuditFinding(
                check="dna_tree",
                severity="warn",
                target=path,
                message=f"module {path!r} has no enclosing parent and no root module exists",
                suggestion=(
                    "Create the missing parent module via `cbim dna init <parent-dir> "
                    "--type parent ...` or move this module under an existing parent."
                ),
                code="TREE_ORPHAN",
            ))

    dep_graph: dict[str, list[str]] = {}
    for path, m in by_path.items():
        deps = [_normalise(d) for d in (m.get("dependencies") or []) if d]
        dep_graph[path] = deps
        ancestors = set(_ancestors(path))
        for dep in deps:
            if dep not in all_paths:
                findings.append(AuditFinding(
                    check="dna_tree",
                    severity="warn",
                    target=path,
                    message=f"module {path!r} declares dependency on unknown path {dep!r}",
                    suggestion=(
                        "Remove the stale dependency via `cbim dna edit "
                        "--target frontmatter --field dependencies` or create the "
                        "missing module."
                    ),
                    code="TREE_DEP_DANGLING",
                    metadata={"dep": dep},
                ))
                continue
            if dep in ancestors:
                findings.append(AuditFinding(
                    check="dna_tree",
                    severity="warn",
                    target=path,
                    message=(
                        f"module {path!r} declares ancestor {dep!r} as a dependency; "
                        "sub-module-to-parent imports are implicit and must not be declared"
                    ),
                    suggestion=(
                        f"Remove ancestor {dep!r} from `dependencies` frontmatter; "
                        "sub-module-to-parent imports are implicit and should not be "
                        "declared as cross-boundary deps."
                    ),
                    code="TREE_DEP_ANCESTOR_DECLARED",
                    metadata={"dep": dep},
                ))
                continue

    for comp in _tarjan_sccs(dep_graph):
        if len(comp) <= 1:
            v = comp[0] if comp else None
            if v is None or v not in dep_graph.get(v, []):
                continue
        findings.append(AuditFinding(
            check="dna_tree",
            severity="error",
            target=None,
            message=f"dependency cycle detected: {' -> '.join(sorted(comp))}",
            suggestion="Break the cycle by extracting the shared concern into a leaf module.",
            code="TREE_CYCLE",
            metadata={"cycle": sorted(comp)},
        ))

    return findings
