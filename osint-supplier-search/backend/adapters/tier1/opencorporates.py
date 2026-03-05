from __future__ import annotations
import structlog
from adapters.base import BaseAdapter
from app.config import settings

logger = structlog.get_logger()

OPEN_CORP_BASE = "https://api.opencorporates.com/v0.4"


class OpenCorporatesAdapter(BaseAdapter):
    name = "opencorporates"
    rate_limit_rpm = 5
    cache_ttl_hours = 48  # registry data changes slowly

    async def search(self, job_id: str, query: str, filters) -> list[dict]:
        # Check cache first
        cached = await self._get_cached(query)
        if cached is not None:
            logger.info("Cache hit", adapter=self.name, query=query)
            return cached

        params: dict = {
            "q": query,
            "per_page": 30,
            "format": "json",
        }
        # Filter by country if specified
        countries = getattr(filters, "countries", [])
        if countries:
            params["jurisdiction_code"] = countries[0].lower()  # OC uses first country

        if settings.opencorporates_api_key:
            params["api_token"] = settings.opencorporates_api_key

        try:
            data = await self._get_json(f"{OPEN_CORP_BASE}/companies/search", params=params)
        except Exception as e:
            logger.warning("OpenCorporates fetch failed", error=str(e))
            return []

        results = []
        companies = data.get("results", {}).get("companies", [])
        for item in companies:
            c = item.get("company", {})
            candidate = self._make_candidate(
                source_url=c.get("opencorporates_url", ""),
                raw_name=c.get("name"),
                raw_address=self._format_address(c.get("registered_address") or {}),
                raw_country=self._get_country(c),
                raw_tin=c.get("company_number"),
                raw_website=self._extract_website(c),
                supplier_type=None,  # registries don't classify supplier type
                raw_description=c.get("current_status"),
                extra_fields=f'{{"jurisdiction": "{c.get("jurisdiction_code", "")}", "company_type": "{c.get("company_type", "")}"}}'
            )
            if candidate.get("raw_name"):
                results.append(candidate)

        await self._set_cached(query, results)
        logger.info("OpenCorporates done", count=len(results), query=query)
        return results

    def _format_address(self, addr: dict) -> str | None:
        if not addr:
            return None
        parts = [
            addr.get("street_address"),
            addr.get("locality"),
            addr.get("region"),
            addr.get("postal_code"),
            addr.get("country"),
        ]
        return ", ".join(p for p in parts if p) or None

    def _get_country(self, company: dict) -> str | None:
        jc = company.get("jurisdiction_code", "")
        if "_" in jc:
            return jc.split("_")[0].upper()
        return jc.upper() if jc else None

    def _extract_website(self, company: dict) -> str | None:
        for key in ("website", "home_page"):
            val = company.get(key)
            if val:
                return val
        return None
