"""actions/llm_hook.py — LLM protocol stubs used by v3 actions.

v3 actions that may invoke an LLM (ModeClassify, DirectReply) take the
client via constructor injection. NullLLM is the default — it never raises
on protocol methods so the engine remains importable and the rule path
remains usable without any LLM wiring.

Real LLM implementations live in `llm_client.py` (AnthropicLLM).
"""

from __future__ import annotations


class NullLLM:
    """Default LLM hook — every protocol method returns a benign default.

    Tests that want a stub pass StubLLM to the action constructor.
    """

    def classify_mode(self, user_request: str) -> str:
        """Classify request into 'conversation' | 'execution'.

        NullLLM default: 'execution'. Real LLM may return either label.
        """
        return "execution"

    def reply_conversation(self, user_request: str) -> str:
        """Generate a conversational reply.

        NullLLM default: a passthrough placeholder so the engine can still
        return a coherent Done message without any LLM wired.
        """
        return f"（对话模式）{user_request}"

    def run(self, prompt: str) -> str:
        """Generic single-prompt entry used by LlmActionLeaf.

        NullLLM default: a JSON stub that downstream parsers can decode
        without crashing. Real clients perform the actual completion.
        """
        return '{"result": null}'
