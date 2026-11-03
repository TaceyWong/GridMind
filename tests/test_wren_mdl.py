import asyncio

import pytest

from gridmind.nl2sql.compiler import compile_logical_sql
from gridmind.nl2sql.engine import Nl2SqlEngine, Nl2SqlError
from gridmind.nl2sql.mdl import clear_wren_session_cache, grid_yaml_to_mdl, plan_sql_with_wren
from gridmind.nl2sql.planner import plan_from_question


def test_grid_yaml_to_mdl_has_models_and_relationships():
    mdl = grid_yaml_to_mdl()
    names = {m["name"] for m in mdl["models"]}
    assert {"stations", "devices", "alarms", "telemetry_daily"} <= names
    assert mdl["catalog"] == "gridmind"
    assert any(r["name"] == "alarms_device" for r in mdl["relationships"])


def test_wren_plans_logical_temperature_sql():
    clear_wren_session_cache()
    ir = plan_from_question("查询昨天各变电站的最高温度")
    logical = compile_logical_sql(ir)
    assert "FROM telemetry_daily" in logical
    assert "JOIN stations" in logical
    planned = plan_sql_with_wren(logical)
    assert planned is not None
    assert "telemetry_daily" in planned.lower()
    assert "stations" in planned.lower()


def test_engine_requires_llm():
    clear_wren_session_cache()

    async def _run() -> None:
        eng = Nl2SqlEngine()
        with pytest.raises(Nl2SqlError, match="LLM"):
            await eng.run("查询昨天各变电站的最高温度")

    asyncio.run(_run())
