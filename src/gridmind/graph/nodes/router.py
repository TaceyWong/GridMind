from __future__ import annotations

from gridmind.graph.state import ChatState
from gridmind.llm.gateway import get_llm_gateway
from gridmind.llm.prompts.router import ROUTER_SYSTEM
from gridmind.llm.providers import ChatMessage


def rule_route(question: str) -> str:
    q = question
    if any(k in q for k in ("说明书", "手册", "定义", "口径", "知识", "如何定义", "什么是")):
        return "rag"
    if any(
        k in q
        for k in (
            "统计",
            "排名",
            "最多",
            "趋势",
            "对比",
            "多少",
            "最高温度",
            "告警数量",
            "在线设备",
            "各区域",
            "各变电站",
        )
    ):
        if any(k in q for k in ("分析", "异常", "温度变化", "综合")):
            return "hybrid"
        return "nl2sql"
    if any(k in q for k in ("设备", "遥测", "状态", "告警", "传感器")):
        if any(k in q for k in ("昨天", "过去", "排名", "最多", "温度变化")):
            return "hybrid"
        return "mcp"
    return "rag"


async def route_question(state: ChatState) -> ChatState:
    question = state["question"]
    route = rule_route(question)
    gateway = get_llm_gateway()
    if gateway.default_provider != "mock":
        result = await gateway.chat(
            [
                ChatMessage(role="system", content=ROUTER_SYSTEM),
                ChatMessage(role="user", content=question),
            ],
            provider=state.get("provider"),
            model=state.get("model"),
        )
        text = result.content.strip().lower()
        for candidate in ("hybrid", "nl2sql", "mcp", "rag"):
            if candidate in text:
                route = candidate
                break
    events = list(state.get("events", []))
    events.append({"type": "route", "route": route})
    return {"route": route, "events": events}  # type: ignore[return-value]
