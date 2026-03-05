from __future__ import annotations
import asyncio
import structlog
from celery import group, chord
from workers.celery_app import celery_app
from adapters.registry import ADAPTERS

logger = structlog.get_logger()


@celery_app.task(bind=True, name="workers.tasks.orchestrator.run_search")
def run_search(self, job_id: str, query: str, filters: dict):
    """
    Fan-out: dispatch all enabled adapters in parallel.
    On completion, trigger entity resolution → ranking.
    """
    from workers.tasks.entity_resolution import run_entity_resolution
    from workers.tasks.ranking import run_ranking

    # Determine which adapters to run
    requested = set(filters.get("adapters", []))
    adapters_to_run = [
        name for name, adapter in ADAPTERS.items()
        if adapter.enabled and (not requested or name in requested)
    ]

    logger.info("Starting search", job_id=job_id, query=query, adapters=adapters_to_run)

    # Update job: running + total adapters count
    asyncio.run(_update_job_status(job_id, "running", len(adapters_to_run)))

    # Build Celery group of adapter tasks
    adapter_tasks = group(
        run_adapter_task.s(job_id, query, filters, name)
        for name in adapters_to_run
    )

    # chord: run all adapters, then ER, then ranking
    workflow = chord(adapter_tasks)(
        run_entity_resolution.s(job_id) | run_ranking.s(job_id)
    )
    return workflow


@celery_app.task(bind=True, name="workers.tasks.orchestrator.run_adapter_task",
                 autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def run_adapter_task(self, job_id: str, query: str, filters: dict, adapter_name: str):
    """Run a single adapter and insert raw_candidates."""
    from adapters.registry import ADAPTERS
    from app.models.schemas import SearchFilters

    adapter = ADAPTERS.get(adapter_name)
    if not adapter:
        logger.warning("Adapter not found", name=adapter_name)
        return {"adapter": adapter_name, "count": 0}

    search_filters = SearchFilters(**filters)
    candidates = asyncio.run(adapter.search_sync(job_id, query, search_filters))

    # Persist to DB
    asyncio.run(_insert_candidates(job_id, candidates))
    asyncio.run(_increment_adapters_done(job_id, len(candidates)))

    logger.info("Adapter complete", adapter=adapter_name, candidates=len(candidates))
    return {"adapter": adapter_name, "count": len(candidates)}


# ── Async DB helpers ───────────────────────────────────────────────────────────

async def _update_job_status(job_id: str, status: str, adapters_total: int):
    from app.db.session import get_pool
    pool = await get_pool()
    await pool.execute(
        "UPDATE search_jobs SET status=$1, adapters_total=$2 WHERE id=$3::uuid",
        status, adapters_total, job_id,
    )


async def _increment_adapters_done(job_id: str, new_candidates: int):
    from app.db.session import get_pool
    pool = await get_pool()
    await pool.execute(
        """
        UPDATE search_jobs
        SET adapters_done = adapters_done + 1,
            candidates_found = candidates_found + $1,
            status = CASE
                WHEN adapters_done + 1 >= adapters_total THEN 'partial'
                ELSE status
            END
        WHERE id = $2::uuid
        """,
        new_candidates, job_id,
    )


async def _insert_candidates(job_id: str, candidates: list[dict]):
    if not candidates:
        return
    from app.db.session import get_pool
    pool = await get_pool()
    await pool.executemany(
        """
        INSERT INTO raw_candidates
            (job_id, adapter, source_url, raw_name, raw_address, raw_country,
             raw_phone, raw_email, raw_website, raw_description,
             raw_tin, raw_lei, supplier_type, extra_fields)
        VALUES ($1::uuid,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14::jsonb)
        """,
        [
            (
                job_id,
                c.get("adapter", ""),
                c.get("source_url", ""),
                c.get("raw_name"),
                c.get("raw_address"),
                c.get("raw_country"),
                c.get("raw_phone"),
                c.get("raw_email"),
                c.get("raw_website"),
                c.get("raw_description"),
                c.get("raw_tin"),
                c.get("raw_lei"),
                c.get("supplier_type"),
                c.get("extra_fields", "{}"),
            )
            for c in candidates
        ],
    )
