from __future__ import annotations
import structlog
from adapters.base import BaseAdapter

logger = structlog.get_logger()

GLEIF_BASE = "https://api.gleif.org/api/v1"


class GleifAdapter(BaseAdapter):
    name = "gleif"
    rate_limit_rpm = 60
    cache_ttl_hours = 72

    async def search(self, job_id: str, query: str, filters) -> list[dict]:
        cached = await self._get_cached(query)
        if cached is not None:
            return cached

        try:
            data = await self._get_json(
                f"{GLEIF_BASE}/lei-records",
                params={"filter[entity.legalName]": query, "page[size]": 20},
            )
        except Exception as e:
            logger.warning("GLEIF fetch failed", error=str(e))
            return []

        results = []
        for item in data.get("data", []):
            attrs = item.get("attributes", {})
            entity = attrs.get("entity", {})
            legal_address = entity.get("legalAddress", {})
            hq_address = entity.get("headquartersAddress", {})
            addr = hq_address or legal_address

            lei = attrs.get("lei", "")
            candidate = self._make_candidate(
                source_url=f"https://www.gleif.org/lei/{lei}",
                raw_name=entity.get("legalName", {}).get("name"),
                raw_lei=lei,
                raw_country=addr.get("country"),
                raw_address=self._fmt(addr),
                raw_website=entity.get("registeredAt", {}).get("website"),
                supplier_type=None,
            )
            if candidate.get("raw_name"):
                results.append(candidate)

        await self._set_cached(query, results)
        logger.info("GLEIF done", count=len(results), query=query)
        return results

    def _fmt(self, addr: dict) -> str | None:
        parts = [
            " ".join(addr.get("addressLines", [])),
            addr.get("city"),
            addr.get("postalCode"),
            addr.get("country"),
        ]
        return ", ".join(p for p in parts if p) or None
