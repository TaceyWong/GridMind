from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from gridmind.core.config import settings


def load_semantic_model(path: Path | None = None) -> dict[str, Any]:
    model_path = path or settings.semantic_model_path
    with model_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def schema_prompt(model: dict[str, Any] | None = None) -> str:
    model = model or load_semantic_model()
    lines = ["语义模型与表结构："]
    for entity in model.get("entities", {}).values():
        table = entity["table"]
        lines.append(f"- 表 {table}: {entity.get('description', '')}")
        for field, desc in entity.get("fields", {}).items():
            lines.append(f"  - {field}: {desc}")
    lines.append("指标：")
    for key, metric in model.get("metrics", {}).items():
        lines.append(f"- {key}: {metric.get('label')} | {metric.get('definition')}")
    return "\n".join(lines)


def tables_whitelist(model: dict[str, Any] | None = None) -> set[str]:
    model = model or load_semantic_model()
    return set(model.get("tables_whitelist", []))


def semantic_catalog(model: dict[str, Any] | None = None) -> dict[str, Any]:
    """前端/API 用的语义目录（指标、维度、实体摘要）。"""
    model = model or load_semantic_model()
    metrics = []
    for key, meta in (model.get("metrics") or {}).items():
        metrics.append(
            {
                "key": key,
                "label": meta.get("label") or key,
                "definition": meta.get("definition") or "",
                "sql": meta.get("sql") or "",
                "default_dimensions": list(meta.get("default_dimensions") or []),
                "synonyms": list(meta.get("synonyms") or []),
            }
        )

    raw_dims = model.get("dimensions") or []
    dimensions = []
    if isinstance(raw_dims, dict):
        for key, meta in raw_dims.items():
            if isinstance(meta, dict):
                dimensions.append(
                    {
                        "key": key,
                        "label": meta.get("label") or key,
                        "definition": meta.get("definition") or "",
                    }
                )
            else:
                dimensions.append({"key": key, "label": str(meta), "definition": ""})
    else:
        for item in raw_dims:
            if isinstance(item, str):
                dimensions.append({"key": item, "label": item, "definition": ""})
            elif isinstance(item, dict) and "key" in item:
                dimensions.append(
                    {
                        "key": item["key"],
                        "label": item.get("label") or item["key"],
                        "definition": item.get("definition") or "",
                    }
                )

    entities = []
    for key, ent in (model.get("entities") or {}).items():
        entities.append(
            {
                "key": key,
                "table": ent.get("table"),
                "description": ent.get("description") or "",
                "fields": [
                    {"name": f, "description": d}
                    for f, d in (ent.get("fields") or {}).items()
                ],
            }
        )

    return {
        "name": model.get("name"),
        "description": model.get("description"),
        "handbook": model.get("handbook"),
        "metrics": metrics,
        "dimensions": dimensions,
        "entities": entities,
        "relationships": model.get("relationships") or [],
    }


def dimension_keys(model: dict[str, Any] | None = None) -> list[str]:
    catalog = semantic_catalog(model)
    return [d["key"] for d in catalog["dimensions"]]
