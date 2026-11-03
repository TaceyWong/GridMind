from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    metric: str | None = Field(default=None, description="强制使用的语义指标 key")
    dimensions: list[str] | None = Field(default=None, description="强制维度")


class QueryResponse(BaseModel):
    question: str
    summary: dict[str, Any]
    sql: str
    rows: list[dict[str, Any]]
    chart: dict[str, Any] | None = None
    gpt_vis: str | None = None
    ir: dict[str, Any] | None = None


class SemanticCatalogResponse(BaseModel):
    name: str | None = None
    description: str | None = None
    handbook: str | None = None
    metrics: list[dict[str, Any]] = Field(default_factory=list)
    dimensions: list[dict[str, Any]] = Field(default_factory=list)
    entities: list[dict[str, Any]] = Field(default_factory=list)
    relationships: list[dict[str, Any]] = Field(default_factory=list)
