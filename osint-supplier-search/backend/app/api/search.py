from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, status
from app.models.schemas import SearchRequest, SearchCreatedResponse
from app.core.security import get_current_user_id
from app.db.rest_client import db_insert

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchCreatedResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_search(
    body: SearchRequest,
    user_id: str = Depends(get_current_user_id),
):
    rows = await db_insert("search_jobs", {
        "user_id": user_id,
        "query": body.query,
        "filters": body.filters.model_dump(),
        "status": "pending",
    })
    job_id = UUID(rows[0]["id"])

    from workers.tasks.orchestrator import run_search
    run_search.delay(str(job_id), body.query, body.filters.model_dump())

    return SearchCreatedResponse(
        job_id=job_id,
        status="pending",
        query=body.query,
        polling_url=f"/v1/jobs/{job_id}",
    )
