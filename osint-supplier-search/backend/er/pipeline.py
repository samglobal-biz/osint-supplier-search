from __future__ import annotations
import structlog
from er.normalizer import (
    normalize_name, normalize_phone, normalize_website,
    normalize_country, normalize_email,
)

logger = structlog.get_logger()


async def run_er_pipeline(job_id: str):
    from app.db.rest_client import db_select

    rows = await db_select("raw_candidates", job_id=job_id)
    if not rows:
        return

    logger.info("ER pipeline start", job_id=job_id, candidates=len(rows))
    normalized = [_normalize_candidate(c) for c in rows]
    clusters = _build_clusters(normalized)

    for cluster in clusters:
        await _persist_cluster(job_id, cluster)

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
    clusters: list[dict] = []
    assigned: set[str] = set()

    for cand in candidates:
        cid = str(cand["id"])
        if cid in assigned:
            continue

        cluster_members = [cand]
        assigned.add(cid)

        for other in candidates:
            oid = str(other["id"])
            if oid in assigned:
                continue
            if _hard_match(cand, other):
                cluster_members.append(other)
                assigned.add(oid)
                continue
            score, _ = _fuzzy_match(cand, other)
            if score >= 0.92:
                cluster_members.append(other)
                assigned.add(oid)

        clusters.append(_build_cluster_dict(cluster_members))

    return clusters


def _hard_match(a: dict, b: dict) -> str | None:
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
    from rapidfuzz import fuzz as rfuzz
    name_a = a.get("norm_name", "")
    name_b = b.get("norm_name", "")
    if not name_a or not name_b:
        return 0.0, []

    token_sort = rfuzz.token_sort_ratio(name_a, name_b) / 100
    partial = rfuzz.partial_ratio(name_a, name_b) / 100
    name_score = 0.5 * token_sort + 0.3 * partial + 0.2 * _phonetic_sim(name_a, name_b)

    addr_score = 0.0
    if a.get("norm_country") == b.get("norm_country") and a.get("raw_address") and b.get("raw_address"):
        addr_score = rfuzz.token_set_ratio(a["raw_address"], b["raw_address"]) / 100

    combined = 0.65 * name_score + 0.35 * addr_score
    fields = ["name"] if name_score > 0.7 else []
    if addr_score > 0.7:
        fields.append("address")
    return combined, fields


def _phonetic_sim(a: str, b: str) -> float:
    try:
        import phonetics
        sx_a = phonetics.soundex(a.split()[0]) if a.split() else ""
        sx_b = phonetics.soundex(b.split()[0]) if b.split() else ""
        return 1.0 if sx_a == sx_b and sx_a else 0.0
    except Exception:
        return 0.0


def _build_cluster_dict(members: list[dict]) -> dict:
    priority = ["gleif", "opencorporates", "kompass", "europages",
                "alibaba", "yellowpages", "direct_website"]

    def best_field(field: str) -> str | None:
        for src in priority:
            for m in members:
                if m.get("adapter") == src and m.get(field):
                    return m[field]
        for m in members:
            if m.get(field):
                return m[field]
        return None

    methods = set()
    if len(members) > 1:
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                method = _hard_match(a, b)
                if method:
                    methods.add(method)
                else:
                    score, _ = _fuzzy_match(a, b)
                    if score >= 0.92:
                        methods.add("name_fuzzy")

    source_count = len(members)
    has_lei = any(m.get("raw_lei") for m in members)
    has_tin = any(m.get("raw_tin") for m in members)
    base_conf = 0.60 + 0.05 * min(source_count - 1, 3)
    if has_lei:
        base_conf += 0.03
    if has_tin:
        base_conf += 0.02
    confidence = min(base_conf, 1.0)

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
        "supplier_types": list({m["supplier_type"] for m in members if m.get("supplier_type")}),
        "source_count": source_count,
        "confidence_score": round(confidence, 4),
        "resolution_methods": list(methods),
    }


async def _persist_cluster(job_id: str, cluster: dict):
    from app.db.rest_client import db_insert, db_update_in

    rows = await db_insert("entity_clusters", {
        "job_id": job_id,
        "canonical_name": cluster["canonical_name"],
        "canonical_address": cluster["canonical_address"],
        "canonical_country": cluster["canonical_country"],
        "canonical_phone": cluster["canonical_phone"],
        "canonical_email": cluster["canonical_email"],
        "canonical_website": cluster["canonical_website"],
        "canonical_tin": cluster["canonical_tin"],
        "canonical_lei": cluster["canonical_lei"],
        "supplier_types": cluster["supplier_types"],
        "source_count": cluster["source_count"],
        "confidence_score": cluster["confidence_score"],
        "resolution_methods": cluster["resolution_methods"],
    })
    cluster_id = rows[0]["id"]

    member_ids = [str(m["id"]) for m in cluster["members"]]
    await db_update_in("raw_candidates", {"cluster_id": cluster_id}, "id", member_ids)

    evidence = [
        {
            "cluster_id": cluster_id,
            "raw_candidate_id": str(m["id"]),
            "adapter": m["adapter"],
            "source_url": m.get("source_url", ""),
            "matched_fields": ["name"],
            "snippet": m.get("raw_description"),
            "scraped_at": m.get("scraped_at"),
        }
        for m in cluster["members"]
    ]
    await db_insert("evidence_links", evidence)
