from fastapi import APIRouter, Depends

from gridmind.api.deps import get_chat_service
from gridmind.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatStreamResponse,
    ChatToolsResponse,
)
from gridmind.services.chat import ChatService

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("", description="Chat endpoint.")
async def chat(
    request: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    return await service.chat(request)


@router.post("/stream", description="Chat stream endpoint.")
async def chat_stream(
    request: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> ChatStreamResponse:
    return await service.chat_stream(request)


@router.post("/tools", description="Chat tools endpoint.")
async def chat_tools(
    service: ChatService = Depends(get_chat_service),
) -> ChatToolsResponse:
    return await service.chat_tools()
