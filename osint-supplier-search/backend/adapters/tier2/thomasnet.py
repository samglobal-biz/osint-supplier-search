from __future__ import annotations
import urllib.parse
import structlog
from selectolax.parser import HTMLParser
from adapters.base import BaseAdapter

logger = structlog.get_logger()


class ThomasNetAdapter(BaseAdapter):
    """ThomasNet — industrial supplier directory (USA focus)."""
    name = "thomasnet"
    rate_limit_rpm = 8
    cache_ttl_hours = 48
    cloudflare_protected = True

    async def search(self, job_id: str, query: str, filters) -> list[dict]:
        cached = await self._get_cached(query)
        if cached is not None:
            return cached

        results = []
        try:
            encoded = urllib.parse.quote_plus(query)
            url = f"https://www.thomasnet.com/search/?what={encoded}&heading={encoded}&pg=1"
            html = await self._get(url, headers=self._browser_headers())
            results = self._parse(html, query)
        except Exception as e:
            logger.warning("ThomasNet search failed", error=str(e), query=query)

        await self._set_cached(query, results)
        return results

    def _parse(self, html: str, query: str) -> list[dict]:
        tree = HTMLParser(html)
        results = []

        cards = (
            tree.css("div.profile-card") or
            tree.css("article[class*='supplier']") or
            tree.css("div[class*='ProfileCard']") or
            tree.css("li.supplier-result")
        )

        for card in cards[:20]:
            name = self._text(card, [
                "h2[class*='name']", "h2 a", ".company-name",
                "a[class*='company']", "h3 a",
            ])
            if not name:
                continue

            country = "US"  # ThomasNet is primarily USA
            address = self._text(card, [
                ".address", ".location", "address", "span[class*='location']",
            ])
            description = self._text(card, [
                ".description", "p[class*='desc']", ".profile-description",
            ])
            phone = self._text(card, [".phone", "a[href^='tel:']", "span[class*='phone']"])
            website = self._attr(card, ["a[class*='website']", "a[href*='http']"], "href")
            link = self._attr(card, ["h2 a", "h3 a", "a[class*='profile']"], "href")
            if link and not link.startswith("http"):
                link = "https://www.thomasnet.com" + link

            results.append(self._make_candidate(
                source_url=link or f"https://www.thomasnet.com/search/?what={urllib.parse.quote_plus(query)}",
                raw_name=name,
                raw_country=country,
                raw_address=address,
                raw_phone=phone,
                raw_website=website,
                raw_description=description,
                supplier_type="manufacturer",
            ))

        logger.info("ThomasNet results", count=len(results), query=query)
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
