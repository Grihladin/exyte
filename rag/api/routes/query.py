"""Query endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from rag.api.models import QueryRequest, QueryResultModel
from rag.graph import build_workflow

router = APIRouter(prefix="/query", tags=["query"])
workflow = build_workflow()


@router.post("", response_model=QueryResultModel)
async def run_query(request: QueryRequest) -> QueryResultModel:
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    state = {
        "query": request.query,
        "options": request.options.dict(exclude_none=True) if request.options else {},
    }
    output = workflow.invoke(state)
    result = output.get("result")
    if result is None:
        raise HTTPException(status_code=500, detail="Workflow did not return a result.")
    return QueryResultModel(**result)
