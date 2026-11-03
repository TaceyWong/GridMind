"""把 GridMind `grid.yaml` 转成 Wren MDL，并可选调用 wren-core 做 SQL planning。"""

from __future__ import annotations

import base64
import json
import logging
from functools import lru_cache
from typing import Any

from gridmind.nl2sql.semantic import load_semantic_model

logger = logging.getLogger(__name__)

# 演示库里的惯用关联（YAML 未声明时兜底）
_DEFAULT_RELATIONSHIPS: list[dict[str, Any]] = [
    {
        "name": "devices_station",
        "models": ["devices", "stations"],
        "joinType": "MANY_TO_ONE",
        "condition": "devices.station_id = stations.station_id",
    },
    {
        "name": "alarms_device",
        "models": ["alarms", "devices"],
        "joinType": "MANY_TO_ONE",
        "condition": "alarms.device_id = devices.device_id",
    },
    {
        "name": "telemetry_station",
        "models": ["telemetry_daily", "stations"],
        "joinType": "MANY_TO_ONE",
        "condition": "telemetry_daily.station_id = stations.station_id",
    },
    {
        "name": "telemetry_device",
        "models": ["telemetry_daily", "devices"],
        "joinType": "MANY_TO_ONE",
        "condition": "telemetry_daily.device_id = devices.device_id",
    },
]

_PRIMARY_KEYS = {
    "stations": "station_id",
    "devices": "device_id",
    "alarms": "alarm_id",
}


def grid_yaml_to_mdl(model: dict[str, Any] | None = None) -> dict[str, Any]:
    """Convert GridMind semantic YAML into a Wren MDL manifest dict."""
    model = model or load_semantic_model()
    entities = model.get("entities") or {}

    models: list[dict[str, Any]] = []
    table_to_model: dict[str, str] = {}

    for entity_key, entity in entities.items():
        table = str(entity.get("table") or entity_key)
        model_name = table  # 与现有 compiler SQL 表名对齐，便于 transform
        table_to_model[table] = model_name
        columns: list[dict[str, Any]] = []
        for field, desc in (entity.get("fields") or {}).items():
            columns.append(
                {
                    "name": field,
                    "type": _guess_type(field),
                    "properties": {"description": str(desc)},
                }
            )

        # 把 YAML metrics 挂到主表上的 calculated field（可被语义检索/展开）
        for metric_key, metric in (model.get("metrics") or {}).items():
            host = _metric_host_table(metric_key)
            if host != table:
                continue
            expr = str(metric.get("sql") or "").strip()
            # 带 WHERE 的指标表达式不适合作 Wren calculated field
            if not expr or "WHERE" in expr.upper() or "FILTER-like" in expr:
                continue
            columns.append(
                {
                    "name": metric_key,
                    "type": "double",
                    "isCalculated": True,
                    "expression": expr,
                    "properties": {
                        "description": metric.get("definition") or metric.get("label") or "",
                        "label": metric.get("label") or metric_key,
                    },
                }
            )

        item: dict[str, Any] = {
            "name": model_name,
            "tableReference": {"table": table},
            "columns": columns,
            "properties": {
                "description": entity.get("description") or entity_key,
                "entity": entity_key,
            },
        }
        pk = _PRIMARY_KEYS.get(table)
        if pk:
            item["primaryKey"] = pk
        models.append(item)

    relationships = list(model.get("relationships") or [])
    if not relationships:
        # 只保留两端模型都存在的默认关系
        names = {m["name"] for m in models}
        relationships = [
            rel
            for rel in _DEFAULT_RELATIONSHIPS
            if set(rel["models"]).issubset(names)
        ]

    # 给关系列补上 relationship 字段，便于以后写逻辑 SQL
    _attach_relationship_columns(models, relationships)

    return {
        "catalog": "gridmind",
        "schema": "public",
        "dataSource": "DUCKDB",
        "description": model.get("description") or model.get("name") or "GridMind",
        "models": models,
        "relationships": relationships,
        "views": model.get("views") or [],
        "cubes": model.get("cubes") or [],
    }


def mdl_to_base64(mdl: dict[str, Any]) -> str:
    raw = json.dumps(mdl, ensure_ascii=False).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


@lru_cache
def get_wren_session() -> Any | None:
    """Lazy SessionContext; returns None if wren-core-py unavailable."""
    try:
        from wren_core import SessionContext
    except ImportError:
        logger.warning("wren-core-py 未安装，跳过 Wren planning")
        return None

    mdl = grid_yaml_to_mdl()
    b64 = mdl_to_base64(mdl)
    try:
        return SessionContext(mdl_base64=b64, data_source="DUCKDB")
    except Exception:
        logger.exception("创建 Wren SessionContext 失败")
        return None


def clear_wren_session_cache() -> None:
    get_wren_session.cache_clear()


def plan_sql_with_wren(sql: str) -> str | None:
    """Run wren-core transform_sql. Return planned SQL or None on failure."""
    ctx = get_wren_session()
    if ctx is None:
        return None
    try:
        planned = ctx.transform_sql(sql)
        return str(planned).strip() or None
    except Exception as exc:
        logger.warning("wren-core transform_sql 失败，将回退本地 compiler: %s", exc)
        return None


def _guess_type(field: str) -> str:
    name = field.lower()
    if name.endswith("_c") or "temp" in name or name.startswith("avg_") or name.startswith("max_"):
        return "double"
    if name.endswith("_count") or name in {"limit"}:
        return "bigint"
    return "varchar"


def _metric_host_table(metric_key: str) -> str | None:
    mapping = {
        "alarm_count": "alarms",
        "critical_alarm_count": "alarms",
        "online_device_count": "devices",
        "offline_device_count": "devices",
        "max_temperature": "telemetry_daily",
        "avg_temperature": "telemetry_daily",
    }
    return mapping.get(metric_key)


def _attach_relationship_columns(
    models: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
) -> None:
    by_name = {m["name"]: m for m in models}
    for rel in relationships:
        left, right = rel["models"]
        join_type = rel.get("joinType", "")
        # MANY_TO_ONE: left 持有指向 right 的关系列
        if join_type == "MANY_TO_ONE" and left in by_name and right in by_name:
            cols = by_name[left]["columns"]
            if any(c.get("relationship") == rel["name"] for c in cols):
                continue
            cols.append(
                {
                    "name": right.rstrip("s") if right.endswith("s") else right,
                    "type": right,
                    "relationship": rel["name"],
                    "properties": {"description": f"relation via {rel['name']}"},
                }
            )
