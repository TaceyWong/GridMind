from __future__ import annotations

from gridmind.graph.state import ChatState
from gridmind.nl2sql.engine import get_nl2sql_engine


async def execute_nl2sql(state: ChatState) -> ChatState:
    engine = get_nl2sql_engine()
    result = await engine.run(state["question"], use_llm=True)
    rows = result["rows"]
    preview = rows[:5]
    answer = (
        f"查询口径：{result['summary']}\n"
        f"SQL：{result['sql']}\n"
        f"结果预览：{preview}"
    )
    events = list(state.get("events", []))
    events.append({"type": "nl2sql", "sql": result["sql"], "row_count": len(rows)})
    intermediate = list(state.get("intermediate", []))
    intermediate.append(answer)
    return {
        "sql": result["sql"],
        "query_summary": result["summary"],
        "query_rows": rows,
        "answer": answer,
        "events": events,
        "intermediate": intermediate,
    }  # type: ignore[return-value]
