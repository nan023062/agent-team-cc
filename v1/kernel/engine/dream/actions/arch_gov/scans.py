"""arch_gov/scans.py — Eight LLM-driven scan leaves.

Each scan inspects `state["inventory"]`, asks the LLM to identify problems
matching its specific criterion, and writes the findings list to
`state["findings"][<scan_id>]`. An empty list is a legitimate result.

Finding shape (loose contract; Classify reads `.kind`):
    {"kind": "<scan_id>", "subject": "<module_path>", "detail": "<one line>"}

These leaves subclass `LlmActionLeaf` so when t2 lands the prompt/parse
hooks are wired through the real primitive. Until then the stub returns
SUCCESS with an empty findings list — Classify treats absent / empty as
nothing to do.
"""
from __future__ import annotations

import json
from typing import Any

from ._llm_leaf import LlmActionLeaf


# ---------------------------------------------------------------------------
# Shared scan base — bookkeeping + tick wrapper
# ---------------------------------------------------------------------------

class _ScanBase(LlmActionLeaf):
    """Base for the eight architect-governance scans.

    Subclass overrides:
      SCAN_ID:    short ASCII id, used as state["findings"] key
      CRITERION: one-sentence judgment criterion (for the LLM prompt)
      BUCKET_HINT: "safe" | "risky" — non-binding hint for Classify
    """

    SCAN_ID: str = "scan_base"
    CRITERION: str = ""
    BUCKET_HINT: str = "risky"

    def __init__(self, *, llm, state: dict, name: str = "Scan") -> None:
        super().__init__(llm=llm, name=name)
        self._state = state

    def build_prompt(self, bb, state: dict) -> str:
        inv = state.get("inventory") or {}
        modules_brief = [
            {"path": m["path"], "deps": m.get("deps", []),
             "status": m.get("frontmatter", {}).get("status"),
             "owner":  m.get("frontmatter", {}).get("owner")}
            for m in inv.get("modules", [])
        ]
        return (
            "你是 architect 治理子循环里的一个扫描节点。\n"
            f"扫描类别：{self.SCAN_ID}\n"
            f"判据：{self.CRITERION}\n\n"
            "下面是当前 .dna/ 模块清单（已脱敏，只保留路径 / 依赖 / status / owner）：\n"
            f"```json\n{json.dumps(modules_brief, ensure_ascii=False, indent=2)}\n```\n\n"
            "请返回严格 JSON：`{\"findings\": [{\"subject\": \"<模块路径>\", "
            "\"detail\": \"<一句话说明>\"}, ...]}`。\n"
            "若没有符合判据的模块，返回 `{\"findings\": []}`。"
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
        # parsed is always a list (possibly empty) from parse_reply.
        state.setdefault("findings", {})[self.SCAN_ID] = list(parsed or [])


# ---------------------------------------------------------------------------
# Eight concrete scans — order locked by build_architect_governance_subtree
# ---------------------------------------------------------------------------

class ScanOrphan(_ScanBase):
    SCAN_ID = "scan_orphan"
    CRITERION = (
        "存在 .dna/module.md 但实际模块目录已不存在（幽灵模块）。"
        "只看 inventory 中 dna_present=true 且 dir_present=false 的项。"
    )
    BUCKET_HINT = "safe"  # dna_reindex 可清掉，无副作用


class ScanStale(_ScanBase):
    SCAN_ID = "scan_stale"
    CRITERION = (
        "frontmatter.status=implemented 但代码近期无变更，"
        "或 contract.md 长期未更新 — 模块可能已实质废弃。"
    )
    BUCKET_HINT = "risky"


class ScanCycle(_ScanBase):
    SCAN_ID = "scan_cycle"
    CRITERION = (
        "依赖图中出现循环（A→B→A 或更长环路）。"
        "用 inventory 中每个模块的 deps 字段构建有向图。"
    )
    BUCKET_HINT = "risky"


class ScanDrift(_ScanBase):
    SCAN_ID = "scan_drift"
    CRITERION = (
        "已发布契约（contract.md）与当前代码行为出现明显背离。"
        "标准：模块声明的接口与其他模块的调用方式不一致。"
    )
    BUCKET_HINT = "risky"


class ScanPromote(_ScanBase):
    SCAN_ID = "scan_promote"
    CRITERION = (
        "frontmatter.status=spec 但代码已实现 — 可提升为 implemented。"
        "或近期 memory 里反复出现的决策可固化为模块知识。"
    )
    BUCKET_HINT = "risky"


class ScanSplit(_ScanBase):
    SCAN_ID = "scan_split"
    CRITERION = (
        "单一模块 body 描述了明显属于另一职责域的内容；"
        "模块过宽，应裂变为多个。"
    )
    BUCKET_HINT = "risky"


class ScanMerge(_ScanBase):
    SCAN_ID = "scan_merge"
    CRITERION = (
        "两个或多个模块职责高度重叠，接口几乎重合；"
        "可合并以消除冗余。"
    )
    BUCKET_HINT = "risky"


class ScanRestructure(_ScanBase):
    SCAN_ID = "scan_restructure"
    CRITERION = (
        "命名 / 层级不符合规范（非 kebab-case、不按 src/<domain>/<module> 分层）；"
        "或整片依赖图层级混乱需重组。"
    )
    BUCKET_HINT = "risky"


__all__ = [
    "ScanOrphan",
    "ScanStale",
    "ScanCycle",
    "ScanDrift",
    "ScanPromote",
    "ScanSplit",
    "ScanMerge",
    "ScanRestructure",
]
