from fastapi import FastAPI

from gridmind.api.router import api_v1_router
from gridmind.schemas.common import HealthResponse, MessageResponse

app = FastAPI(
    title="GridMind API",
    description="API for GridMind server.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)
app.include_router(api_v1_router)


@app.get("/", description="Root endpoint.", tags=["System"])
async def root() -> MessageResponse:
    return MessageResponse(message="Hello, this is GridMind!")


@app.get("/health", description="Health check endpoint.", tags=["System"])
async def health() -> HealthResponse:
    return HealthResponse(message="OK")
