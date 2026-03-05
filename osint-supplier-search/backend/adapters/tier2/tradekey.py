from __future__ import annotations
import urllib.parse
import structlog
from selectolax.parser import HTMLParser
from adapters.base import BaseAdapter

logger = structlog.get_logger()


class TradekeyAdapter(BaseAdapter):
    """Tradekey — global B2B marketplace."""
    name = "tradekey"
    rate_limit_rpm = 10
    cache_ttl_hours = 24

    async def search(self, job_id: str, query: str, filters) -> list[dict]:
        cached = await self._get_cached(query)
        if cached is not None:
            return cached

        results = []
        try:
            encoded = urllib.parse.quote_plus(query)
            url = f"https://www.tradekey.com/products/{encoded}.html"
            html = await self._get(url, headers=self._browser_headers())
            results = self._parse(html, query)
        except Exception as e:
            logger.warning("Tradekey search failed", error=str(e), query=query)

        await self._set_cached(query, results)
        return results

    def _parse(self, html: str, query: str) -> list[dict]:
        tree = HTMLParser(html)
        results = []
        seen_names: set[str] = set()

        cards = (
            tree.css("div.product-listing") or
            tree.css("li.product-item") or
            tree.css("div[class*='product-card']") or
            tree.css("div.listing-item")
        )

        for card in cards[:20]:
            # Company name is typically separate from product name
            company = self._text(card, [
                ".company-name a", ".seller-name", ".supplier-name",
                "span[class*='company']", "a[class*='company']",
            ])
            product = self._text(card, [
                "h2 a", "h3 a", ".product-title a", ".product-name",
            ])
            name = company or product
            if not name or name in seen_names:
                continue
            seen_names.add(name)

            country = self._text(card, [".country", ".location", "span[class*='country']"])
            link = self._attr(card, [
                "a[class*='company']", ".company-name a", "h2 a", "h3 a",
            ], "href")
            if link and not link.startswith("http"):
                link = "https://www.tradekey.com" + link

            results.append(self._make_candidate(
                source_url=link or f"https://www.tradekey.com/products/{urllib.parse.quote_plus(query)}.html",
                raw_name=name,
                raw_country=country,
                raw_description=product if company else "",
                supplier_type="trader",
            ))

        logger.info("Tradekey results", count=len(results), query=query)
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
