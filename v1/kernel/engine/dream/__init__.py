"""engine.dream — CBIM governance loop driver (second root, peer of engine.execution).

Reuses engine.execution.core primitives (Node ABC / Composite / Decorator / Runner /
persistence / trace) but owns an independent root topology, blackboard schema,
trace, and MCP entry surface. Dependency is strictly one-way: dream → bt.core.
"""
