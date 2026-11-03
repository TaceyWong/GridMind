from __future__ import annotations

from gridmind.graph.state import ChatState
from gridmind.nl2sql.engine import get_nl2sql_engine
from gridmind.nl2sql.gpt_vis import build_nl2sql_answer


async def execute_nl2sql(state: ChatState) -> ChatState:
    engine = get_nl2sql_engine()
    result = await engine.run(state["question"], use_llm=True)
    rows = result["rows"]
    ir = result.get("ir") or {}
    answer = build_nl2sql_answer(
        summary=result.get("summary"),
        sql=result.get("sql"),
        rows=rows,
        chart=result.get("chart"),
        intent=ir.get("intent"),
        metric=ir.get("metric"),
    )
    events = list(state.get("events", []))
    events.append(
        {
            "type": "nl2sql",
            "sql": result["sql"],
            "row_count": len(rows),
            "has_chart": bool(result.get("gpt_vis")),
        }
    )
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
