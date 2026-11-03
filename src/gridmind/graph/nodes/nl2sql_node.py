from __future__ import annotations

from gridmind.graph.state import ChatState
from gridmind.nl2sql.engine import Nl2SqlError, get_nl2sql_engine
from gridmind.nl2sql.gpt_vis import build_nl2sql_answer


async def execute_nl2sql(state: ChatState) -> ChatState:
    engine = get_nl2sql_engine()
    events = list(state.get("events", []))
    try:
        result = await engine.run(
            state["question"],
            metric=state.get("preferred_metric"),
            dimensions=state.get("preferred_dimensions") or None,
        )
    except Nl2SqlError as exc:
        msg = f"问数失败：{exc}"
        events.append({"type": "error", "message": str(exc), "route": "nl2sql"})
        intermediate = list(state.get("intermediate", []))
        intermediate.append(msg)
        return {
            "answer": msg,
            "events": events,
            "intermediate": intermediate,
            "query_rows": [],
            "sql": None,
            "query_summary": {"error": str(exc), "planner": None},
        }  # type: ignore[return-value]

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
