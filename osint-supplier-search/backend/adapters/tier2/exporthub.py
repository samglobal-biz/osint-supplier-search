from __future__ import annotations
import urllib.parse
import structlog
from selectolax.parser import HTMLParser
from adapters.base import BaseAdapter

logger = structlog.get_logger()


class ExportHubAdapter(BaseAdapter):
    """ExportHub — global trading platform for exporters/importers."""
    name = "exporthub"
    rate_limit_rpm = 10
    cache_ttl_hours = 24

    async def search(self, job_id: str, query: str, filters) -> list[dict]:
        cached = await self._get_cached(query)
        if cached is not None:
            return cached

        results = []
        try:
            encoded = urllib.parse.quote_plus(query)
            url = f"https://www.exporthub.com/suppliers/{encoded}"
            html = await self._get(url, headers=self._browser_headers())
            results = self._parse(html, query)
        except Exception as e:
            logger.warning("ExportHub search failed", error=str(e), query=query)

        await self._set_cached(query, results)
        return results

    def _parse(self, html: str, query: str) -> list[dict]:
        tree = HTMLParser(html)
        results = []

        cards = (
            tree.css("div.supplier-item") or
            tree.css("li.supplier-list-item") or
            tree.css("div[class*='supplier-card']") or
            tree.css("div.company-item") or
            tree.css("article.supplier")
        )

        for card in cards[:20]:
            name = self._text(card, [
                "h2 a", "h3 a", ".company-name", ".supplier-name a",
                "a[class*='name']",
            ])
            if not name:
                continue

            country = self._text(card, [".country", ".location", "span[class*='country']"])
            address = self._text(card, [".address", ".location"])
            description = self._text(card, [".description", "p.desc", ".profile"])
            link = self._attr(card, ["h2 a", "h3 a", "a[class*='name']"], "href")
            if link and not link.startswith("http"):
                link = "https://www.exporthub.com" + link

            results.append(self._make_candidate(
                source_url=link or f"https://www.exporthub.com/suppliers/{urllib.parse.quote_plus(query)}",
                raw_name=name,
                raw_country=country,
                raw_address=address,
                raw_description=description,
                supplier_type="exporter",
            ))

        logger.info("ExportHub results", count=len(results), query=query)
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
        }
