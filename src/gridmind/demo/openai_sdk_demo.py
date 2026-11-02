"""学习示例 2：OpenAI Python SDK

目标：
- AsyncOpenAI / OpenAI 客户端
- chat.completions 非流式与流式
- 兼容自定义 base_url（DeepSeek / 本地网关）

运行::

    uv run python -m gridmind.demo openai_sdk
"""

from __future__ import annotations

import asyncio

from openai import AsyncOpenAI

from gridmind.demo._common import api_key, banner, base_url, has_api_key, model_name, need_key_hint


async def real_chat() -> None:
    client = AsyncOpenAI(api_key=api_key(), base_url=base_url())
    model = model_name()
    print(f"调用 {base_url()} model={model}")

    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "你是简洁的助教，用一句话回答。"},
            {"role": "user", "content": "用一句话解释什么是 OpenAI SDK。"},
        ],
        temperature=0,
    )
    print("非流式:", resp.choices[0].message.content)

    print("流式:", end=" ", flush=True)
    stream = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "数到 3。"}],
        stream=True,
    )
    async for event in stream:
        delta = event.choices[0].delta.content
        if delta:
            print(delta, end="", flush=True)
    print()


async def mock_chat() -> None:
    need_key_hint()
    print("Mock 非流式: OpenAI SDK 用 HTTP 调 /chat/completions，可换 base_url。")
    print("Mock 流式: stream=True 时按 chunk 返回 delta.content。")


def main() -> None:
    banner("2) OpenAI SDK")
    if has_api_key():
        asyncio.run(real_chat())
    else:
        asyncio.run(mock_chat())
    print("\n要点：SDK 负责协议；多厂商路由通常再包一层 LiteLLM / 网关。")


if __name__ == "__main__":
    main()
