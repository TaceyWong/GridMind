from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class QueryIR(BaseModel):
    intent: Literal["metric", "rank", "compare", "status", "unknown"] = "unknown"
    metric: str | None = None
    dimensions: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    time_range: str | None = None
    order_by: str | None = None
    limit: int = 100
    raw_question: str = ""
