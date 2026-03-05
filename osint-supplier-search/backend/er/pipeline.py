from __future__ import annotations
import json
import structlog
from er.normalizer import (
    normalize_name, normalize_phone, normalize_website,
    normalize_country, normalize_email,
)

logger = structlog.get_logger()


async def run_er_pipeline(job_id: str):
    """
    Full Entity Resolution pipeline for a completed search job.
    Reads raw_candidates, clusters them, writes entity_clusters + evidence_links.
    """
    from app.db.session import get_pool
    pool = await get_pool()

    # Load all raw candidates for this job
    rows = await pool.fetch(
        "SELECT * FROM raw_candidates WHERE job_id = $1::uuid",
        job_id,
    )
    if not rows:
        return

    candidates = [dict(r) for r in rows]
    logger.info("ER pipeline start", job_id=job_id, candidates=len(candidates))

    # Normalize all candidates
    normalized = [_normalize_candidate(c) for c in candidates]

    # Build clusters via hard match first, then fuzzy
    clusters = _build_clusters(normalized)

    # Persist clusters and evidence
    for cluster in clusters:
        await _persist_cluster(pool, job_id, cluster)

    logger.info("ER pipeline done", job_id=job_id, clusters=len(clusters))


def _normalize_candidate(c: dict) -> dict:
    return {
        **c,
        "norm_name": normalize_name(c.get("raw_name")),
        "norm_phone": normalize_phone(c.get("raw_phone")),
        "norm_website": normalize_website(c.get("raw_website")),
        "norm_country": normalize_country(c.get("raw_country")),
        "norm_email": normalize_email(c.get("raw_email")),
    }


def _build_clusters(candidates: list[dict]) -> list[dict]:
    """
    Assign each candidate to a cluster.
    Returns list of cluster dicts, each with a 'members' list.
    """
    clusters: list[dict] = []
    assigned: set[str] = set()  # candidate IDs already clustered

    for cand in candidates:
        cid = str(cand["id"])
        if cid in assigned:
            continue

        # Start new cluster with this candidate as seed
        cluster_members = [cand]
        assigned.add(cid)

        # Find all candidates that hard-match this one
        for other in candidates:
            oid = str(other["id"])
            if oid in assigned:
                continue
            match_result = _hard_match(cand, other)
            if match_result:
                cluster_members.append(other)
                assigned.add(oid)
                continue
            # Fuzzy match
            score, fields = _fuzzy_match(cand, other)
            if score >= 0.92:
                cluster_members.append(other)
                assigned.add(oid)

        clusters.append(_build_cluster_dict(cluster_members))

    return clusters


def _hard_match(a: dict, b: dict) -> str | None:
    """Return match method name if hard match, else None."""
    if a.get("raw_lei") and a["raw_lei"] == b.get("raw_lei"):
        return "lei_match"
    if a.get("raw_tin") and a["raw_tin"] == b.get("raw_tin") and \
       a.get("norm_country") == b.get("norm_country"):
        return "tin_match"
    if a.get("norm_website") and a["norm_website"] == b.get("norm_website"):
        return "website_match"
    if a.get("norm_phone") and a["norm_phone"] == b.get("norm_phone"):
        return "phone_match"
    return None


def _fuzzy_match(a: dict, b: dict) -> tuple[float, list[str]]:
    """Return (combined_score, matched_fields)."""
    from rapidfuzz import fuzz as rfuzz

    name_a = a.get("norm_name", "")
    name_b = b.get("norm_name", "")
    if not name_a or not name_b:
        return 0.0, []

    # Name similarity (three metrics combined)
    token_sort = rfuzz.token_sort_ratio(name_a, name_b) / 100
    partial = rfuzz.partial_ratio(name_a, name_b) / 100
    name_score = 0.5 * token_sort + 0.3 * partial + 0.2 * _phonetic_sim(name_a, name_b)

    # Address / city bonus (only same country)
    addr_score = 0.0
    if a.get("norm_country") == b.get("norm_country") and a.get("raw_address") and b.get("raw_address"):
        addr_score = rfuzz.token_set_ratio(a["raw_address"], b["raw_address"]) / 100

    combined = 0.65 * name_score + 0.35 * addr_score
    fields = ["name"] if name_score > 0.7 else []
    if addr_score > 0.7:
        fields.append("address")

    return combined, fields


