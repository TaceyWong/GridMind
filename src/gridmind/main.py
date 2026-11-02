from contextlib import asynccontextmanager

from fastapi import FastAPI

from gridmind.api.middleware import RequestContextMiddleware
from gridmind.api.router import api_v1_router
from gridmind.core.config import settings
from gridmind.core.errors import register_exception_handlers
from gridmind.core.logging import setup_logging
from gridmind.nl2sql.executor import init_demo_db
from gridmind.rag.retriever import get_knowledge_store
from gridmind.schemas.common import HealthResponse, MessageResponse


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging(settings.debug)
    init_demo_db()
    get_knowledge_store()
    yield


app = FastAPI(
    title="GridMind API",
    description="电网智能问答与数据分析平台（Agent + MCP + NL2SQL 学习项目）",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)
app.add_middleware(RequestContextMiddleware)
register_exception_handlers(app)
app.include_router(api_v1_router)


@app.get("/", description="Root endpoint.", tags=["System"])
async def root() -> MessageResponse:
    return MessageResponse(message="Hello, this is GridMind!")


@app.get("/health", description="Health check endpoint.", tags=["System"])
async def health() -> HealthResponse:
    return HealthResponse(message="OK")
