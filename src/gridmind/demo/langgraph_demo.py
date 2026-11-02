"""学习示例 5：LangGraph

目标：
- StateGraph + TypedDict 状态
- 节点 / 边 / 条件边
- 最小 router → tool|direct → end

运行::

    uv run python -m gridmind.demo langgraph
"""

from __future__ import annotations

import asyncio
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph


class State(TypedDict):
    question: str
    route: str
    answer: str


def classify(state: State) -> State:
    q = state["question"]
    route = "tool" if any(k in q for k in ("查询", "统计", "设备")) else "direct"
    return {"route": route}


def call_tool(state: State) -> State:
    return {"answer": f"[tool] 已用规则工具处理：{state['question']}"}


def direct_answer(state: State) -> State:
    return {"answer": f"[direct] 这是概念题直接回答：{state['question']}"}


def select(state: State) -> Literal["tool", "direct"]:
    return "tool" if state.get("route") == "tool" else "direct"  # type: ignore[return-value]


def build_graph():
    g = StateGraph(State)
    g.add_node("classify", classify)
    g.add_node("tool", call_tool)
    g.add_node("direct", direct_answer)
    g.add_edge(START, "classify")
    g.add_conditional_edges("classify", select, {"tool": "tool", "direct": "direct"})
    g.add_edge("tool", END)
    g.add_edge("direct", END)
    return g.compile()


async def main_async() -> None:
    from gridmind.demo._common import banner

    banner("5) LangGraph")
    app = build_graph()
    for q in ("什么是向量检索？", "查询设备 DEV-001 状态"):
        result = await app.ainvoke({"question": q, "route": "", "answer": ""})
        print(f"Q: {q}")
        print(f"  route={result['route']} → {result['answer']}")
    print("\nMermaid:")
    print(app.get_graph().draw_mermaid())
    print("要点：LangGraph 管状态与分支；节点内部可再调 LangChain/LiteLLM/工具。")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
