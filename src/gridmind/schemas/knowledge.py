from typing import Any

from pydantic import BaseModel, Field


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class KnowledgeChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    provider: str | None = None
    model: str | None = None


class KnowledgeDocument(BaseModel):
    doc_id: str
    name: str
    chars: int
    meta: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSearchResponse(BaseModel):
    hits: list[dict[str, Any]]


class KnowledgeChatResponse(BaseModel):
    answer: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
