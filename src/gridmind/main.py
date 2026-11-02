from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from gridmind.api.middleware import RequestContextMiddleware
from gridmind.api.router import api_v1_router
from gridmind.core.config import settings
from gridmind.core.errors import register_exception_handlers
from gridmind.core.logging import setup_logging
from gridmind.nl2sql.executor import init_demo_db
from gridmind.rag.retriever import get_knowledge_store
from gridmind.schemas.common import HealthResponse

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestContextMiddleware)
register_exception_handlers(app)
app.include_router(api_v1_router)


@app.get("/health", description="Health check endpoint.", tags=["System"])
async def health() -> HealthResponse:
    return HealthResponse(message="OK")


if FRONTEND_DIST.exists():
    @app.get("/")
    async def spa_index() -> FileResponse:
        return FileResponse(FRONTEND_DIST / "index.html")

    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
else:

    @app.get("/", tags=["System"])
    async def root() -> dict[str, str]:
        return {
            "message": "GridMind API is running. Build frontend with `npm run build` in frontend/, or use `npm run dev`.",
            "docs": "/docs",
        }
