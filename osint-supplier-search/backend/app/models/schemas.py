from __future__ import annotations
from typing import Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


# ── Request schemas ────────────────────────────────────────────────────────────

class SearchFilters(BaseModel):
    countries: list[str] = Field(default_factory=list, description="ISO 3166-1 alpha-2 codes")
    supplier_types: list[str] = Field(
        default_factory=list,
        description="manufacturer|distributor|importer|exporter|wholesaler|trader"
    )
    adapters: list[str] = Field(default_factory=list, description="Empty = all enabled")


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    filters: SearchFilters = Field(default_factory=SearchFilters)


# ── Job schemas ────────────────────────────────────────────────────────────────

class JobProgress(BaseModel):
    adapters_done: int
    adapters_total: int
    candidates_found: int


class JobStatusResponse(BaseModel):
    job_id: UUID
    status: str
    query: str
    progress: JobProgress
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None


class SearchCreatedResponse(BaseModel):
    job_id: UUID
    status: str
    query: str
    polling_url: str


# ── Evidence & result schemas ──────────────────────────────────────────────────

class EvidenceLink(BaseModel):
    adapter: str
    source_url: str
    matched_fields: list[str]
    field_scores: dict[str, float]
    snippet: str | None = None
    scraped_at: datetime | None = None


class SupplierResult(BaseModel):
    rank: int
    cluster_id: UUID
    canonical_name: str
    canonical_country: str | None = None
    canonical_address: str | None = None
    canonical_phone: str | None = None
    canonical_email: str | None = None
    canonical_website: str | None = None
    canonical_tin: str | None = None
    canonical_lei: str | None = None
    supplier_types: list[str]
    industry_tags: list[str]
    sanction_flag: bool
    confidence_score: float
    rank_score: float
    source_count: int
    resolution_methods: list[str]
    evidence: list[EvidenceLink]


class SearchResultsResponse(BaseModel):
    job_id: UUID
    query: str
    status: str
    total_candidates_scraped: int
    total_clusters: int
    results: list[SupplierResult]
    completed_at: datetime | None = None


# ── Supplier profile (full detail) ────────────────────────────────────────────

class RawCandidateDetail(BaseModel):
    id: UUID
    adapter: str
    source_url: str
    raw_name: str | None
    raw_address: str | None
    raw_country: str | None
    raw_phone: str | None
    raw_email: str | None
    raw_website: str | None
    supplier_type: str | None
    scraped_at: datetime


class SupplierProfileResponse(BaseModel):
    cluster_id: UUID
    canonical_name: str
    canonical_country: str | None = None
    canonical_address: str | None = None
    canonical_phone: str | None = None
    canonical_email: str | None = None
    canonical_website: str | None = None
    canonical_tin: str | None = None
    canonical_lei: str | None = None
    supplier_types: list[str]
    industry_tags: list[str]
    description: str | None = None
    founding_year: int | None = None
    employee_range: str | None = None
    sanction_flag: bool
    confidence_score: float
    source_count: int
    resolution_methods: list[str]
    all_raw_names: list[str]
    evidence: list[EvidenceLink]
    raw_candidates: list[RawCandidateDetail]


# ── SSE event schemas ──────────────────────────────────────────────────────────

class SSEEvent(BaseModel):
    type: str   # adapter_complete | er_complete | job_complete | error
    data: dict[str, Any] = Field(default_factory=dict)


# ── Adapter management ─────────────────────────────────────────────────────────

class AddAdapterRequest(BaseModel):
    url: str = Field(..., description="URL of new source to add")
