from __future__ import annotations

from gridmind.nl2sql.query_ir import QueryIR
from gridmind.nl2sql.semantic import load_semantic_model


def plan_from_question(
    question: str,
    *,
    metric: str | None = None,
    dimensions: list[str] | None = None,
) -> QueryIR:
    """Rule-based planner；可选强制口径（metric/dimensions）。"""
    ir = QueryIR(raw_question=question, limit=100)
    model = load_semantic_model()
    metrics = model.get("metrics") or {}

    if metric:
        if metric not in metrics:
            raise ValueError(f"未知指标: {metric}")
        ir.metric = metric
        ir.intent = _intent_for_metric(metric, question)
        if dimensions:
            ir.dimensions = list(dimensions)
        else:
            ir.dimensions = list(metrics[metric].get("default_dimensions") or [])
        ir.time_range = _time_range(question, metric)
        if ir.intent == "rank":
            ir.order_by = f"{metric} desc"
            ir.limit = 10
        _apply_filters(ir, question)
        return ir

    # —— 自动识别 ——
    if any(k in question for k in ("对比", "本月", "上月")):
        ir.intent = "compare"
        ir.metric = "alarm_count"
        ir.dimensions = ["month"]
        ir.time_range = "this_month_vs_last_month"
    elif any(k in question for k in ("离线", "掉线")):
        ir.intent = "status"
        ir.metric = "offline_device_count"
        ir.dimensions = ["region"] if "区域" in question else []
    elif any(k in question for k in ("在线", "在线设备", "在运")):
        ir.intent = "status"
        ir.metric = "online_device_count"
    elif any(k in question for k in ("严重告警", "危急")):
        ir.intent = "metric"
        ir.metric = "critical_alarm_count"
        ir.dimensions = ["region"] if "区域" in question else ["level"]
    elif any(k in question for k in ("平均温度", "均温")):
        ir.intent = "metric"
        ir.metric = "avg_temperature"
        ir.dimensions = ["station_id"]
        ir.time_range = "yesterday" if "昨天" in question else "recent"
    elif any(k in question for k in ("排名", "最多", "top", "前10", "前五", "前5", "前三")):
        ir.intent = "rank"
        ir.metric = "alarm_count"
        ir.dimensions = ["device_id"]
        ir.order_by = "alarm_count desc"
        ir.limit = 10
        ir.time_range = "last_7_days" if "7" in question or "七" in question else "recent"
    elif any(k in question for k in ("最高温度", "峰值温度", "温度")):
        ir.intent = "metric"
        ir.metric = "max_temperature"
        ir.dimensions = ["station_id"]
        ir.time_range = "yesterday" if "昨天" in question else "recent"
    elif any(k in question for k in ("等级", "占比")) and "告警" in question:
        ir.intent = "metric"
        ir.metric = "alarm_count"
        ir.dimensions = ["level"]
    elif "告警" in question:
        ir.intent = "metric"
        ir.metric = "alarm_count"
        if "区域" in question:
            ir.dimensions = ["region"]
    else:
        # 同义词兜底
        hit = _match_synonym(question, metrics)
        if hit:
            ir.intent = _intent_for_metric(hit, question)
            ir.metric = hit
            ir.dimensions = list(metrics[hit].get("default_dimensions") or [])
            ir.time_range = _time_range(question, hit)
        else:
            ir.intent = "unknown"

    if dimensions is not None:
        ir.dimensions = list(dimensions)

    _apply_filters(ir, question)
    return ir


def _intent_for_metric(metric: str, question: str) -> str:
    if any(k in question for k in ("排名", "最多", "top", "前")):
        return "rank"
    if any(k in question for k in ("对比", "本月", "上月")):
        return "compare"
    if metric in {"online_device_count", "offline_device_count"}:
        return "status"
    return "metric"


def _time_range(question: str, metric: str) -> str | None:
    if "昨天" in question:
        return "yesterday"
    if "7" in question or "七" in question:
        return "last_7_days"
    if metric in {"max_temperature", "avg_temperature"}:
        return "recent"
    return None


def _apply_filters(ir: QueryIR, question: str) -> None:
    if "华东" in question:
        ir.filters["region"] = "华东"
    if "华北" in question:
        ir.filters["region"] = "华北"
    if "华南" in question:
        ir.filters["region"] = "华南"
    if "西南" in question:
        ir.filters["region"] = "西南"


def _match_synonym(question: str, metrics: dict) -> str | None:
    for key, meta in metrics.items():
        label = str(meta.get("label") or "")
        if label and label in question:
            return key
        for syn in meta.get("synonyms") or []:
            if syn and syn in question:
                return key
    return None
