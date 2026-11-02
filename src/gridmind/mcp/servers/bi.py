from __future__ import annotations

from typing import Any

from gridmind.mcp.registry import registry
from gridmind.nl2sql.engine import get_nl2sql_engine


async def nl2sql_query(question: str) -> dict[str, Any]:
    return await get_nl2sql_engine().run(question, use_llm=False)


async def alarm_top(limit: int = 5) -> list[dict[str, Any]]:
    return await get_nl2sql_engine().alarm_top_devices(limit=limit)


async def temperature_for_devices(device_ids: list[str]) -> list[dict[str, Any]]:
    return await get_nl2sql_engine().analyze_devices_temperature(device_ids)


def register_bi_tools() -> None:
    registry.register("bi", "nl2sql_query", "自然语言问数", nl2sql_query)
    registry.register("bi", "alarm_top", "告警设备排名", alarm_top)
    registry.register(
        "bi",
        "temperature_for_devices",
        "查询设备温度汇总（内存时序降级）",
        temperature_for_devices,
    )
