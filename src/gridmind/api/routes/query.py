from fastapi import APIRouter

from gridmind.nl2sql.engine import get_nl2sql_engine
from gridmind.schemas.query import QueryRequest, QueryResponse

router = APIRouter(prefix="/query", tags=["Query"])


@router.post("", description="Natural language query (NL2SQL / ChatBI).")
async def query(request: QueryRequest) -> QueryResponse:
    result = await get_nl2sql_engine().run(request.question, use_llm=request.use_llm)
    return QueryResponse(
        question=result["question"],
        summary=result["summary"],
        sql=result["sql"],
        rows=result["rows"],
        chart=result.get("chart"),
        gpt_vis=result.get("gpt_vis") or None,
        ir=result.get("ir"),
    )
