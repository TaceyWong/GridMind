"""学习示例 7：综合 —— Settings + LiteLLM/LangChain + LangGraph + LlamaIndex

对应 GridMind 主链路的迷你版：
Settings 配模型 → LangGraph 路由 → RAG(LlamaIndex) / 直答(LangChain|Mock)

运行::

    uv run python -m gridmind.demo integrated
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from gridmind.demo._common import banner, has_api_key, need_key_hint


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[3] / ".env"),
        extra="ignore",
    )
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_base_url: str = Field(default="https://api.openai.com/v1", alias="LLM_BASE_URL")
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")


class State(TypedDict):
    question: str
    route: str
    context: str
    answer: str


def build_retriever():
    from llama_index.core import Document, Settings as LlamaSettings, VectorStoreIndex
    from llama_index.core.embeddings import BaseEmbedding

    class HashEmbedding(BaseEmbedding):
        def _embed(self, text: str) -> list[float]:
            vec = [0.0] * 32
            for ch in text.lower():
                vec[ord(ch) % 32] += 1.0
            norm = sum(v * v for v in vec) ** 0.5 or 1.0
            return [v / norm for v in vec]

        def _get_query_embedding(self, query: str) -> list[float]:
            return self._embed(query)

        def _get_text_embedding(self, text: str) -> list[float]:
            return self._embed(text)

        async def _aget_query_embedding(self, query: str) -> list[float]:
            return self._embed(query)

        async def _aget_text_embedding(self, text: str) -> list[float]:
            return self._embed(text)

    LlamaSettings.embed_model = HashEmbedding()
    LlamaSettings.llm = None
    docs = [
        Document(text="告警数量：按 alarm_id 去重。"),
        Document(text="GridMind 使用 LangGraph 做路由编排。"),
    ]
    return VectorStoreIndex.from_documents(docs).as_retriever(similarity_top_k=1)


RETRIEVER = None


def router(state: State) -> State:
    q = state["question"]
    route = "rag" if any(k in q for k in ("口径", "定义", "什么是", "告警数量")) else "chat"
    return {"route": route}


def rag_node(state: State) -> State:
    global RETRIEVER
    if RETRIEVER is None:
        RETRIEVER = build_retriever()
    hits = RETRIEVER.retrieve(state["question"])
    ctx = hits[0].get_content() if hits else ""
    return {"context": ctx, "answer": f"[RAG] 依据知识库：{ctx}"}


async def chat_node(state: State) -> State:
    settings = Settings()
    if not settings.llm_api_key.strip():
        return {"answer": f"[Mock/LangChain路径] 收到：{state['question']}"}

    # 有 Key：LangChain ChatOpenAI（底层 OpenAI 兼容；生产可换成 LiteLLM）
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        model=settings.llm_model.split("/")[-1],
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=0,
    )
    prompt = ChatPromptTemplate.from_messages([("human", "{q}")])
    msg = await (prompt | llm).ainvoke({"q": state["question"]})
    content = msg.content if isinstance(msg.content, str) else str(msg.content)
    return {"answer": f"[LangChain] {content}"}


def select(state: State) -> Literal["rag", "chat"]:
    return "rag" if state.get("route") == "rag" else "chat"  # type: ignore[return-value]


def build_app():
    g = StateGraph(State)
    g.add_node("router", router)
    g.add_node("rag", rag_node)
    g.add_node("chat", chat_node)
    g.add_edge(START, "router")
    g.add_conditional_edges("router", select, {"rag": "rag", "chat": "chat"})
    g.add_edge("rag", END)
    g.add_edge("chat", END)
    return g.compile()


async def main_async() -> None:
    banner("7) 综合：Settings + LangGraph + LlamaIndex + LangChain/LiteLLM")
    if not has_api_key():
        need_key_hint()

    app = build_app()
    for q in ("告警数量口径是什么？", "你好，介绍一下自己"):
        out = await app.ainvoke(
            {"question": q, "route": "", "context": "", "answer": ""}
        )
        print(f"Q: {q}")
        print(f"  route={out['route']}")
        print(f"  answer={out['answer']}")

    print("\n对应 GridMind：FastAPI 收请求 → LangGraph 编排 → RAG/NL2SQL/MCP 节点。")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
