from __future__ import annotations
import asyncio
import json
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from app.models.schemas import JobStatusResponse, JobProgress, SearchResultsResponse, SupplierResult, EvidenceLink
from app.core.security import get_current_user_id
from app.db.session import get_pool

router = APIRouter(prefix="/jobs", tags=["jobs"])


async def _get_job_row(pool, job_id: UUID, user_id: str):
    row = await pool.fetchrow(
        "SELECT * FROM search_jobs WHERE id = $1 AND user_id = $2::uuid",
        job_id, user_id,
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return row


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: UUID,
    user_id: str = Depends(get_current_user_id),
):
    pool = await get_pool()
    row = await _get_job_row(pool, job_id, user_id)
    return JobStatusResponse(
        job_id=row["id"],
        status=row["status"],
        query=row["query"],
        progress=JobProgress(
            adapters_done=row["adapters_done"],
            adapters_total=row["adapters_total"],
            candidates_found=row["candidates_found"],
        ),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        completed_at=row["completed_at"],
        error_message=row["error_message"],
    )


@router.get("/{job_id}/stream")
async def stream_job(
    job_id: UUID,
    user_id: str = Depends(get_current_user_id),
):
    pool = await get_pool()
    # Verify ownership
    await _get_job_row(pool, job_id, user_id)

    async def event_generator():
        last_done = -1
        while True:
            row = await pool.fetchrow(
                "SELECT status, adapters_done, adapters_total, candidates_found FROM search_jobs WHERE id = $1",
                job_id,
            )
            if not row:
                break
            if row["adapters_done"] != last_done:
                last_done = row["adapters_done"]
                data = {
                    "type": "progress",
                    "adapters_done": row["adapters_done"],
                    "adapters_total": row["adapters_total"],
                    "candidates_found": row["candidates_found"],
                }
                yield f"data: {json.dumps(data)}\n\n"
            if row["status"] in ("complete", "failed"):
                data = {"type": "job_complete", "status": row["status"]}
                yield f"data: {json.dumps(data)}\n\n"
                break
            await asyncio.sleep(2)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/{job_id}/results", response_model=SearchResultsResponse)
async def get_results(
    job_id: UUID,
    user_id: str = Depends(get_current_user_id),
):
    pool = await get_pool()
    job = await _get_job_row(pool, job_id, user_id)

    if job["status"] not in ("partial", "complete"):
        raise HTTPException(status_code=status.HTTP_202_ACCEPTED, detail="Results not ready yet")

    clusters = await pool.fetch(
        """
        SELECT ec.*, COUNT(rc.id) as candidate_count
        FROM entity_clusters ec
        LEFT JOIN raw_candidates rc ON rc.cluster_id = ec.id
        WHERE ec.job_id = $1
        GROUP BY ec.id
        ORDER BY ec.rank_score DESC
        """,
        job_id,
    )

    results = []
    for i, c in enumerate(clusters, start=1):
        evidence_rows = await pool.fetch(
            "SELECT * FROM evidence_links WHERE cluster_id = $1 ORDER BY scraped_at DESC",
            c["id"],
        )
        evidence = [
            EvidenceLink(
                adapter=e["adapter"],
                source_url=e["source_url"],
                matched_fields=list(e["matched_fields"] or []),
                field_scores=dict(e["field_scores"] or {}),
                snippet=e["snippet"],
                scraped_at=e["scraped_at"],
            )
            for e in evidence_rows
        ]
        results.append(SupplierResult(
            rank=i,
            cluster_id=c["id"],
            canonical_name=c["canonical_name"],
            canonical_country=c["canonical_country"],
            canonical_address=c["canonical_address"],
            canonical_phone=c["canonical_phone"],
            canonical_email=c["canonical_email"],
            canonical_website=c["canonical_website"],
            canonical_tin=c["canonical_tin"],
            canonical_lei=c["canonical_lei"],
            supplier_types=list(c["supplier_types"] or []),
            industry_tags=list(c["industry_tags"] or []),
            sanction_flag=c["sanction_flag"],
            confidence_score=c["confidence_score"],
            rank_score=c["rank_score"],
            source_count=c["source_count"],
            resolution_methods=list(c["resolution_methods"] or []),
            evidence=evidence,
        ))

    total_candidates = await pool.fetchval(
        "SELECT COUNT(*) FROM raw_candidates WHERE job_id = $1", job_id
    )

    return SearchResultsResponse(
        job_id=job_id,
        query=job["query"],
        status=job["status"],
        total_candidates_scraped=total_candidates or 0,
        total_clusters=len(clusters),
        results=results,
        completed_at=job["completed_at"],
    )


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: UUID,
    user_id: str = Depends(get_current_user_id),
):
    pool = await get_pool()
    await _get_job_row(pool, job_id, user_id)
    await pool.execute("DELETE FROM search_jobs WHERE id = $1", job_id)
