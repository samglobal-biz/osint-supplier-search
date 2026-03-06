from __future__ import annotations
import json
import re
import urllib.parse
import structlog
from adapters.base import BaseAdapter

logger = structlog.get_logger()


class EuropagesAdapter(BaseAdapter):
    name = "europages"
    rate_limit_rpm = 10
    cache_ttl_hours = 24

    async def search(self, job_id: str, query: str, filters) -> list[dict]:
        cached = await self._get_cached(query)
        if cached is not None:
            return cached

        results = []
        try:
            encoded = urllib.parse.quote_plus(query)
            url = f"https://www.europages.co.uk/en/search?text={encoded}"
            html = await self._get(url, headers=self._browser_headers())
            results = self._parse(html, query)
        except Exception as e:
            logger.warning("Europages search failed", error=str(e), query=query)

        await self._set_cached(query, results)
        return results

    def _parse(self, html: str, query: str) -> list[dict]:
        results = []

        # Parse JSON-LD structured data (most reliable)
        for match in re.finditer(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL):
            try:
                data = json.loads(match.group(1))
                items = self._extract_items(data)
                if items:
                    results.extend(items)
            except (json.JSONDecodeError, KeyError):
                continue

        # Deduplicate by name
        seen = set()
        unique = []
        for r in results:
            if r.get("raw_name") and r["raw_name"] not in seen:
                seen.add(r["raw_name"])
                unique.append(r)

        logger.info("Europages results", count=len(unique), query=query)
        return unique[:30]

    def _extract_items(self, data: dict | list) -> list[dict]:
        results = []
        if isinstance(data, list):
            for item in data:
                results.extend(self._extract_items(item))
            return results

        # Handle @graph array
        if "@graph" in data:
            for item in data["@graph"]:
                results.extend(self._extract_items(item))

        # Handle ItemList
        if data.get("@type") == "ItemList" and "itemListElement" in data:
            for list_item in data["itemListElement"]:
                org = list_item.get("item", {})
                if org.get("@type") == "Organization":
                    addr = org.get("address", {})
                    country = addr.get("addressCountry")
                    city = addr.get("addressLocality")
                    address = ", ".join(p for p in [city, country] if p) or None
                    results.append(self._make_candidate(
                        source_url=org.get("url", ""),
                        raw_name=org.get("name"),
                        raw_country=country,
                        raw_address=address,
                    ))

        return results

    def _browser_headers(self) -> dict:
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
