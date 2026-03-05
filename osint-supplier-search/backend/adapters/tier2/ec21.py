from __future__ import annotations
import urllib.parse
import structlog
from selectolax.parser import HTMLParser
from adapters.base import BaseAdapter

logger = structlog.get_logger()


class EC21Adapter(BaseAdapter):
    """EC21 — Korean global B2B trading platform."""
    name = "ec21"
    rate_limit_rpm = 10
    cache_ttl_hours = 24

    async def search(self, job_id: str, query: str, filters) -> list[dict]:
        cached = await self._get_cached(query)
        if cached is not None:
            return cached

        results = []
        try:
            encoded = urllib.parse.quote_plus(query)
            url = f"https://www.ec21.com/trade/{encoded}/"
            html = await self._get(url, headers=self._browser_headers())
            results = self._parse(html, query)
        except Exception as e:
            logger.warning("EC21 search failed", error=str(e), query=query)

        await self._set_cached(query, results)
        return results

    def _parse(self, html: str, query: str) -> list[dict]:
        tree = HTMLParser(html)
        results = []

        cards = (
            tree.css("div.wrd-list-row") or
            tree.css("li.company-list-item") or
            tree.css("div[class*='seller']") or
            tree.css("div.list-box") or
            tree.css("ul.list-product > li")
        )

        for card in cards[:20]:
            name = self._text(card, [
                "strong.company-name", ".company-name a", "a.name",
                "h3 a", "h4 a", ".seller-name",
            ])
            if not name:
                continue

            country = self._text(card, [
                ".country", "span.flag + span", ".company-country",
                "span[class*='country']",
            ])
            description = self._text(card, [
                ".product-name", "p.desc", ".description",
            ])
            link = self._attr(card, ["a.name", "a[href*='/sell/']", "h3 a", "h4 a"], "href")
            if link and not link.startswith("http"):
                link = "https://www.ec21.com" + link

            results.append(self._make_candidate(
                source_url=link or f"https://www.ec21.com/trade/{urllib.parse.quote_plus(query)}/",
                raw_name=name,
                raw_country=country,
                raw_description=description,
                supplier_type="trader",
            ))

        logger.info("EC21 results", count=len(results), query=query)
        return results

    def _text(self, node, selectors):
        for sel in selectors:
            els = node.css(sel)
            if els:
                t = els[0].text(strip=True)
                if t:
                    return t
        return ""

    def _attr(self, node, selectors, attr):
        for sel in selectors:
            els = node.css(sel)
            if els:
                v = els[0].attributes.get(attr, "")
                if v:
                    return v
        return ""

    def _browser_headers(self):
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
