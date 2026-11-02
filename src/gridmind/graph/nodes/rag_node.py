from __future__ import annotations

from gridmind.graph.state import ChatState
from gridmind.llm.gateway import get_llm_gateway
from gridmind.llm.prompts.answer import ANSWER_SYSTEM
from gridmind.llm.providers import ChatMessage
from gridmind.rag.retriever import get_knowledge_store


async def execute_rag(state: ChatState) -> ChatState:
    store = get_knowledge_store()
    payload = await store.answer(state["question"])
    answer = payload["answer"]
    gateway = get_llm_gateway()
    if gateway.default_provider != "mock" and payload.get("context"):
        result = await gateway.chat(
            [
                ChatMessage(role="system", content=ANSWER_SYSTEM),
                ChatMessage(
                    role="user",
                    content=(
                        f"问题：{state['question']}\n\n检索上下文：\n{payload['context']}"
                    ),
                ),
            ],
            provider=state.get("provider"),
            model=state.get("model"),
        )
        answer = result.content
    events = list(state.get("events", []))
    events.append({"type": "rag", "sources": len(payload.get("sources", []))})
    return {
        "rag_context": payload.get("context", ""),
        "sources": payload.get("sources", []),
        "answer": answer,
        "events": events,
    }  # type: ignore[return-value]
