from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import litellm

from gridmind.core.config import settings

logger = logging.getLogger(__name__)

# Keep LiteLLM quieter in learning demos
litellm.suppress_debug_info = True


@dataclass
class ChatMessage:
    role: str
    content: str


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def add(self, other: TokenUsage) -> None:
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.total_tokens += other.total_tokens


@dataclass
class LLMResult:
    content: str
    model: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    raw: Any = None


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> LLMResult:
        raise NotImplementedError

    @abstractmethod
    async def stream(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        raise NotImplementedError
        yield  # pragma: no cover


class MockProvider(LLMProvider):
    name = "mock"

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> LLMResult:
        user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        content = (
            f"[mock] GridMind 收到问题：{user}\n"
            "当前未配置 LLM_API_KEY，已使用规则/模板降级回答。"
        )
        return LLMResult(content=content, model=model or "mock")

    async def stream(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        result = await self.chat(messages, model=model, temperature=temperature, **kwargs)
        for chunk in result.content:
            yield chunk
            await asyncio.sleep(0)


PROVIDER_MODEL_PREFIX: dict[str, str] = {
    "openai": "openai",
    "deepseek": "deepseek",
    "qwen": "openai",  # many Qwen deployments are OpenAI-compatible
    "local": "openai",
}


def resolve_litellm_model(provider: str | None, model: str | None) -> str:
    """Map provider/model to a LiteLLM model id.

    Examples:
      openai + gpt-4o-mini -> openai/gpt-4o-mini
      deepseek + deepseek-chat -> deepseek/deepseek-chat
      already-prefixed openai/gpt-4o-mini -> unchanged
    """
    raw = (model or settings.llm_model).strip()
    if "/" in raw:
        return raw
    prefix = PROVIDER_MODEL_PREFIX.get((provider or "openai").lower(), "openai")
    return f"{prefix}/{raw}"


class LiteLLMProvider(LLMProvider):
    """Multi-provider chat via LiteLLM; OpenAI-compatible api_base supported."""

    def __init__(
        self,
        *,
        api_key: str,
        api_base: str,
        default_model: str,
        provider_name: str = "openai",
        timeout: float = 60.0,
        max_retries: int = 2,
    ) -> None:
        self.name = provider_name
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.default_model = default_model
        self.timeout = timeout
        self.max_retries = max_retries

    def _model(self, model: str | None) -> str:
        return resolve_litellm_model(self.name, model or self.default_model)

    def _payload_messages(self, messages: list[ChatMessage]) -> list[dict[str, str]]:
        return [{"role": m.role, "content": m.content} for m in messages]

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> LLMResult:
        model_name = self._model(model)
        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = await litellm.acompletion(
                    model=model_name,
                    messages=self._payload_messages(messages),
                    temperature=temperature,
                    api_key=self.api_key,
                    api_base=self.api_base,
                    timeout=self.timeout,
                    **kwargs,
                )
                content = resp.choices[0].message.content or ""
                usage = TokenUsage()
                if getattr(resp, "usage", None):
                    usage = TokenUsage(
                        prompt_tokens=int(getattr(resp.usage, "prompt_tokens", 0) or 0),
                        completion_tokens=int(
                            getattr(resp.usage, "completion_tokens", 0) or 0
                        ),
                        total_tokens=int(getattr(resp.usage, "total_tokens", 0) or 0),
                    )
                return LLMResult(content=content, model=model_name, usage=usage, raw=resp)
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                logger.warning("LiteLLM chat attempt %s failed: %s", attempt + 1, exc)
                await asyncio.sleep(0.5 * (attempt + 1))
        raise RuntimeError(f"LiteLLM chat failed after retries: {last_err}")

    async def stream(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        model_name = self._model(model)
        stream = await litellm.acompletion(
            model=model_name,
            messages=self._payload_messages(messages),
            temperature=temperature,
            api_key=self.api_key,
            api_base=self.api_base,
            timeout=self.timeout,
            stream=True,
            **kwargs,
        )
        async for event in stream:
            choices = getattr(event, "choices", None) or []
            if not choices:
                continue
            delta = choices[0].delta
            text = getattr(delta, "content", None)
            if text:
                yield text
