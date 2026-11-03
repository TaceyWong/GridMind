from __future__ import annotations

from typing import Any

from gridmind.llm.gateway import get_llm_gateway
from gridmind.llm.prompts.nl2sql import NL2SQL_SYSTEM
from gridmind.llm.providers import ChatMessage
from gridmind.nl2sql.compiler import compile_sql
from gridmind.nl2sql.executor import execute_sql, init_demo_db, memory_timeseries_join
from gridmind.nl2sql.gpt_vis import rows_to_gpt_vis
from gridmind.nl2sql.planner import plan_from_question
from gridmind.nl2sql.query_ir import QueryIR
from gridmind.nl2sql.semantic import load_semantic_model, schema_prompt
from gridmind.nl2sql.sql_guard import validate_sql


class Nl2SqlEngine:
    def __init__(self) -> None:
        init_demo_db()
        self.model = load_semantic_model()

    async def run(self, question: str, *, use_llm: bool = True) -> dict[str, Any]:
        ir = plan_from_question(question)
        sql = compile_sql(ir)

        if use_llm:
            gateway = get_llm_gateway()
            if gateway.default_provider != "mock":
                prompt = (
                    f"{schema_prompt(self.model)}\n\n"
                    f"QueryIR: {ir.model_dump_json()}\n"
                    f"参考 SQL:\n{sql}\n"
                    f"用户问题: {question}"
                )
                result = await gateway.chat(
                    [
                        ChatMessage(role="system", content=NL2SQL_SYSTEM),
                        ChatMessage(role="user", content=prompt),
                    ]
                )
                candidate = _extract_sql(result.content)
                if candidate:
                    sql = candidate

        safe_sql = validate_sql(sql, dialect="sqlite")
        rows = execute_sql(safe_sql)
        chart = _to_chart(ir, rows)
        gpt_vis = rows_to_gpt_vis(
            rows,
            chart=chart,
            intent=ir.intent,
            metric=ir.metric,
        )
        summary = {
            "time_range": ir.time_range,
            "metric": ir.metric,
            "dimensions": ir.dimensions,
            "filters": ir.filters,
            "definition": self.model.get("metrics", {}).get(ir.metric or "", {}).get(
                "definition", ""
            ),
        }
        return {
            "question": question,
            "ir": ir.model_dump(),
            "sql": safe_sql,
            "summary": summary,
            "rows": rows,
            "chart": chart,
            "gpt_vis": gpt_vis,
        }

    async def alarm_top_devices(self, limit: int = 5) -> list[dict[str, Any]]:
        result = await self.run(f"查询过去7天告警数量排名前{limit}的设备", use_llm=False)
        return result["rows"][:limit]

    async def analyze_devices_temperature(self, device_ids: list[str]) -> list[dict[str, Any]]:
        return memory_timeseries_join(device_ids, hours=24 * 7)


def _extract_sql(text: str) -> str | None:
    text = text.strip()
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            cleaned = part.strip()
            if cleaned.startswith("sql"):
                cleaned = cleaned[3:].strip()
            if cleaned.lower().startswith(("select", "with")):
                return cleaned
    if text.lower().startswith(("select", "with")):
        return text
    return None


def _to_chart(ir: QueryIR, rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    keys = list(rows[0].keys())
    if len(keys) < 2:
        return {"type": "table", "columns": keys, "data": rows}

    chart_type = "column"
    if ir.intent == "compare" or (ir.dimensions and ir.dimensions[0] in {"month", "day"}):
        chart_type = "line"
    elif ir.intent == "status" and len(rows) <= 6:
        chart_type = "pie"
    elif ir.intent == "rank":
        chart_type = "column"
    elif ir.metric and "temp" in ir.metric:
        chart_type = "column"

    return {
        "type": chart_type,
        "x": keys[0],
        "y": keys[1],
        "data": rows,
    }


_engine: Nl2SqlEngine | None = None


def get_nl2sql_engine() -> Nl2SqlEngine:
    global _engine
    if _engine is None:
        _engine = Nl2SqlEngine()
    return _engine
