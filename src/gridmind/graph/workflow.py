from __future__ import annotations

from typing import Any, Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from gridmind.graph.nodes import (
    execute_hybrid,
    execute_mcp,
    execute_nl2sql,
    execute_rag,
    generate_answer,
    route_question,
)
from gridmind.graph.state import ChatState


def select_route(state: ChatState) -> Literal["rag", "nl2sql", "mcp", "hybrid"]:
    route = state.get("route", "rag")
    if route in {"rag", "nl2sql", "mcp", "hybrid"}:
        return route  # type: ignore[return-value]
    return "rag"


def build_chat_graph():
    builder = StateGraph(ChatState)
    builder.add_node("router", route_question)
    builder.add_node("rag", execute_rag)
    builder.add_node("nl2sql", execute_nl2sql)
    builder.add_node("mcp", execute_mcp)
    builder.add_node("hybrid", execute_hybrid)
    builder.add_node("answer", generate_answer)

    builder.add_edge(START, "router")
    builder.add_conditional_edges(
        "router",
        select_route,
        {
            "rag": "rag",
            "nl2sql": "nl2sql",
            "mcp": "mcp",
            "hybrid": "hybrid",
        },
    )
    builder.add_edge("rag", "answer")
    builder.add_edge("nl2sql", "answer")
    builder.add_edge("mcp", "answer")
    builder.add_edge("hybrid", "answer")
    builder.add_edge("answer", END)

    memory = MemorySaver()
    return builder.compile(checkpointer=memory)


_chat_graph = None


def get_chat_graph():
    global _chat_graph
    if _chat_graph is None:
        _chat_graph = build_chat_graph()
    return _chat_graph


async def run_chat(
    question: str,
    *,
    session_id: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    user_id: str = "demo-user",
    tenant_id: str = "demo-tenant",
) -> dict[str, Any]:
    graph = get_chat_graph()
    thread_id = session_id or "default"
    result = await graph.ainvoke(
        {
            "question": question,
            "session_id": session_id,
            "provider": provider,
            "model": model,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "messages": [],
            "events": [],
            "intermediate": [],
            "sources": [],
        },
        config={"configurable": {"thread_id": thread_id}},
    )
    return result
