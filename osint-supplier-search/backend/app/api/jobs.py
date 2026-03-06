from __future__ import annotations
import asyncio
import json
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from app.models.schemas import JobStatusResponse, JobProgress, SearchResultsResponse, SupplierResult, EvidenceLink
from app.core.security import get_current_user_id
from app.db.rest_client import db_select, db_count, db_delete

router = APIRouter(prefix="/jobs", tags=["jobs"])


async def _get_job(job_id: UUID, user_id: str) -> dict:
    rows = await db_select("search_jobs", id=str(job_id), user_id=user_id)
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return rows[0]


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: UUID,
    user_id: str = Depends(get_current_user_id),
):
    row = await _get_job(job_id, user_id)
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
        completed_at=row.get("completed_at"),
        error_message=row.get("error_message"),
    )


@router.get("/{job_id}/stream")
async def stream_job(
    job_id: UUID,
    user_id: str = Depends(get_current_user_id),
):
    await _get_job(job_id, user_id)

    async def event_generator():
        last_done = -1
        while True:
            rows = await db_select(
                "search_jobs",
                select="status,adapters_done,adapters_total,candidates_found",
                id=str(job_id),
            )
            if not rows:
                break
            row = rows[0]
            if row["adapters_done"] != last_done:
                last_done = row["adapters_done"]
                yield f"data: {json.dumps({'type': 'progress', 'adapters_done': row['adapters_done'], 'adapters_total': row['adapters_total'], 'candidates_found': row['candidates_found']})}\n\n"
            if row["status"] in ("complete", "failed"):
                yield f"data: {json.dumps({'type': 'job_complete', 'status': row['status']})}\n\n"
                break
            await asyncio.sleep(2)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/{job_id}/results", response_model=SearchResultsResponse)
async def get_results(
    job_id: UUID,
    user_id: str = Depends(get_current_user_id),
):
    job = await _get_job(job_id, user_id)
    if job["status"] not in ("partial", "complete"):
        raise HTTPException(status_code=status.HTTP_202_ACCEPTED, detail="Results not ready yet")

    clusters = await db_select("entity_clusters", order="rank_score.desc", job_id=str(job_id))

    results = []
    for i, c in enumerate(clusters, start=1):
        evidence_rows = await db_select("evidence_links", order="scraped_at.desc", cluster_id=str(c["id"]))
        results.append(SupplierResult(
            rank=i,
            cluster_id=c["id"],
            canonical_name=c["canonical_name"],
            canonical_country=c.get("canonical_country"),
            canonical_address=c.get("canonical_address"),
            canonical_phone=c.get("canonical_phone"),
            canonical_email=c.get("canonical_email"),
            canonical_website=c.get("canonical_website"),
            canonical_tin=c.get("canonical_tin"),
            canonical_lei=c.get("canonical_lei"),
            supplier_types=list(c.get("supplier_types") or []),
            industry_tags=list(c.get("industry_tags") or []),
            sanction_flag=c.get("sanction_flag", False),
            confidence_score=c.get("confidence_score", 0),
            rank_score=c.get("rank_score", 0),
            source_count=c.get("source_count", 1),
            resolution_methods=list(c.get("resolution_methods") or []),
            evidence=[
                EvidenceLink(
                    adapter=e["adapter"],
                    source_url=e["source_url"],
                    matched_fields=list(e.get("matched_fields") or []),
                    field_scores=dict(e.get("field_scores") or {}),
                    snippet=e.get("snippet"),
                    scraped_at=e.get("scraped_at"),
                )
                for e in evidence_rows
            ],
        ))

    total_candidates = await db_count("raw_candidates", job_id=str(job_id))
    return SearchResultsResponse(
        job_id=job_id,
        query=job["query"],
        status=job["status"],
        total_candidates_scraped=total_candidates,
        total_clusters=len(clusters),
        results=results,
        completed_at=job.get("completed_at"),
    )


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: UUID,
    user_id: str = Depends(get_current_user_id),
):
    await _get_job(job_id, user_id)
    await db_delete("search_jobs", id=str(job_id))
