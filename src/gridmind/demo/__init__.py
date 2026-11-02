"""GridMind 独立学习示例。

运行方式（在仓库根目录）::

    uv run python -m gridmind.demo                  # 列出全部
    uv run python -m gridmind.demo pydantic_settings
    uv run python -m gridmind.demo openai_sdk
    uv run python -m gridmind.demo litellm
    uv run python -m gridmind.demo langchain
    uv run python -m gridmind.demo langgraph
    uv run python -m gridmind.demo llamaindex
    uv run python -m gridmind.demo integrated
"""

DEMOS = (
    "pydantic_settings",
    "pydantic",
    "openai_sdk",
    "litellm",
    "langchain",
    "langgraph",
    "llamaindex",
    "integrated",
)
