from __future__ import annotations

import json
from collections.abc import AsyncIterator

from gridmind.graph.workflow import run_chat
from gridmind.mcp.client import McpClient
from gridmind.schemas.chat import ChatRequest, ChatResponse, ChatToolsResponse


class ChatService:
    async def chat(self, request: ChatRequest) -> ChatResponse:
        result = await run_chat(
            request.message,
            session_id=request.session_id,
            provider=request.provider,
            model=request.model,
        )
        return ChatResponse(
            message=result.get("answer") or "（无回答）",
            session_id=request.session_id,
            source="langgraph",
            route=result.get("route"),
            events=result.get("events") or [],
            sources=result.get("sources") or [],
            sql=result.get("sql"),
            query_summary=result.get("query_summary"),
        )

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """Yield SSE data payloads as the graph progresses (coarse-grained)."""
        yield _sse("status", {"message": "started"})
        result = await run_chat(
            request.message,
            session_id=request.session_id,
            provider=request.provider,
            model=request.model,
        )
        for event in result.get("events") or []:
            yield _sse("event", event)
        answer = result.get("answer") or ""
        # Stream answer in small chunks for demo UX
        chunk_size = 24
        for i in range(0, len(answer), chunk_size):
            yield _sse("token", {"text": answer[i : i + chunk_size]})
        yield _sse(
            "done",
            {
                "message": answer,
                "route": result.get("route"),
                "session_id": request.session_id,
            },
        )

    async def chat_tools(self) -> ChatToolsResponse:
        client = McpClient()
        tools = await client.list_tools()
        return ChatToolsResponse(
            message="GridMind MCP tools",
            tools=[{"name": t["key"], "description": t["description"]} for t in tools],
        )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
