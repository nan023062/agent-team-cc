"""audit/checks — individual governance drift checks.

Each module exposes `check(project_root, config) -> list[AuditFinding]`.
The registry in `audit/registry.py` wires them by name.
"""
