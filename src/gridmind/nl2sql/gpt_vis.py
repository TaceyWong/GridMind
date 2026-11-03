"""把查询结果转成 GPT-Vis Markdown fence，供聊天流式渲染。"""

from __future__ import annotations

from typing import Any


def rows_to_gpt_vis(
    rows: list[dict[str, Any]],
    *,
    chart: dict[str, Any] | None = None,
    intent: str | None = None,
    metric: str | None = None,
) -> str:
    if not rows:
        return ""

    keys = list(rows[0].keys())
    if len(keys) < 2:
        return ""

    chart_type = _pick_type(rows, chart=chart, intent=intent, metric=metric)
    if chart_type == "table":
        return ""

    cat_key = (chart or {}).get("x") or keys[0]
    val_key = (chart or {}).get("y") or _pick_value_key(keys, rows)
    if cat_key not in rows[0] or val_key not in rows[0]:
        cat_key, val_key = keys[0], keys[1]

    lines = [f"vis {chart_type}", "data"]
    for row in rows[:24]:
        cat = _fmt_label(row.get(cat_key))
        val = _fmt_number(row.get(val_key))
        if val is None:
            continue
        # line 用 time 字段更自然；其余用 category
        if chart_type == "line":
            lines.append(f"  - time {cat}")
        else:
            lines.append(f"  - category {cat}")
        lines.append(f"    value {val}")

    if len(lines) <= 2:
        return ""

    if chart_type == "pie":
        lines.append("innerRadius: 0.58")
    elif metric:
        lines.append(f"axisYTitle: {_axis_title(metric)}")

    body = "\n".join(lines)
    return f"```gpt-vis\n{body}\n```"


def build_nl2sql_answer(
    *,
    summary: dict[str, Any] | None,
    sql: str | None,
    rows: list[dict[str, Any]],
    chart: dict[str, Any] | None = None,
    intent: str | None = None,
    metric: str | None = None,
) -> str:
    """面向聊天的问数回答：结论 + GPT-Vis + 简要口径。"""
    summary = summary or {}
    metric_name = metric or summary.get("metric") or "指标"
    n = len(rows)
    vis = rows_to_gpt_vis(rows, chart=chart, intent=intent, metric=str(metric_name))

    parts = [
        f"已按问数分析查出 **{n}** 条结果。",
    ]
    if summary.get("definition"):
        parts.append(f"口径：{summary['definition']}")
    elif summary.get("time_range") or summary.get("dimensions"):
        bits = []
        if summary.get("time_range"):
            bits.append(f"时间={summary['time_range']}")
        if summary.get("dimensions"):
            bits.append(f"维度={','.join(summary['dimensions'])}")
        if summary.get("metric"):
            bits.append(f"指标={summary['metric']}")
        if bits:
            parts.append("查询摘要：" + "；".join(bits))

    if vis:
        parts.append("")
        parts.append(vis)
    elif rows:
        preview = rows[:5]
        parts.append(f"结果预览：{preview}")

    if sql:
        parts.append("")
        parts.append(f"生成 SQL：`{sql}`")

    return "\n".join(parts).strip()


def _pick_type(
    rows: list[dict[str, Any]],
    *,
    chart: dict[str, Any] | None,
    intent: str | None,
    metric: str | None,
) -> str:
    declared = (chart or {}).get("type")
    if declared == "table":
        return "table"
    if declared in {"pie", "line", "column", "bar"}:
        return "column" if declared == "bar" else str(declared)

    intent = (intent or "").lower()
    metric = (metric or "").lower()
    n = len(rows)
    first_key = list(rows[0].keys())[0].lower()

    if intent == "compare" or "month" in first_key or "day" in first_key or "time" in first_key:
        return "line" if n >= 3 else "column"
    if "temp" in metric:
        return "column"
    if n <= 6 and (intent == "status" or "alarm" in metric):
        return "pie"
    if intent == "rank" or n >= 3:
        return "column"
    if n <= 5:
        return "pie"
    return "column"


def _pick_value_key(keys: list[str], rows: list[dict[str, Any]]) -> str:
    for key in keys[1:]:
        if _fmt_number(rows[0].get(key)) is not None:
            return key
    return keys[1]


def _fmt_label(value: Any) -> str:
    text = str(value if value is not None else "")
    text = text.replace("\n", " ").strip()
    return text or "-"


def _fmt_number(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if value is None:
        return None
    try:
        text = str(value).strip()
        if not text:
            return None
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return None


def _axis_title(metric: str) -> str:
    mapping = {
        "alarm_count": "告警数量",
        "max_temperature": "最高温度 ℃",
        "online_device_count": "在线设备数",
    }
    return mapping.get(metric, metric)
