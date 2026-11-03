"""Query IR → 逻辑 SQL 模板（仅测试/离线 demo；业务引擎走 LLM，不调用本模块）。"""

from __future__ import annotations

from datetime import date, timedelta

from gridmind.nl2sql.query_ir import QueryIR


def compile_logical_sql(ir: QueryIR) -> str:
    """把 Query IR 编译成「对语义模型」的逻辑 SQL。

    约定：FROM/JOIN 使用 MDL model 名（本演示中与物理表同名）。
    真正落到可执行 SQL 由 wren-core transform_sql 完成。
    """
    if ir.metric == "max_temperature":
        where = _day_where("telemetry_daily.day", ir.time_range)
        return f"""
SELECT stations.name AS station, MAX(telemetry_daily.max_temp_c) AS max_temp_c
FROM telemetry_daily
JOIN stations ON stations.station_id = telemetry_daily.station_id
{where}
GROUP BY stations.name
ORDER BY max_temp_c DESC
LIMIT {ir.limit}
""".strip()

    if ir.metric == "avg_temperature":
        where = _day_where("telemetry_daily.day", ir.time_range)
        return f"""
SELECT stations.name AS station, AVG(telemetry_daily.avg_temp_c) AS avg_temp_c
FROM telemetry_daily
JOIN stations ON stations.station_id = telemetry_daily.station_id
{where}
GROUP BY stations.name
ORDER BY avg_temp_c DESC
LIMIT {ir.limit}
""".strip()

    if ir.metric == "online_device_count":
        if ir.dimensions == ["region"]:
            return """
SELECT devices.region, COUNT(*) AS online_device_count
FROM devices
WHERE devices.status = 'online'
GROUP BY devices.region
ORDER BY online_device_count DESC
LIMIT 100
""".strip()
        return """
SELECT COUNT(*) AS online_device_count
FROM devices
WHERE devices.status = 'online'
""".strip()

    if ir.metric == "offline_device_count":
        if ir.dimensions == ["region"]:
            return """
SELECT devices.region, COUNT(*) AS offline_device_count
FROM devices
WHERE devices.status = 'offline'
GROUP BY devices.region
ORDER BY offline_device_count DESC
LIMIT 100
""".strip()
        return """
SELECT COUNT(*) AS offline_device_count
FROM devices
WHERE devices.status = 'offline'
""".strip()

    if ir.metric == "critical_alarm_count":
        region_filter = ""
        if ir.filters.get("region"):
            region_filter = f"AND devices.region = '{ir.filters['region']}'"
        if ir.dimensions == ["region"]:
            return f"""
SELECT devices.region, COUNT(DISTINCT alarms.alarm_id) AS critical_alarm_count
FROM alarms
JOIN devices ON devices.device_id = alarms.device_id
WHERE alarms.level = '严重' {region_filter}
GROUP BY devices.region
ORDER BY critical_alarm_count DESC
LIMIT 100
""".strip()
        return f"""
SELECT alarms.level, COUNT(DISTINCT alarms.alarm_id) AS critical_alarm_count
FROM alarms
JOIN devices ON devices.device_id = alarms.device_id
WHERE alarms.level = '严重' {region_filter}
GROUP BY alarms.level
LIMIT 100
""".strip()

    if ir.intent == "compare" and ir.metric == "alarm_count":
        month_start = date.today().replace(day=1)
        prev_month_end = month_start - timedelta(days=1)
        prev_month_start = prev_month_end.replace(day=1)
        return f"""
SELECT
  CASE
    WHEN alarms.occurred_at >= '{month_start.isoformat()}' THEN 'this_month'
    ELSE 'last_month'
  END AS period,
  COUNT(DISTINCT alarms.alarm_id) AS alarm_count
FROM alarms
WHERE alarms.occurred_at >= '{prev_month_start.isoformat()}'
GROUP BY period
ORDER BY period
""".strip()

    if ir.intent == "rank" and ir.metric == "alarm_count":
        days = 7 if ir.time_range == "last_7_days" else 30
        since = (date.today() - timedelta(days=days)).isoformat()
        return f"""
SELECT devices.device_id, devices.name, COUNT(DISTINCT alarms.alarm_id) AS alarm_count
FROM alarms
JOIN devices ON devices.device_id = alarms.device_id
WHERE alarms.occurred_at >= '{since}'
GROUP BY devices.device_id, devices.name
ORDER BY alarm_count DESC
LIMIT {ir.limit}
""".strip()

    if ir.metric == "alarm_count" and ir.dimensions == ["level"]:
        return """
SELECT alarms.level, COUNT(DISTINCT alarms.alarm_id) AS alarm_count
FROM alarms
GROUP BY alarms.level
ORDER BY alarm_count DESC
LIMIT 100
""".strip()

    if ir.metric == "alarm_count" and ir.dimensions == ["region"]:
        return """
SELECT devices.region, COUNT(DISTINCT alarms.alarm_id) AS alarm_count
FROM alarms
JOIN devices ON devices.device_id = alarms.device_id
GROUP BY devices.region
ORDER BY alarm_count DESC
LIMIT 100
""".strip()

    if ir.metric == "alarm_count":
        return """
SELECT COUNT(DISTINCT alarms.alarm_id) AS alarm_count
FROM alarms
""".strip()

    return """
SELECT devices.device_id, devices.name, devices.region, devices.status
FROM devices
LIMIT 20
""".strip()


# 兼容旧名：历史上叫 compile_sql，现语义为逻辑 SQL
compile_sql = compile_logical_sql


def _day_where(column: str, time_range: str | None) -> str:
    if time_range != "yesterday":
        return ""
    day = (date.today() - timedelta(days=1)).isoformat()
    return f"WHERE {column} = '{day}'"
