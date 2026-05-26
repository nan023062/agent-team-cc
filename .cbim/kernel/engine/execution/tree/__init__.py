"""tree/ — global ROOT topology factory.

Re-exports build_root + ROOT from main_loop so callers can `from
engine.execution.tree import ROOT`.
"""

from .main_loop import ROOT, build_root  # noqa: F401
