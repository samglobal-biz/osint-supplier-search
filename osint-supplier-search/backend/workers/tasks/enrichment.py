from __future__ import annotations
import asyncio
import structlog
from workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(bind=True, name="workers.tasks.enrichment.run_enrichment")
def run_enrichment(self, job_id: str):
    """Enrich entity clusters with contact info scraped from company websites."""
    asyncio.run(_do_enrichment(job_id))
    asyncio.run(_mark_complete(job_id))
    logger.info("Enrichment complete, job done", job_id=job_id)
    return job_id


async def _do_enrichment(job_id: str):
    from adapters.tier2.direct_website import DirectWebsiteAdapter
    from app.db.rest_client import db_select, db_update

    clusters = await db_select("entity_clusters", job_id=job_id)
    if not clusters:
        return

    adapter = DirectWebsiteAdapter()
    enriched = 0

    for cluster in clusters:
        website = cluster.get("canonical_website")
        if not website:
            continue
        if cluster.get("canonical_email") and cluster.get("canonical_phone"):
            continue  # Already complete

        url = f"https://{website}" if not website.startswith("http") else website
        try:
            contacts = await adapter.enrich_contact_page(url)
        except Exception as e:
            logger.debug("Enrich failed", cluster_id=cluster["id"], error=str(e))
            continue

        updates = {}
        if contacts.get("emails") and not cluster.get("canonical_email"):
            updates["canonical_email"] = contacts["emails"][0]
        if contacts.get("phones") and not cluster.get("canonical_phone"):
            updates["canonical_phone"] = contacts["phones"][0]

        if updates:
            await db_update("entity_clusters", updates, id=str(cluster["id"]))
            enriched += 1

    logger.info("Enrichment done", job_id=job_id, clusters_enriched=enriched)


async def _mark_complete(job_id: str):
    from app.db.rest_client import db_update
    await db_update("search_jobs", {"status": "complete"}, id=job_id)
