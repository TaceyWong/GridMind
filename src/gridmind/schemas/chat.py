from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message.")
    session_id: str | None = Field(default=None, description="Optional session id.")
    provider: str | None = Field(default=None, description="LLM provider alias.")
    model: str | None = Field(default=None, description="Model name override.")


class ChatResponse(BaseModel):
    message: str = Field(..., description="Assistant reply.")
    session_id: str | None = Field(default=None, description="Session id if provided.")
    source: str = Field(default="graph", description="Reply source tag.")
    route: str | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    sql: str | None = None
    query_summary: dict[str, Any] | None = None


class ChatToolsResponse(BaseModel):
    message: str = Field(..., description="Tools listing message.")
    tools: list[dict[str, str]] = Field(default_factory=list)


class ChatStreamEvent(BaseModel):
    event: str
    data: dict[str, Any]
