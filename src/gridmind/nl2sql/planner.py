from __future__ import annotations

from gridmind.nl2sql.query_ir import QueryIR


def plan_from_question(question: str) -> QueryIR:
    """Rule-based planner for offline demos; LLM can refine later."""
    q = question.lower()
    ir = QueryIR(raw_question=question, limit=100)

    if any(k in question for k in ("对比", "本月", "上月")):
        ir.intent = "compare"
        ir.metric = "alarm_count"
        ir.dimensions = ["month"]
        ir.time_range = "this_month_vs_last_month"
    elif any(k in question for k in ("排名", "最多", "top", "前")):
        ir.intent = "rank"
        ir.metric = "alarm_count"
        ir.dimensions = ["device_id"]
        ir.order_by = "alarm_count desc"
        ir.limit = 10
        ir.time_range = "last_7_days" if "7" in question or "七" in question else "recent"
    elif any(k in question for k in ("最高温度", "温度")):
        ir.intent = "metric"
        ir.metric = "max_temperature"
        ir.dimensions = ["station_id"]
        ir.time_range = "yesterday" if "昨天" in question else "recent"
    elif any(k in question for k in ("在线", "在线设备")):
        ir.intent = "status"
        ir.metric = "online_device_count"
    elif "告警" in question:
        ir.intent = "metric"
        ir.metric = "alarm_count"
        if "区域" in question:
            ir.dimensions = ["region"]
    else:
        ir.intent = "unknown"

    if "华东" in question:
        ir.filters["region"] = "华东"
    return ir
