from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from gridmind.api.deps import get_chat_service
from gridmind.schemas.chat import ChatRequest, ChatResponse, ChatToolsResponse
from gridmind.services.chat import ChatService

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("", description="Chat endpoint powered by LangGraph.")
async def chat(
    request: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    return await service.chat(request)


@router.post("/stream", description="Chat SSE stream endpoint.")
async def chat_stream(
    request: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    return StreamingResponse(
        service.chat_stream(request),
        media_type="text/event-stream",
    )


@router.post("/tools", description="List available MCP tools.")
async def chat_tools(
    service: ChatService = Depends(get_chat_service),
) -> ChatToolsResponse:
    return await service.chat_tools()
