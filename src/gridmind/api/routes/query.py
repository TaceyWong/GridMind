from fastapi import APIRouter, HTTPException

from gridmind.nl2sql.engine import Nl2SqlError, get_nl2sql_engine
from gridmind.schemas.query import QueryRequest, QueryResponse

router = APIRouter(prefix="/query", tags=["Query"])


@router.post("", description="Natural language query (NL2SQL / ChatBI).")
async def query(request: QueryRequest) -> QueryResponse:
    try:
        result = await get_nl2sql_engine().run(
            request.question,
            metric=request.metric,
            dimensions=request.dimensions,
        )
    except Nl2SqlError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return QueryResponse(
        question=result["question"],
        summary=result["summary"],
        sql=result["sql"],
        rows=result["rows"],
        chart=result.get("chart"),
        gpt_vis=result.get("gpt_vis") or None,
        ir=result.get("ir"),
    )
