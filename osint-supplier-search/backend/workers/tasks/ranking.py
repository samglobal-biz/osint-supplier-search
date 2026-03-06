from __future__ import annotations
import asyncio
import structlog
from workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(bind=True, name="workers.tasks.ranking.run_ranking")
def run_ranking(self, job_id: str, _prev=None):
    from er.ranking import compute_ranking
    asyncio.run(compute_ranking(job_id))
    asyncio.run(_mark_complete(job_id))
    logger.info("Ranking complete, job done", job_id=job_id)
    return job_id


async def _mark_complete(job_id: str):
    from app.db.rest_client import db_update
    await db_update("search_jobs", {"status": "complete"}, id=job_id)
