from fastapi import APIRouter

from gridmind.core.config import settings
from gridmind.llm.gateway import get_llm_gateway
from gridmind.schemas.common import HealthResponse

router = APIRouter(tags=["System"])


@router.get("/health", description="API Health check endpoint.")
async def api_health() -> HealthResponse:
    return HealthResponse(message="OK")


@router.get("/meta", description="Runtime metadata for learning demos.")
async def meta() -> dict:
    gateway = get_llm_gateway()
    return {
        "app": settings.app_name,
        "llm_default_provider": gateway.default_provider,
        "llm_providers": gateway.list_providers(),
        "has_llm_key": settings.has_llm_key,
        "token_usage": {
            "prompt_tokens": gateway.usage_total.prompt_tokens,
            "completion_tokens": gateway.usage_total.completion_tokens,
            "total_tokens": gateway.usage_total.total_tokens,
        },
    }
