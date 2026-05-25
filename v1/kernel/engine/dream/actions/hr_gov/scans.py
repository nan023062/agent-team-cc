"""hr_gov/scans.py — Six scan leaves for HR governance.

Mix of deterministic and LLM-driven:
  ScanBroken   — deterministic (frontmatter required-field check)
  ScanIdle     — deterministic stub (no task-history source available yet
                 at the kernel layer; logs the unknown and returns empty)
  ScanGap, ScanDrift, ScanDuplicate, ScanWide — LLM-driven (signal lives
                 in agent descriptions / recent task patterns, not in
                 structured kernel data)

Finding shape (loose contract; Classify reads `.kind` and `.bucket_hint`):
    {"kind": "<scan_id>", "subject": "<agent_name>", "detail": "<one line>",
     "bucket_hint": "safe" | "risky"}
"""
from __future__ import annotations

import json
from typing import Any

from engine.core.node import Node, Status

from ._llm_leaf import LlmActionLeaf


# ---------------------------------------------------------------------------
# Deterministic scans
# ---------------------------------------------------------------------------

_REQUIRED_FM_FIELDS = ("name", "description", "tools")


class ScanBroken(Node):
    """Deterministic frontmatter completeness check.

    Missing required field → safe (补字段 = idempotent dna_edit-equivalent
    on the agent file). Structural unparseable agents (frontmatter empty
    AND body very short) → risky.
    """

    SCAN_ID = "scan_broken"

    def __init__(self, *, llm, state: dict, name: str = "ScanBroken") -> None:
        self.name = name
        self._state = state

    def tick(self, bb) -> Status:
        inv = self._state.get("inventory") or {}
        findings: list[dict[str, Any]] = []
        for agent in inv.get("agents", []):
            fm = agent.get("frontmatter") or {}
            missing = [k for k in _REQUIRED_FM_FIELDS if not fm.get(k)]
            if missing:
                findings.append({
                    "kind": self.SCAN_ID,
                    "subject": agent.get("name") or agent.get("path"),
                    "detail": f"frontmatter 缺字段: {', '.join(missing)}",
                    "bucket_hint": "safe" if fm else "risky",
                })
        self._state.setdefault("findings", {})[self.SCAN_ID] = findings
        return Status.SUCCESS


class ScanIdle(Node):
    """Deterministic placeholder for "14 天无任务" scan.

    The kernel doesn't yet expose a "last task dispatch per agent" feed at
    this layer; without that signal we cannot honestly mark anything as
    idle. We record an empty findings list and let the gap surface in the
    governance report as a known limitation.
    """

    SCAN_ID = "scan_idle"

    def __init__(self, *, llm, state: dict, name: str = "ScanIdle") -> None:
        self.name = name
        self._state = state

    def tick(self, bb) -> Status:
        self._state.setdefault("findings", {})[self.SCAN_ID] = []
        return Status.SUCCESS


# ---------------------------------------------------------------------------
# LLM-driven scans
# ---------------------------------------------------------------------------

class _HRScanBase(LlmActionLeaf):
    SCAN_ID: str = "scan_base"
    CRITERION: str = ""
    BUCKET_HINT: str = "risky"

    def __init__(self, *, llm, state: dict, name: str = "Scan") -> None:
        super().__init__(llm=llm, name=name)
        self._state = state

    def build_prompt(self, bb, state: dict) -> str:
        inv = state.get("inventory") or {}
        agents_brief = [
            {"name": a["name"], "path": a["path"],
             "description": (a.get("frontmatter") or {}).get("description", "")[:200]}
            for a in inv.get("agents", [])
        ]
        return (
            "你是 HR 治理子循环里的一个扫描节点。\n"
            f"扫描类别：{self.SCAN_ID}\n"
            f"判据：{self.CRITERION}\n\n"
            "下面是当前能力册（仅 name / path / description 摘要）：\n"
            f"```json\n{json.dumps(agents_brief, ensure_ascii=False, indent=2)}\n```\n\n"
            "请返回严格 JSON：`{\"findings\": [{\"subject\": \"<agent_name>\", "
            "\"detail\": \"<一句话说明>\"}, ...]}`。\n"
            "若没有符合判据的 agent，返回 `{\"findings\": []}`。"
        )

    def parse_reply(self, reply: str) -> list[dict[str, Any]]:
        if not reply or not reply.strip():
            return []
        try:
            data = json.loads(reply)
        except (ValueError, TypeError):
            return []
        if isinstance(data, dict) and isinstance(data.get("findings"), list):
            out = []
            for item in data["findings"]:
                if not isinstance(item, dict):
                    continue
                out.append({
                    "kind": self.SCAN_ID,
                    "subject": str(item.get("subject", "")),
                    "detail": str(item.get("detail", "")),
                    "bucket_hint": self.BUCKET_HINT,
                })
            return out
        return []

    def apply_result(self, bb, state: dict, parsed) -> None:
        state.setdefault("findings", {})[self.SCAN_ID] = list(parsed or [])


class ScanGap(_HRScanBase):
    SCAN_ID = "scan_gap"
    CRITERION = (
        "近期 bt_tick / hr_execution 日志中连续出现 agent_gap: <capability> "
        "≥ 3 次，且能力册中无 agent 覆盖。"
    )
    BUCKET_HINT = "risky"  # 招募 = risky


class ScanDrift(_HRScanBase):
    SCAN_ID = "scan_drift"
    CRITERION = (
        "agent Positioning / Stance 声明与近期实际承接 task 类型严重不符。"
    )
    BUCKET_HINT = "risky"


class ScanDuplicate(_HRScanBase):
    SCAN_ID = "scan_dup"
    CRITERION = (
        "两个 agent 的 description 关键词重叠 > 70%，或承接 task 类型高度相同。"
        "返回时把两个 agent 合并写在 subject 里（'agent_a vs agent_b'）。"
    )
    BUCKET_HINT = "risky"


class ScanWide(_HRScanBase):
    SCAN_ID = "scan_wide"
    CRITERION = (
        "单个 agent 连续承接 ≥ 3 类不同 capability 的任务，"
        "无法用单一定位概括。"
    )
    BUCKET_HINT = "risky"


__all__ = [
    "ScanIdle",
    "ScanBroken",
    "ScanGap",
    "ScanDrift",
    "ScanDuplicate",
    "ScanWide",
]
