"""学习示例 4：LangChain（langchain-openai + LCEL）

目标：
- ChatOpenAI
- ChatPromptTemplate
- LCEL：prompt | llm
- Structured 思路（简单字符串输出）

运行::

    uv run python -m gridmind.demo langchain
"""

from __future__ import annotations

import asyncio

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from gridmind.demo._common import api_key, banner, base_url, has_api_key, model_name, need_key_hint


async def real_chain() -> None:
    llm = ChatOpenAI(
        model=model_name().split("/")[-1],
        api_key=api_key(),
        base_url=base_url(),
        temperature=0,
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "你是电网助教。用不超过两句话回答。"),
            ("human", "问题：{question}"),
        ]
    )
    chain = prompt | llm | StrOutputParser()
    answer = await chain.ainvoke({"question": "什么是 LangChain？"})
    print("LCEL 输出:", answer)


async def mock_chain() -> None:
    need_key_hint()
    print("Mock LCEL: prompt | ChatOpenAI | StrOutputParser")
    print("LangChain 价值：Prompt/模型/解析器可组合，便于接 Tool、结构化输出。")


def main() -> None:
    banner("4) LangChain")
    if has_api_key():
        asyncio.run(real_chain())
    else:
        asyncio.run(mock_chain())
    print("\n要点：LangChain 管组件抽象；复杂流程编排更适合 LangGraph。")


if __name__ == "__main__":
    main()
