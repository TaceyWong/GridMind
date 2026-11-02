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
