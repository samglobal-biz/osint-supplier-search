from __future__ import annotations
import structlog

logger = structlog.get_logger()


async def compute_ranking(job_id: str):
    from app.db.rest_client import db_select, db_update

    clusters = await db_select("entity_clusters", job_id=job_id)
    if not clusters:
        return

    max_sources = max(c["source_count"] for c in clusters) or 1

    for cluster in clusters:
        confidence = cluster["confidence_score"]
        norm_sources = cluster["source_count"] / max_sources
        completeness = _completeness(cluster)
        registry_bonus = 1.0 if cluster.get("canonical_lei") or cluster.get("canonical_tin") else 0.0

        rank_score = round(
            0.30 * confidence
            + 0.25 * norm_sources
            + 0.20 * completeness
            + 0.10 * registry_bonus,
            4,
        )
        await db_update("entity_clusters", {"rank_score": rank_score}, id=str(cluster["id"]))

    logger.info("Ranking done", job_id=job_id, clusters=len(clusters))


def _completeness(cluster: dict) -> float:
    fields = [
        "canonical_name", "canonical_country", "canonical_address",
        "canonical_phone", "canonical_email", "canonical_website",
    ]
    filled = sum(1 for f in fields if cluster.get(f))
    return filled / len(fields)
