from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
import csv
import io
from app.models.schemas import SupplierProfileResponse, EvidenceLink, RawCandidateDetail
from app.core.security import get_current_user_id
from app.db.rest_client import db_select

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


@router.get("/{cluster_id}", response_model=SupplierProfileResponse)
async def get_supplier_profile(
    cluster_id: UUID,
    user_id: str = Depends(get_current_user_id),
):
    clusters = await db_select("entity_clusters", id=str(cluster_id))
    if not clusters:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    cluster = clusters[0]

    # Verify user owns the job
    jobs = await db_select("search_jobs", id=cluster["job_id"], user_id=user_id)
    if not jobs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")

    evidence_rows = await db_select("evidence_links", cluster_id=str(cluster_id), order="scraped_at.desc")
    raw_rows = await db_select("raw_candidates", cluster_id=str(cluster_id), order="scraped_at.desc")
    all_raw_names = list({r["raw_name"] for r in raw_rows if r.get("raw_name")})

    return SupplierProfileResponse(
        cluster_id=cluster["id"],
        canonical_name=cluster["canonical_name"],
        canonical_country=cluster.get("canonical_country"),
        canonical_address=cluster.get("canonical_address"),
        canonical_phone=cluster.get("canonical_phone"),
        canonical_email=cluster.get("canonical_email"),
        canonical_website=cluster.get("canonical_website"),
        canonical_tin=cluster.get("canonical_tin"),
        canonical_lei=cluster.get("canonical_lei"),
        supplier_types=list(cluster.get("supplier_types") or []),
        industry_tags=list(cluster.get("industry_tags") or []),
        description=cluster.get("description"),
        founding_year=cluster.get("founding_year"),
        employee_range=cluster.get("employee_range"),
        sanction_flag=cluster.get("sanction_flag", False),
        confidence_score=cluster.get("confidence_score", 0),
        source_count=cluster.get("source_count", 1),
        resolution_methods=list(cluster.get("resolution_methods") or []),
        all_raw_names=all_raw_names,
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
        raw_candidates=[
            RawCandidateDetail(
                id=r["id"],
                adapter=r["adapter"],
                source_url=r["source_url"],
                raw_name=r.get("raw_name"),
                raw_address=r.get("raw_address"),
                raw_country=r.get("raw_country"),
                raw_phone=r.get("raw_phone"),
                raw_email=r.get("raw_email"),
                raw_website=r.get("raw_website"),
                supplier_type=r.get("supplier_type"),
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
    jobs = await db_select("search_jobs", id=str(job_id), user_id=user_id)
    if not jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    clusters = await db_select("entity_clusters", job_id=str(job_id), order="rank_score.desc")

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
            "country": c.get("canonical_country") or "",
            "types": ",".join(c.get("supplier_types") or []),
            "address": c.get("canonical_address") or "",
            "phone": c.get("canonical_phone") or "",
            "email": c.get("canonical_email") or "",
            "website": c.get("canonical_website") or "",
            "tin": c.get("canonical_tin") or "",
            "lei": c.get("canonical_lei") or "",
            "confidence": round(c.get("confidence_score", 0), 3),
            "sources": c.get("source_count", 1),
            "sanction_flag": c.get("sanction_flag", False),
        })

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="suppliers_{job_id}.csv"'},
    )
