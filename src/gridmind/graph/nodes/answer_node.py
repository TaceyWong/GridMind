from __future__ import annotations

from gridmind.graph.state import ChatState
from gridmind.llm.gateway import get_llm_gateway
from gridmind.llm.prompts.answer import ANSWER_SYSTEM
from gridmind.llm.providers import ChatMessage


async def generate_answer(state: ChatState) -> ChatState:
    if state.get("answer") and get_llm_gateway().default_provider == "mock":
        events = list(state.get("events", []))
        events.append({"type": "answer", "mode": "passthrough"})
        return {"events": events}  # type: ignore[return-value]

    gateway = get_llm_gateway()
    if gateway.default_provider == "mock":
        return {}

    context_parts = []
    if state.get("rag_context"):
        context_parts.append(f"RAG:\n{state['rag_context']}")
    if state.get("query_rows") is not None:
        context_parts.append(f"SQL: {state.get('sql')}\nRows: {state.get('query_rows')[:10]}")
    if state.get("tool_result") is not None:
        context_parts.append(f"Tool: {state.get('tool_name')}\nResult: {state.get('tool_result')}")
    if state.get("intermediate"):
        context_parts.append("Intermediate:\n" + "\n".join(state["intermediate"]))

    result = await gateway.chat(
        [
            ChatMessage(role="system", content=ANSWER_SYSTEM),
            ChatMessage(
                role="user",
                content=f"问题：{state['question']}\n\n材料：\n" + "\n\n".join(context_parts),
            ),
        ],
        provider=state.get("provider"),
        model=state.get("model"),
    )
    events = list(state.get("events", []))
    events.append({"type": "answer", "mode": "llm"})
    return {"answer": result.content, "events": events}  # type: ignore[return-value]
