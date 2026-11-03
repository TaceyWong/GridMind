from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator

from gridmind.graph.workflow import run_chat
from gridmind.mcp.client import McpClient
from gridmind.nl2sql.engine import Nl2SqlError
from gridmind.schemas.chat import ChatRequest, ChatResponse, ChatToolsResponse

logger = logging.getLogger(__name__)


class ChatService:
    async def chat(self, request: ChatRequest) -> ChatResponse:
        try:
            result = await run_chat(
                request.message,
                session_id=request.session_id,
                provider=request.provider,
                model=request.model,
                preferred_metric=request.metric,
                preferred_dimensions=request.dimensions,
            )
        except Nl2SqlError as exc:
            return ChatResponse(
                message=f"问数失败：{exc}",
                session_id=request.session_id,
                source="langgraph",
                route="nl2sql",
                events=[{"type": "error", "message": str(exc)}],
                sources=[],
                sql=None,
                query_summary={"error": str(exc)},
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
        """Yield SSE events: status → event* → token* → done | error."""
        yield _sse("status", {"message": "started", "stage": "routing"})
        await asyncio.sleep(0)

        try:
            result = await run_chat(
                request.message,
                session_id=request.session_id,
                provider=request.provider,
                model=request.model,
                preferred_metric=request.metric,
                preferred_dimensions=request.dimensions,
            )
        except Exception as exc:
            logger.exception("chat_stream failed")
            yield _sse(
                "error",
                {
                    "message": str(exc),
                    "detail": str(exc),
                    "route": "nl2sql" if isinstance(exc, Nl2SqlError) else None,
                },
            )
            return

        # 图内已消化的问数失败：仍通过 error 事件推到前端
        for event in result.get("events") or []:
            if event.get("type") == "error":
                yield _sse(
                    "error",
                    {
                        "message": event.get("message") or "问数失败",
                        "detail": event.get("message"),
                        "route": event.get("route") or result.get("route"),
                    },
                )
                return
            yield _sse("event", event)
            await asyncio.sleep(0)

        yield _sse(
            "status",
            {
                "message": "generating",
                "stage": "answer",
                "route": result.get("route"),
            },
        )

        answer = result.get("answer") or ""
        # 答案文本里若已是失败提示，也发 error 便于 UI 统一样式
        summary = result.get("query_summary") or {}
        if isinstance(summary, dict) and summary.get("error"):
            yield _sse(
                "error",
                {
                    "message": str(summary["error"]),
                    "detail": str(summary["error"]),
                    "route": result.get("route"),
                },
            )
            return

        chunk_size = 16
        for i in range(0, len(answer), chunk_size):
            yield _sse("token", {"text": answer[i : i + chunk_size]})
            await asyncio.sleep(0.02)

        yield _sse(
            "done",
            {
                "message": answer,
                "route": result.get("route"),
                "session_id": request.session_id,
                "sources": result.get("sources") or [],
                "sql": result.get("sql"),
                "query_summary": result.get("query_summary"),
                "query_rows": result.get("query_rows") or [],
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
