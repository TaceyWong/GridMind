from fastapi import APIRouter

API_V1_ROUTER = APIRouter(
    prefix="/api/v1",
    tags=["GridMind API"],
)


@API_V1_ROUTER.post("/chat",description="Chat endpoint.")
async def chat() -> dict[str, str]:
    return {"message": "Hello, this is GridMind! How can I help you today?"}


@API_V1_ROUTER.post("/chat/stream",description="Chat stream endpoint.")
async def chat_stream() -> dict[str, str]:
    return {"message": "Hello, this is GridMind! How can I help you today?"}

@API_V1_ROUTER.post("/chat/tools",description="Chat tools endpoint.")
async def chat_tools() -> dict[str, str]:
    return {"message": "Hello, this is GridMind! How can I help you today?"}

@API_V1_ROUTER.post("/health",description="API Health check endpoint.")
async def health() -> dict[str, str]:
    return {"message": "OK"}