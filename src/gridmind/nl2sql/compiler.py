from __future__ import annotations

from gridmind.nl2sql.query_ir import QueryIR


def compile_sql(ir: QueryIR) -> str:
    """Compile Query IR into demo SQLite-compatible SQL."""
    if ir.metric == "max_temperature":
        where = "WHERE day = date('now', '-1 day')" if ir.time_range == "yesterday" else ""
        return f"""
SELECT s.name AS station, MAX(t.max_temp_c) AS max_temp_c
FROM telemetry_daily t
JOIN stations s ON s.station_id = t.station_id
{where}
GROUP BY s.name
ORDER BY max_temp_c DESC
LIMIT {ir.limit}
""".strip()

    if ir.metric == "online_device_count":
        return """
SELECT COUNT(*) AS online_device_count
FROM devices
WHERE status = 'online'
""".strip()

    if ir.intent == "compare" and ir.metric == "alarm_count":
        return """
SELECT
  CASE
    WHEN date(occurred_at) >= date('now', 'start of month') THEN 'this_month'
    ELSE 'last_month'
  END AS period,
  COUNT(DISTINCT alarm_id) AS alarm_count
FROM alarms
WHERE date(occurred_at) >= date('now', 'start of month', '-1 month')
GROUP BY period
ORDER BY period
""".strip()

    if ir.intent == "rank" and ir.metric == "alarm_count":
        days = 7 if ir.time_range == "last_7_days" else 30
        return f"""
SELECT d.device_id, d.name, COUNT(DISTINCT a.alarm_id) AS alarm_count
FROM alarms a
JOIN devices d ON d.device_id = a.device_id
WHERE date(a.occurred_at) >= date('now', '-{days} day')
GROUP BY d.device_id, d.name
ORDER BY alarm_count DESC
LIMIT {ir.limit}
""".strip()

    if ir.metric == "alarm_count" and ir.dimensions == ["region"]:
        return """
SELECT d.region, COUNT(DISTINCT a.alarm_id) AS alarm_count
FROM alarms a
JOIN devices d ON d.device_id = a.device_id
GROUP BY d.region
ORDER BY alarm_count DESC
LIMIT 100
""".strip()

    # Fallback exploratory query
    return """
SELECT device_id, name, region, status
FROM devices
LIMIT 20
""".strip()
