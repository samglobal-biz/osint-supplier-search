from __future__ import annotations
import structlog

logger = structlog.get_logger()


async def compute_ranking(job_id: str):
    """
    Compute rank_score for each entity_cluster in a job.
    rank = 0.30*confidence + 0.25*norm(source_count) + 0.20*completeness + 0.15*recency + 0.10*registry_bonus
    """
    from app.db.session import get_pool
    pool = await get_pool()

    clusters = await pool.fetch(
        "SELECT * FROM entity_clusters WHERE job_id = $1::uuid",
        job_id,
    )
    if not clusters:
        return

    max_sources = max(c["source_count"] for c in clusters) or 1

    for cluster in clusters:
        confidence = cluster["confidence_score"]
        norm_sources = cluster["source_count"] / max_sources
        completeness = _completeness(cluster)
        registry_bonus = 1.0 if cluster["canonical_lei"] or cluster["canonical_tin"] else 0.0

        rank_score = (
            0.30 * confidence
            + 0.25 * norm_sources
            + 0.20 * completeness
            + 0.10 * registry_bonus
        )

        await pool.execute(
            "UPDATE entity_clusters SET rank_score=$1 WHERE id=$2",
            round(rank_score, 4),
            cluster["id"],
        )

    logger.info("Ranking done", job_id=job_id, clusters=len(clusters))


def _completeness(cluster) -> float:
    fields = [
        "canonical_name", "canonical_country", "canonical_address",
        "canonical_phone", "canonical_email", "canonical_website",
    ]
    filled = sum(1 for f in fields if cluster[f])
    return filled / len(fields)
