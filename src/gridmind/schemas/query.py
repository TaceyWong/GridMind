from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    use_llm: bool = True


class QueryResponse(BaseModel):
    question: str
    summary: dict[str, Any]
    sql: str
    rows: list[dict[str, Any]]
    chart: dict[str, Any] | None = None
    ir: dict[str, Any] | None = None
