from __future__ import annotations
import asyncio
import structlog
from workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(bind=True, name="workers.tasks.entity_resolution.run_entity_resolution")
def run_entity_resolution(self, adapter_results: list[dict], job_id: str):
    """
    Cluster raw_candidates into entity_clusters.
    Runs after all adapters complete (chord callback).
    """
    from er.pipeline import run_er_pipeline
    asyncio.run(run_er_pipeline(job_id))
    logger.info("ER complete", job_id=job_id)
    return job_id
