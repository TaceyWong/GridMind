from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message.")
    session_id: str | None = Field(default=None, description="Optional session id.")


class ChatResponse(BaseModel):
    message: str = Field(..., description="Assistant reply.")
    session_id: str | None = Field(default=None, description="Session id if provided.")
    source: str = Field(default="stub", description="Reply source tag.")


class ChatStreamResponse(BaseModel):
    message: str = Field(..., description="Stream chunk or full stub reply.")
    done: bool = Field(default=True, description="Whether the stream is finished.")


class ChatToolsResponse(BaseModel):
    message: str = Field(..., description="Tools listing or stub message.")
    tools: list[str] = Field(default_factory=list, description="Available tool names.")
