from __future__ import annotations
import asyncio
import structlog
from celery import group, chord
from workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(bind=True, name="workers.tasks.orchestrator.run_search")
def run_search(self, job_id: str, query: str, filters: dict):
    from adapters.registry import ADAPTERS
    from workers.tasks.entity_resolution import run_entity_resolution
    from workers.tasks.ranking import run_ranking

    requested = set(filters.get("adapters", []))
    adapters_to_run = [
        name for name, adapter in ADAPTERS.items()
        if adapter.enabled and (not requested or name in requested)
    ]

    logger.info("Starting search", job_id=job_id, query=query, adapters=adapters_to_run)
    asyncio.run(_update_job_status(job_id, "running", len(adapters_to_run)))

    adapter_tasks = group(
        run_adapter_task.s(job_id, query, filters, name)
        for name in adapters_to_run
    )
    workflow = chord(adapter_tasks)(
        run_entity_resolution.s(job_id) | run_ranking.s(job_id)
    )
    return workflow


@celery_app.task(bind=True, name="workers.tasks.orchestrator.run_adapter_task",
                 autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def run_adapter_task(self, job_id: str, query: str, filters: dict, adapter_name: str):
    from adapters.registry import ADAPTERS
    from app.models.schemas import SearchFilters

    adapter = ADAPTERS.get(adapter_name)
    if not adapter:
        logger.warning("Adapter not found", name=adapter_name)
        return {"adapter": adapter_name, "count": 0}

    search_filters = SearchFilters(**filters)
    candidates = asyncio.run(adapter.search_sync(job_id, query, search_filters))

    asyncio.run(_insert_candidates(job_id, candidates))
    asyncio.run(_increment_adapter_done(job_id, len(candidates)))

    logger.info("Adapter complete", adapter=adapter_name, candidates=len(candidates))
    return {"adapter": adapter_name, "count": len(candidates)}


async def _update_job_status(job_id: str, status: str, adapters_total: int):
    from app.db.rest_client import db_update
    await db_update("search_jobs", {"status": status, "adapters_total": adapters_total}, id=job_id)


async def _increment_adapter_done(job_id: str, new_candidates: int):
    # Read-modify-write: safe because --concurrency=1 (no parallel tasks)
    from app.db.rest_client import db_select, db_update
    rows = await db_select("search_jobs", select="adapters_done,candidates_found", id=job_id)
    if rows:
        done = (rows[0]["adapters_done"] or 0) + 1
        found = (rows[0]["candidates_found"] or 0) + new_candidates
        await db_update("search_jobs", {"adapters_done": done, "candidates_found": found}, id=job_id)


async def _insert_candidates(job_id: str, candidates: list[dict]):
    if not candidates:
        return
    from app.db.rest_client import db_insert
    rows = [
        {
            "job_id": job_id,
            "adapter": c.get("adapter", ""),
            "source_url": c.get("source_url", ""),
            "raw_name": c.get("raw_name"),
            "raw_address": c.get("raw_address"),
            "raw_country": c.get("raw_country"),
            "raw_phone": c.get("raw_phone"),
            "raw_email": c.get("raw_email"),
            "raw_website": c.get("raw_website"),
            "raw_description": c.get("raw_description"),
            "raw_tin": c.get("raw_tin"),
            "raw_lei": c.get("raw_lei"),
            "supplier_type": c.get("supplier_type"),
            "extra_fields": c.get("extra_fields", {}),
        }
        for c in candidates
    ]
    await db_insert("raw_candidates", rows)
