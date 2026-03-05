from __future__ import annotations
import urllib.parse, structlog
from adapters.base import BaseAdapter

logger = structlog.get_logger()


class OpenSanctionsAdapter(BaseAdapter):
    """OpenSanctions — free aggregated sanctions/PEP database. Used for compliance checks."""
    name = "open_sanctions"
    rate_limit_rpm = 10
    cache_ttl_hours = 24

    async def search(self, job_id, query, filters):
        cached = await self._get_cached(query)
        if cached is not None:
            return cached
        results = []
        try:
            data = await self._get_json(
                "https://api.opensanctions.org/match/default",
                params={"q": query, "schema": "Organization", "limit": 20},
                headers={"Accept": "application/json", "User-Agent": "OSINTSupplierBot/1.0"},
            )
            results = self._parse(data, query)
        except Exception as e:
            logger.warning("OpenSanctions failed", error=str(e))
        await self._set_cached(query, results)
        return results

    def _parse(self, data, query):
        results = []
        items = []
        if isinstance(data, dict):
            items = data.get("results") or data.get("entities") or []
        for item in items:
            props = item.get("properties") or {}
            names = props.get("name") or []
            name = names[0] if names else item.get("caption") or ""
            if not name:
                continue
            countries = props.get("country") or []
            addresses = props.get("address") or []
            results.append(self._make_candidate(
                source_url=f"https://www.opensanctions.org/entities/{item.get('id', '')}",
                raw_name=name,
                raw_country=countries[0] if countries else "",
                raw_address=addresses[0] if addresses else "",
                extra_fields={"sanction_flag": True, "datasets": item.get("datasets"), "score": item.get("score")},
            ))
        logger.info("OpenSanctions results", count=len(results))
        return results
