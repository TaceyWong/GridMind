from fastapi import APIRouter

from gridmind.api.routes import chat_router, system_router
from gridmind.core.config import settings

api_v1_router = APIRouter(prefix=settings.api_v1_prefix)
api_v1_router.include_router(chat_router)
api_v1_router.include_router(system_router)
