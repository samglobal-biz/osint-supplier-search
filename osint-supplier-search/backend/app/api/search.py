from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from app.models.schemas import SearchRequest, SearchCreatedResponse
from app.core.security import get_current_user_id
from app.db.session import get_pool

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchCreatedResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_search(
    body: SearchRequest,
    user_id: str = Depends(get_current_user_id),
):
    pool = await get_pool()

    # Create job record
    job_id: UUID = await pool.fetchval(
        """
        INSERT INTO search_jobs (user_id, query, filters, status)
        VALUES ($1::uuid, $2, $3::jsonb, 'pending')
        RETURNING id
        """,
        user_id,
        body.query,
        body.filters.model_dump_json(),
    )

    # Dispatch Celery task
    from workers.tasks.orchestrator import run_search
    run_search.delay(str(job_id), body.query, body.filters.model_dump())

    return SearchCreatedResponse(
        job_id=job_id,
        status="pending",
        query=body.query,
        polling_url=f"/v1/jobs/{job_id}",
    )
