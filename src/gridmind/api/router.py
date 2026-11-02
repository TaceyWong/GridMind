from fastapi import APIRouter, Depends

from gridmind.api.routes import chat_router, knowledge_router, query_router, system_router
from gridmind.core.config import settings
from gridmind.core.security import optional_api_key

api_v1_router = APIRouter(
    prefix=settings.api_v1_prefix,
    dependencies=[Depends(optional_api_key)],
)
api_v1_router.include_router(chat_router)
api_v1_router.include_router(knowledge_router)
api_v1_router.include_router(query_router)
api_v1_router.include_router(system_router)
