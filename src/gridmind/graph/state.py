from __future__ import annotations

from typing import Any, Literal, TypedDict


Route = Literal["rag", "nl2sql", "mcp", "hybrid", "answer"]


class ChatState(TypedDict, total=False):
    question: str
    session_id: str | None
    user_id: str
    tenant_id: str
    provider: str | None
    model: str | None
    preferred_metric: str | None
    preferred_dimensions: list[str]
    route: Route
    messages: list[dict[str, str]]
    rag_context: str
    sql: str
    query_summary: dict[str, Any]
    query_rows: list[dict[str, Any]]
    tool_name: str | None
    tool_args: dict[str, Any]
    tool_result: Any
    intermediate: list[str]
    answer: str
    sources: list[dict[str, Any]]
    events: list[dict[str, Any]]
