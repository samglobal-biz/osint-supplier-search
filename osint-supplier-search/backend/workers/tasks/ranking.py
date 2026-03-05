from __future__ import annotations
import asyncio
import structlog
from workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(bind=True, name="workers.tasks.ranking.run_ranking")
def run_ranking(self, job_id: str, _prev=None):
    """Compute rank_score for each cluster and mark job complete."""
    from er.ranking import compute_ranking
    asyncio.run(compute_ranking(job_id))
    asyncio.run(_mark_complete(job_id))
    logger.info("Ranking complete, job done", job_id=job_id)
    return job_id


async def _mark_complete(job_id: str):
    from app.db.session import get_pool
    pool = await get_pool()
    await pool.execute(
        "UPDATE search_jobs SET status='complete', completed_at=NOW() WHERE id=$1::uuid",
        job_id,
    )
