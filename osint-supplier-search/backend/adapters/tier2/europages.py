from __future__ import annotations
import re
import urllib.parse
import structlog
from selectolax.parser import HTMLParser
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
            url = f"https://www.europages.co.uk/en/search?cserpRedirect=1&text={encoded}"
            html = await self._get(url, headers=self._browser_headers())
            results = self._parse(html, query)
        except Exception as e:
            logger.warning("Europages search failed", error=str(e), query=query)

        await self._set_cached(query, results)
        return results

    def _parse(self, html: str, query: str) -> list[dict]:
        tree = HTMLParser(html)
        results = []

        # Try multiple possible card selectors
        cards = (
            tree.css("article[data-cy='company-card']") or
            tree.css("div.company-item") or
            tree.css("li.company-card") or
            tree.css("div[class*='CompanyCard']")
        )

        for card in cards[:20]:
            name = self._text(card, [
                "h2 a", "h2", ".company-name a", ".company-name",
                "[data-cy='company-name']", "a[class*='name']",
            ])
            if not name:
                continue

            country = self._text(card, [
                ".company-country", ".country", "span[class*='country']",
                "[data-cy='company-country']",
            ])
            address = self._text(card, [
                ".company-address", ".address", "address",
                "[data-cy='company-address']",
            ])
            description = self._text(card, [
                ".company-description", ".description", "p[class*='desc']",
            ])
            website = self._attr(card, [
                "a[href*='http']", ".company-website a",
            ], "href")
            source_url = self._attr(card, ["h2 a", "a[class*='company']"], "href") or ""
            if source_url and not source_url.startswith("http"):
                source_url = "https://www.europages.co.uk" + source_url

            results.append(self._make_candidate(
                source_url=source_url or f"https://www.europages.co.uk/en/search?text={urllib.parse.quote_plus(query)}",
                raw_name=name,
                raw_address=address,
                raw_country=country,
                raw_website=website,
                raw_description=description,
            ))

        logger.info("Europages results", count=len(results), query=query)
        return results

    def _text(self, node, selectors: list[str]) -> str:
        for sel in selectors:
            els = node.css(sel)
            if els:
                t = els[0].text(strip=True)
                if t:
                    return t
        return ""

    def _attr(self, node, selectors: list[str], attr: str) -> str:
        for sel in selectors:
            els = node.css(sel)
            if els:
                v = els[0].attributes.get(attr, "")
                if v:
                    return v
        return ""

    def _browser_headers(self) -> dict:
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
