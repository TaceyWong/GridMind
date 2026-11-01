from fastapi import FastAPI
from gridmind.router import API_V1_ROUTER

app = FastAPI(
    title="GridMind API",
    description="API for GridMind server.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)
app.include_router(API_V1_ROUTER)

@app.get("/",description="Root endpoint.",tags=["System"])
async def root() -> dict[str, str]:
    return {"message": "Hello, this is GridMind!"}

@app.get("/health",description="Health check endpoint.",tags=["System"])
async def health() -> dict[str, str]:
    return {"message": "OK"}
