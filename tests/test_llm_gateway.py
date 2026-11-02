import pytest

from gridmind.llm.gateway import get_llm_gateway
from gridmind.llm.providers import ChatMessage, resolve_litellm_model


def test_resolve_litellm_model_prefix():
    assert resolve_litellm_model("openai", "gpt-4o-mini") == "openai/gpt-4o-mini"
    assert resolve_litellm_model("deepseek", "deepseek-chat") == "deepseek/deepseek-chat"
    assert resolve_litellm_model("openai", "openai/gpt-4o") == "openai/gpt-4o"


@pytest.mark.asyncio
async def test_mock_gateway_chat():
    gateway = get_llm_gateway()
    # Force mock path regardless of env
    result = await gateway.chat(
        [ChatMessage(role="user", content="hello")],
        provider="mock",
    )
    assert "mock" in result.content.lower() or "GridMind" in result.content
