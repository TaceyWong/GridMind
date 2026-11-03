from fastapi import APIRouter

from gridmind.nl2sql.semantic import semantic_catalog
from gridmind.schemas.query import SemanticCatalogResponse

router = APIRouter(prefix="/semantic", tags=["Semantic"])


@router.get("", description="语义目录：指标 / 维度 / 实体（前端选口径）。")
async def get_semantic_catalog() -> SemanticCatalogResponse:
    return SemanticCatalogResponse(**semantic_catalog())
