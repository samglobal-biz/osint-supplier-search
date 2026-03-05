from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
import csv
import io
from app.models.schemas import SupplierProfileResponse, EvidenceLink, RawCandidateDetail
from app.core.security import get_current_user_id
from app.db.session import get_pool

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


@router.get("/{cluster_id}", response_model=SupplierProfileResponse)
async def get_supplier_profile(
    cluster_id: UUID,
    user_id: str = Depends(get_current_user_id),
):
    pool = await get_pool()
    cluster = await pool.fetchrow(
        """
        SELECT ec.* FROM entity_clusters ec
        JOIN search_jobs sj ON sj.id = ec.job_id
        WHERE ec.id = $1 AND sj.user_id = $2::uuid
        """,
        cluster_id, user_id,
    )
    if not cluster:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")

    evidence_rows = await pool.fetch(
        "SELECT * FROM evidence_links WHERE cluster_id = $1 ORDER BY scraped_at DESC",
        cluster_id,
    )
    raw_rows = await pool.fetch(
        "SELECT * FROM raw_candidates WHERE cluster_id = $1 ORDER BY scraped_at DESC",
        cluster_id,
    )

    all_raw_names = list({r["raw_name"] for r in raw_rows if r["raw_name"]})

    return SupplierProfileResponse(
        cluster_id=cluster["id"],
        canonical_name=cluster["canonical_name"],
        canonical_country=cluster["canonical_country"],
        canonical_address=cluster["canonical_address"],
        canonical_phone=cluster["canonical_phone"],
        canonical_email=cluster["canonical_email"],
        canonical_website=cluster["canonical_website"],
        canonical_tin=cluster["canonical_tin"],
        canonical_lei=cluster["canonical_lei"],
        supplier_types=list(cluster["supplier_types"] or []),
        industry_tags=list(cluster["industry_tags"] or []),
        description=cluster["description"],
        founding_year=cluster["founding_year"],
        employee_range=cluster["employee_range"],
        sanction_flag=cluster["sanction_flag"],
        confidence_score=cluster["confidence_score"],
        source_count=cluster["source_count"],
        resolution_methods=list(cluster["resolution_methods"] or []),
        all_raw_names=all_raw_names,
        evidence=[
            EvidenceLink(
                adapter=e["adapter"],
                source_url=e["source_url"],
                matched_fields=list(e["matched_fields"] or []),
                field_scores=dict(e["field_scores"] or {}),
                snippet=e["snippet"],
                scraped_at=e["scraped_at"],
            )
            for e in evidence_rows
        ],
        raw_candidates=[
            RawCandidateDetail(
                id=r["id"],
                adapter=r["adapter"],
                source_url=r["source_url"],
                raw_name=r["raw_name"],
                raw_address=r["raw_address"],
                raw_country=r["raw_country"],
                raw_phone=r["raw_phone"],
                raw_email=r["raw_email"],
                raw_website=r["raw_website"],
                supplier_type=r["supplier_type"],
                scraped_at=r["scraped_at"],
            )
            for r in raw_rows
        ],
    )


router_export = APIRouter(prefix="/jobs", tags=["export"])


@router_export.get("/{job_id}/export")
async def export_csv(
    job_id: UUID,
    user_id: str = Depends(get_current_user_id),
):
    pool = await get_pool()
    job = await pool.fetchrow(
        "SELECT * FROM search_jobs WHERE id = $1 AND user_id = $2::uuid",
        job_id, user_id,
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    clusters = await pool.fetch(
        "SELECT * FROM entity_clusters WHERE job_id = $1 ORDER BY rank_score DESC",
        job_id,
    )

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        "rank", "name", "country", "types", "address", "phone",
        "email", "website", "tin", "lei", "confidence", "sources", "sanction_flag",
    ])
    writer.writeheader()
    for i, c in enumerate(clusters, start=1):
        writer.writerow({
            "rank": i,
            "name": c["canonical_name"],
            "country": c["canonical_country"] or "",
            "types": ",".join(c["supplier_types"] or []),
            "address": c["canonical_address"] or "",
            "phone": c["canonical_phone"] or "",
            "email": c["canonical_email"] or "",
            "website": c["canonical_website"] or "",
            "tin": c["canonical_tin"] or "",
            "lei": c["canonical_lei"] or "",
            "confidence": round(c["confidence_score"], 3),
            "sources": c["source_count"],
            "sanction_flag": c["sanction_flag"],
        })

    output.seek(0)
    filename = f"suppliers_{job_id}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
