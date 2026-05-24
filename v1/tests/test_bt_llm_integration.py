"""L5 — real-LLM integration tests (all skipped in 4A+4B).

Markers: @pytest.mark.requires_api_key. Conftest controls enablement via
ANTHROPIC_API_KEY env var.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.requires_api_key


@pytest.mark.skip(reason="L5: LLM not wired in 4A+4B; enable in 4D")
def test_intent_analyze_with_real_llm():
    # Will exercise IntentAnalyze(llm=AnthropicLLM(...)).classify() on a
    # truly novel request that no rule matches.
    pass


@pytest.mark.skip(reason="L5: LLM not wired in 4A+4B; enable in 4D")
def test_converge_judge_with_real_llm_on_edge_case():
    # Edge: 2 ok subtasks but outputs imply a new subtask. Real LLM should
    # return new_subtasks_implied=True; rule path returns False.
    pass


@pytest.mark.skip(reason="L5: LLM not wired in 4A+4B; enable in 4D")
def test_decompose_with_real_llm_complex_request():
    # "Build a saga that updates 3 modules atomically" — real LLM should
    # decompose into 3+ subtasks with ordered depends_on.
    pass