def _phonetic_sim(a: str, b: str) -> float:
    """Simple phonetic similarity using Soundex."""
    try:
        import phonetics
        sx_a = phonetics.soundex(a.split()[0]) if a.split() else ""
        sx_b = phonetics.soundex(b.split()[0]) if b.split() else ""
        return 1.0 if sx_a == sx_b and sx_a else 0.0
    except Exception:
        return 0.0


def _build_cluster_dict(members: list[dict]) -> dict:
    """Select canonical field values using source priority."""
    # Priority: GLEIF > OpenCorporates > others
    priority = ["gleif", "opencorporates", "kompass", "europages",
                 "alibaba", "yellowpages", "direct_website"]

    def best_field(field: str) -> str | None:
        for src in priority:
            for m in members:
                if m.get("adapter") == src and m.get(field):
                    return m[field]
        # Fallback: first non-null
        for m in members:
            if m.get(field):
                return m[field]
        return None

    # Collect resolution methods
    methods = set()
    if len(members) > 1:
        for i, a in enumerate(members):
            for b in members[i+1:]:
                method = _hard_match(a, b)
                if method:
                    methods.add(method)
                else:
                    score, _ = _fuzzy_match(a, b)
                    if score >= 0.92:
                        methods.add("name_fuzzy")

    # Compute confidence
    source_count = len(members)
    has_lei = any(m.get("raw_lei") for m in members)
    has_tin = any(m.get("raw_tin") for m in members)
    base_conf = 0.60 + 0.05 * min(source_count - 1, 3)
    if has_lei:
        base_conf += 0.03
    if has_tin:
        base_conf += 0.02
    confidence = min(base_conf, 1.0)

    # Aggregate supplier types
    supplier_types = list({m["supplier_type"] for m in members if m.get("supplier_type")})

    return {
        "members": members,
        "canonical_name": best_field("raw_name"),
        "canonical_address": best_field("raw_address"),
        "canonical_country": best_field("norm_country"),
        "canonical_phone": best_field("norm_phone"),
        "canonical_email": best_field("norm_email"),
        "canonical_website": best_field("norm_website"),
        "canonical_tin": best_field("raw_tin"),
        "canonical_lei": best_field("raw_lei"),
        "supplier_types": supplier_types,
        "source_count": source_count,
        "confidence_score": round(confidence, 4),
        "resolution_methods": list(methods),
    }


async def _persist_cluster(pool, job_id: str, cluster: dict):
    """Insert entity_cluster + evidence_links, update raw_candidates.cluster_id."""
    cluster_id = await pool.fetchval(
        """
        INSERT INTO entity_clusters
            (job_id, canonical_name, canonical_address, canonical_country,
             canonical_phone, canonical_email, canonical_website,
             canonical_tin, canonical_lei, supplier_types,
             source_count, confidence_score, resolution_methods)
        VALUES ($1::uuid,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
        RETURNING id
        """,
        job_id,
        cluster["canonical_name"],
        cluster["canonical_address"],
        cluster["canonical_country"],
        cluster["canonical_phone"],
        cluster["canonical_email"],
        cluster["canonical_website"],
        cluster["canonical_tin"],
        cluster["canonical_lei"],
        cluster["supplier_types"],
        cluster["source_count"],
        cluster["confidence_score"],
        cluster["resolution_methods"],
    )

    # Link raw candidates to cluster
    member_ids = [m["id"] for m in cluster["members"]]
    await pool.execute(
        "UPDATE raw_candidates SET cluster_id=$1 WHERE id = ANY($2::uuid[])",
        cluster_id, member_ids,
    )

    # Insert evidence links
    for member in cluster["members"]:
        await pool.execute(
            """
            INSERT INTO evidence_links
                (cluster_id, raw_candidate_id, adapter, source_url,
                 matched_fields, snippet, scraped_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7)
            """,
            cluster_id,
            member["id"],
            member["adapter"],
            member.get("source_url", ""),
            ["name"],
            member.get("raw_description"),
            member.get("scraped_at"),
        )
