from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
    message: str = Field(..., description="Human-readable message.")


class HealthResponse(BaseModel):
    message: str = Field(default="OK", description="Health status.")
