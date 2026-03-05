from __future__ import annotations
import urllib.parse
import structlog
from adapters.base import BaseAdapter

logger = structlog.get_logger()


class ImportYetiAdapter(BaseAdapter):
    """ImportYeti — open US Bill of Lading database (importers/exporters)."""
    name = "importyeti"
    rate_limit_rpm = 10
    cache_ttl_hours = 48

    async def search(self, job_id: str, query: str, filters) -> list[dict]:
        cached = await self._get_cached(query)
        if cached is not None:
            return cached

        results = []
        try:
            # ImportYeti public search API
            encoded = urllib.parse.quote_plus(query)
            data = await self._get_json(
                f"https://www.importyeti.com/api/search/v3",
                params={"product": query, "page": 0},
                headers=self._browser_headers(),
            )
            results = self._parse(data, query)
        except Exception as e:
            logger.warning("ImportYeti search failed", error=str(e), query=query)

        await self._set_cached(query, results)
        return results

    def _parse(self, data: dict | list, query: str) -> list[dict]:
        results = []
        # Response is typically {"suppliers": [...]} or similar
        suppliers = []
        if isinstance(data, dict):
            suppliers = (
                data.get("suppliers") or
                data.get("results") or
                data.get("data") or
                []
            )
        elif isinstance(data, list):
            suppliers = data

        for item in suppliers[:25]:
            name = item.get("name") or item.get("companyName") or item.get("company_name") or ""
            if not name:
                continue

            country = item.get("country") or item.get("supplierCountry") or ""
            address = item.get("address") or item.get("supplierAddress") or ""
            website = item.get("website") or item.get("url") or ""
            slug = item.get("slug") or item.get("id") or ""
            source_url = f"https://www.importyeti.com/company/{slug}" if slug else "https://www.importyeti.com"

            results.append(self._make_candidate(
                source_url=source_url,
                raw_name=name,
                raw_country=country,
                raw_address=address,
                raw_website=website,
                supplier_type="exporter",
                extra_fields={
                    "shipment_count": item.get("shipmentCount") or item.get("shipments"),
                    "top_products": item.get("topProducts") or item.get("products"),
                },
            ))

        logger.info("ImportYeti results", count=len(results), query=query)
        return results

    def _browser_headers(self) -> dict:
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Referer": "https://www.importyeti.com/",
        }
