from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


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


class OpenAICompatibleProvider(LLMProvider):
    name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        default_model: str,
        timeout: float = 60.0,
        max_retries: int = 2,
        provider_name: str = "openai",
    ) -> None:
        self.name = provider_name
        self.default_model = default_model
        self.max_retries = max_retries
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> LLMResult:
        model_name = model or self.default_model
        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = await self.client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": m.role, "content": m.content} for m in messages],
                    temperature=temperature,
                    **kwargs,
                )
                choice = resp.choices[0].message.content or ""
                usage = TokenUsage()
                if resp.usage:
                    usage = TokenUsage(
                        prompt_tokens=resp.usage.prompt_tokens or 0,
                        completion_tokens=resp.usage.completion_tokens or 0,
                        total_tokens=resp.usage.total_tokens or 0,
                    )
                return LLMResult(content=choice, model=model_name, usage=usage, raw=resp)
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                logger.warning("LLM chat attempt %s failed: %s", attempt + 1, exc)
                await asyncio.sleep(0.5 * (attempt + 1))
        raise RuntimeError(f"LLM chat failed after retries: {last_err}")

    async def stream(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        model_name = model or self.default_model
        stream = await self.client.chat.completions.create(
            model=model_name,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
            stream=True,
            **kwargs,
        )
        async for event in stream:
            if not event.choices:
                continue
            delta = event.choices[0].delta.content
            if delta:
                yield delta
