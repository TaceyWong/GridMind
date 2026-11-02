"""学习示例 3：LiteLLM

目标：
- 统一 acompletion 接口
- 模型名带厂商前缀：openai/xxx、deepseek/xxx
- 与 OpenAI SDK 类似的 messages 结构

运行::

    uv run python -m gridmind.demo litellm
"""

from __future__ import annotations

import asyncio

import litellm

from gridmind.demo._common import api_key, banner, base_url, has_api_key, model_name, need_key_hint

litellm.suppress_debug_info = True


def to_litellm_model(raw: str) -> str:
    return raw if "/" in raw else f"openai/{raw}"


async def real_call() -> None:
    model = to_litellm_model(model_name())
    print(f"LiteLLM model={model} api_base={base_url()}")
    resp = await litellm.acompletion(
        model=model,
        messages=[{"role": "user", "content": "用一句话解释 LiteLLM 是做什么的。"}],
        api_key=api_key(),
        api_base=base_url(),
        temperature=0,
    )
    print("回复:", resp.choices[0].message.content)


async def mock_call() -> None:
    need_key_hint()
    print("Mock: litellm.acompletion(model='openai/gpt-4o-mini', messages=[...])")
    print("换厂商通常只改 model 前缀或 api_base，业务代码少改。")


def main() -> None:
    banner("3) LiteLLM")
    if has_api_key():
        asyncio.run(real_call())
    else:
        asyncio.run(mock_call())
    print("\n要点：LiteLLM = 多厂商路由器；langchain-openai = LangChain 的 ChatModel 适配。")


if __name__ == "__main__":
    main()
