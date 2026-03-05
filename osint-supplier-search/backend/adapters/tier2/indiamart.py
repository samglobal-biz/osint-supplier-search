from __future__ import annotations
import urllib.parse, structlog
from adapters.base import BaseAdapter

logger = structlog.get_logger()


class IndiaMartAdapter(BaseAdapter):
    """IndiaMart — largest Indian B2B marketplace."""
    name = "indiamart"
    rate_limit_rpm = 5
    cache_ttl_hours = 24

    async def search(self, job_id, query, filters):
        cached = await self._get_cached(query)
        if cached is not None:
            return cached
        results = []
        try:
            # IndiaMart has a public search API endpoint
            encoded = urllib.parse.quote_plus(query)
            data = await self._get_json(
                "https://dir.indiamart.com/api/companyprofile/search/",
                params={"q": query, "mcatid": "", "start": 0, "limit": 20},
                headers=self._bh(),
            )
            results = self._parse(data, query)
        except Exception as e:
            logger.warning("IndiaMart failed", error=str(e))
        await self._set_cached(query, results)
        return results

    def _parse(self, data, query):
        results = []
        items = []
        if isinstance(data, dict):
            items = data.get("data") or data.get("result") or data.get("companies") or []
        elif isinstance(data, list):
            items = data

        for item in items[:20]:
            name = item.get("name") or item.get("companyName") or item.get("COMPANY_NAME") or ""
            if not name:
                continue
            city = item.get("city") or item.get("CITY") or ""
            phone = item.get("phone") or item.get("PHONE") or ""
            website = item.get("website") or item.get("WEBSITE") or ""
            slug = item.get("slug") or item.get("GLID") or ""
            results.append(self._make_candidate(
                source_url=f"https://www.indiamart.com/company/{slug}/" if slug else "https://www.indiamart.com",
                raw_name=name,
                raw_country="IN",
                raw_address=city,
                raw_phone=phone,
                raw_website=website,
                supplier_type="manufacturer",
            ))
        logger.info("IndiaMart results", count=len(results))
        return results

    def _bh(self):
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Referer": "https://www.indiamart.com/",
        }
