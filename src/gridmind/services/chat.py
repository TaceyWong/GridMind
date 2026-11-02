from gridmind.agent.orchestrator import AgentOrchestrator
from gridmind.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatStreamResponse,
    ChatToolsResponse,
)


class ChatService:
    """Chat application service. Delegates to AgentOrchestrator stub."""

    def __init__(self, orchestrator: AgentOrchestrator | None = None) -> None:
        self._orchestrator = orchestrator or AgentOrchestrator()

    async def chat(self, request: ChatRequest) -> ChatResponse:
        reply = await self._orchestrator.run(request.message)
        return ChatResponse(
            message=reply,
            session_id=request.session_id,
            source="agent-stub",
        )

    async def chat_stream(self, request: ChatRequest) -> ChatStreamResponse:
        reply = await self._orchestrator.run(request.message)
        return ChatStreamResponse(message=reply, done=True)

    async def chat_tools(self) -> ChatToolsResponse:
        tools = await self._orchestrator.list_tools()
        return ChatToolsResponse(
            message="Available GridMind tools (stub).",
            tools=tools,
        )
