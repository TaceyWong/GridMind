from gridmind.nl2sql.planner import plan_from_question
from gridmind.nl2sql.semantic import semantic_catalog


def test_semantic_catalog_has_new_metrics():
    cat = semantic_catalog()
    keys = {m["key"] for m in cat["metrics"]}
    assert {"alarm_count", "avg_temperature", "offline_device_count", "critical_alarm_count"} <= keys
    assert any(d["key"] == "level" for d in cat["dimensions"])


def test_forced_metric_overrides_question():
    ir = plan_from_question("随便问问", metric="avg_temperature")
    assert ir.metric == "avg_temperature"
    assert "station_id" in ir.dimensions
