from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from gridmind.core.config import settings
from gridmind.llm.providers import (
    ChatMessage,
    LiteLLMProvider,
    LLMProvider,
    LLMResult,
    MockProvider,
    TokenUsage,
    resolve_litellm_model,
)


class LLMGateway:
    """LLM gateway: LiteLLM transport + langchain-openai ChatModel surface."""

    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {"mock": MockProvider()}
        self.usage_total = TokenUsage()
        if settings.has_llm_key:
            shared = LiteLLMProvider(
                api_key=settings.llm_api_key,
                api_base=settings.llm_base_url,
                default_model=settings.llm_model,
                timeout=settings.llm_timeout,
                max_retries=settings.llm_max_retries,
                provider_name="openai",
            )
            self._providers["openai"] = shared
            for alias in ("deepseek", "qwen", "local", "litellm"):
                self._providers[alias] = LiteLLMProvider(
                    api_key=settings.llm_api_key,
                    api_base=settings.llm_base_url,
                    default_model=settings.llm_model,
                    timeout=settings.llm_timeout,
                    max_retries=settings.llm_max_retries,
                    provider_name=alias if alias != "litellm" else "openai",
                )

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

    def get_chat_model(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> BaseChatModel:
        """LangChain ChatOpenAI model (OpenAI-compatible endpoint via settings).

        Use this in LCEL / Tool Calling. Runtime multi-provider routing for
        gateway.chat/stream goes through LiteLLM.
        """
        if not settings.has_llm_key:
            raise RuntimeError("LLM_API_KEY not configured; ChatOpenAI unavailable")

        # ChatOpenAI talks OpenAI-compatible HTTP; strip litellm provider prefix
        raw_model = resolve_litellm_model(provider, model)
        openai_model = raw_model.split("/", 1)[-1]
        return ChatOpenAI(
            model=openai_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=temperature,
            timeout=settings.llm_timeout,
            max_retries=settings.llm_max_retries,
        )

    async def chat(
        self,
        messages: list[ChatMessage] | list[dict[str, str]] | list[BaseMessage],
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

    async def chat_langchain(
        self,
        messages: list[ChatMessage] | list[dict[str, str]] | list[BaseMessage],
        *,
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> LLMResult:
        """Invoke via langchain-openai ChatOpenAI (same credentials/base_url)."""
        if not settings.has_llm_key:
            return await self.chat(
                messages, provider="mock", model=model, temperature=temperature
            )

        lc_messages = _to_lc_messages(_normalize_messages(messages))
        llm = self.get_chat_model(
            provider=provider, model=model, temperature=temperature
        )
        ai = await llm.ainvoke(lc_messages)
        content = ai.content if isinstance(ai.content, str) else str(ai.content)
        usage = TokenUsage()
        meta = getattr(ai, "usage_metadata", None) or {}
        if meta:
            usage = TokenUsage(
                prompt_tokens=int(meta.get("input_tokens") or 0),
                completion_tokens=int(meta.get("output_tokens") or 0),
                total_tokens=int(meta.get("total_tokens") or 0),
            )
            self.usage_total.add(usage)
        resolved = resolve_litellm_model(provider, model)
        return LLMResult(content=content, model=resolved, usage=usage, raw=ai)

    async def stream(
        self,
        messages: list[ChatMessage] | list[dict[str, str]] | list[BaseMessage],
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
    messages: list[ChatMessage] | list[dict[str, str]] | list[BaseMessage],
) -> list[ChatMessage]:
    out: list[ChatMessage] = []
    for m in messages:
        if isinstance(m, ChatMessage):
            out.append(m)
        elif isinstance(m, BaseMessage):
            role = "assistant"
            if isinstance(m, HumanMessage):
                role = "user"
            elif isinstance(m, SystemMessage):
                role = "system"
            elif isinstance(m, AIMessage):
                role = "assistant"
            content = m.content if isinstance(m.content, str) else str(m.content)
            out.append(ChatMessage(role=role, content=content))
        else:
            out.append(ChatMessage(role=m["role"], content=m["content"]))
    return out


def _to_lc_messages(messages: list[ChatMessage]) -> list[BaseMessage]:
    out: list[BaseMessage] = []
    for m in messages:
        if m.role == "system":
            out.append(SystemMessage(content=m.content))
        elif m.role == "assistant":
            out.append(AIMessage(content=m.content))
        else:
            out.append(HumanMessage(content=m.content))
    return out


_gateway: LLMGateway | None = None


def get_llm_gateway() -> LLMGateway:
    global _gateway
    if _gateway is None:
        _gateway = LLMGateway()
    return _gateway
