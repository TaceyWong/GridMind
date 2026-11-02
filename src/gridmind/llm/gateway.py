from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from gridmind.core.config import settings
from gridmind.llm.providers import (
    ChatMessage,
    LLMProvider,
    LLMResult,
    MockProvider,
    OpenAICompatibleProvider,
    TokenUsage,
)


class LLMGateway:
    """Model gateway with provider registry, fallback to mock when no API key."""

    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {"mock": MockProvider()}
        self.usage_total = TokenUsage()
        if settings.has_llm_key:
            self._providers["openai"] = OpenAICompatibleProvider(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                default_model=settings.llm_model,
                timeout=settings.llm_timeout,
                max_retries=settings.llm_max_retries,
                provider_name="openai",
            )
            # Aliases for common OpenAI-compatible vendors using same base URL/key.
            for alias in ("deepseek", "qwen", "local"):
                self._providers[alias] = self._providers["openai"]

    @property
    def default_provider(self) -> str:
        return "openai" if settings.has_llm_key else "mock"

    def list_providers(self) -> list[str]:
        return sorted(self._providers.keys())

    def get(self, provider: str | None = None) -> LLMProvider:
        name = provider or self.default_provider
        if name not in self._providers:
            return self._providers[self.default_provider]
        return self._providers[name]

    async def chat(
        self,
        messages: list[ChatMessage] | list[dict[str, str]],
        *,
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> LLMResult:
        normalized = _normalize_messages(messages)
        result = await self.get(provider).chat(
            normalized, model=model, temperature=temperature, **kwargs
        )
        self.usage_total.add(result.usage)
        return result

    async def stream(
        self,
        messages: list[ChatMessage] | list[dict[str, str]],
        *,
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        normalized = _normalize_messages(messages)
        async for chunk in self.get(provider).stream(
            normalized, model=model, temperature=temperature, **kwargs
        ):
            yield chunk


def _normalize_messages(
    messages: list[ChatMessage] | list[dict[str, str]],
) -> list[ChatMessage]:
    out: list[ChatMessage] = []
    for m in messages:
        if isinstance(m, ChatMessage):
            out.append(m)
        else:
            out.append(ChatMessage(role=m["role"], content=m["content"]))
    return out


_gateway: LLMGateway | None = None


def get_llm_gateway() -> LLMGateway:
    global _gateway
    if _gateway is None:
        _gateway = LLMGateway()
    return _gateway
