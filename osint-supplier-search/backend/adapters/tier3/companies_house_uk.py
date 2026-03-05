from __future__ import annotations
import urllib.parse, structlog
from adapters.base import BaseAdapter

logger = structlog.get_logger()


class CompaniesHouseUKAdapter(BaseAdapter):
    """Companies House UK — official UK company registry (free API, no key needed for basic)."""
    name = "companies_house_uk"
    rate_limit_rpm = 10
    cache_ttl_hours = 72

    async def search(self, job_id, query, filters):
        cached = await self._get_cached(query)
        if cached is not None:
            return cached
        results = []
        try:
            data = await self._get_json(
                "https://api.company-information.service.gov.uk/search/companies",
                params={"q": query, "items_per_page": 20},
                headers={"Accept": "application/json", "User-Agent": "OSINTSupplierBot/1.0"},
            )
            results = self._parse(data, query)
        except Exception as e:
            logger.warning("CompaniesHouseUK failed", error=str(e))
        await self._set_cached(query, results)
        return results

    def _parse(self, data, query):
        results = []
        items = data.get("items") or [] if isinstance(data, dict) else []
        for item in items[:20]:
            name = item.get("title") or ""
            if not name:
                continue
            address = item.get("address", {})
            addr_str = ", ".join(filter(None, [
                address.get("premises"), address.get("address_line_1"),
                address.get("locality"), address.get("postal_code"),
            ]))
            company_number = item.get("company_number", "")
            status = item.get("company_status", "")
            results.append(self._make_candidate(
                source_url=f"https://find-and-update.company-information.service.gov.uk/company/{company_number}",
                raw_name=name,
                raw_country="GB",
                raw_address=addr_str,
                extra_fields={"company_number": company_number, "status": status, "type": item.get("company_type")},
            ))
        logger.info("CompaniesHouseUK results", count=len(results))
        return results
