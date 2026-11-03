from __future__ import annotations

import logging
from typing import Any

import sqlglot

from gridmind.core.config import settings
from gridmind.llm.gateway import get_llm_gateway
from gridmind.llm.prompts.nl2sql import NL2SQL_SYSTEM
from gridmind.llm.providers import ChatMessage
from gridmind.nl2sql.executor import execute_sql, init_demo_db, memory_timeseries_join
from gridmind.nl2sql.gpt_vis import rows_to_gpt_vis
from gridmind.nl2sql.mdl import plan_sql_with_wren
from gridmind.nl2sql.planner import plan_from_question
from gridmind.nl2sql.query_ir import QueryIR
from gridmind.nl2sql.semantic import load_semantic_model, schema_prompt
from gridmind.nl2sql.sql_guard import validate_sql

logger = logging.getLogger(__name__)


class Nl2SqlError(RuntimeError):
    """问数失败（缺 LLM、SQL 无效、Wren 展开失败等）。"""


class Nl2SqlEngine:
    def __init__(self) -> None:
        init_demo_db()
        self.model = load_semantic_model()

    async def run(
        self,
        question: str,
        *,
        metric: str | None = None,
        dimensions: list[str] | None = None,
    ) -> dict[str, Any]:
        """主路径：LLM 逻辑 SQL → Wren 语义展开 → 校验执行。无模板、无回退。"""
        _require_llm()

        ir = plan_from_question(question, metric=metric, dimensions=dimensions)
        logical_sql = await _generate_logical_sql(
            question=question,
            ir=ir,
            model=self.model,
        )
        physical_sql, planner = _logical_to_physical(logical_sql)
        safe_sql = validate_sql(physical_sql, dialect="sqlite")
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
            "planner": planner,
            "logical_sql": logical_sql,
        }
        return {
            "question": question,
            "ir": ir.model_dump(),
            "logical_sql": logical_sql,
            "sql": safe_sql,
            "summary": summary,
            "rows": rows,
            "chart": chart,
            "gpt_vis": gpt_vis,
        }

    async def alarm_top_devices(self, limit: int = 5) -> list[dict[str, Any]]:
        result = await self.run(f"查询过去7天告警数量排名前{limit}的设备")
        return result["rows"][:limit]

    async def analyze_devices_temperature(self, device_ids: list[str]) -> list[dict[str, Any]]:
        return memory_timeseries_join(device_ids, hours=24 * 7)


def _require_llm() -> None:
    gateway = get_llm_gateway()
    if not settings.has_llm_key or gateway.default_provider == "mock":
        raise Nl2SqlError("问数需要配置可用 LLM（设置 LLM_API_KEY），当前无模型可用")


def _logical_to_physical(logical_sql: str) -> tuple[str, str]:
    """Wren 展开逻辑 SQL；失败直接报错，不回退模板/直连。"""
    if not settings.wren_core_enabled:
        raise Nl2SqlError("Wren Core 未启用（WREN_CORE_ENABLED=true），无法展开语义 SQL")

    planned = plan_sql_with_wren(logical_sql)
    if not planned:
        raise Nl2SqlError("Wren 未能展开逻辑 SQL")

    try:
        sqlite_sql = sqlglot.transpile(planned, read="duckdb", write="sqlite")[0]
    except Exception as exc:
        raise Nl2SqlError(f"逻辑 SQL 方言转换失败: {exc}") from exc

    try:
        safe = validate_sql(sqlite_sql, dialect="sqlite")
        execute_sql(safe)
        return safe, "wren-core"
    except Exception as exc:
        raise Nl2SqlError(f"Wren 展开结果无法在 SQLite 执行: {exc}") from exc


async def _generate_logical_sql(
    *,
    question: str,
    ir: QueryIR,
    model: dict[str, Any],
) -> str:
    gateway = get_llm_gateway()
    prompt = (
        f"{schema_prompt(model)}\n\n"
        f"QueryIR（意图约束，可参考）: {ir.model_dump_json()}\n"
        f"用户问题: {question}\n"
        "请直接生成对语义模型的逻辑 SQL。"
    )
    result = await gateway.chat(
        [
            ChatMessage(role="system", content=NL2SQL_SYSTEM),
            ChatMessage(role="user", content=prompt),
        ]
    )
    candidate = _extract_sql(result.content)
    if not candidate:
        raise Nl2SqlError("LLM 未返回有效逻辑 SQL（需以 SELECT/WITH 开头）")
    return candidate


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

    x_key = keys[0]
    y_key = keys[1]
    for key in keys[1:]:
        sample = rows[0].get(key)
        if isinstance(sample, (int, float)) and not isinstance(sample, bool):
            y_key = key
            break

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
        "x": x_key,
        "y": y_key,
        "data": rows,
    }


_engine: Nl2SqlEngine | None = None


def get_nl2sql_engine() -> Nl2SqlEngine:
    global _engine
    if _engine is None:
        _engine = Nl2SqlEngine()
    return _engine
