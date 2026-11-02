from fastapi import APIRouter

from gridmind.schemas.common import HealthResponse

router = APIRouter(tags=["System"])


@router.get("/health", description="API Health check endpoint.")
async def api_health() -> HealthResponse:
    return HealthResponse(message="OK")
