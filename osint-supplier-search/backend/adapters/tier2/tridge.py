from __future__ import annotations
import urllib.parse, structlog
from selectolax.parser import HTMLParser
from adapters.base import BaseAdapter

logger = structlog.get_logger()


class TridgeAdapter(BaseAdapter):
    """Tridge — global food & agri-commodity trade platform."""
    name = "tridge"
    rate_limit_rpm = 5
    cache_ttl_hours = 48
    cloudflare_protected = True

    async def search(self, job_id, query, filters):
        cached = await self._get_cached(query)
        if cached is not None:
            return cached
        results = []
        try:
            encoded = urllib.parse.quote_plus(query)
            html = await self._get(
                f"https://www.tridge.com/intelligences/search?query={encoded}&tab=supplier",
                headers=self._bh(),
            )
            results = self._parse(html, query)
        except Exception as e:
            logger.warning("Tridge failed", error=str(e))
        await self._set_cached(query, results)
        return results

    def _parse(self, html, query):
        tree = HTMLParser(html)
        results = []
        cards = tree.css("div.supplier-card") or tree.css("li[class*='supplier']") or tree.css("div[class*='SupplierCard']")
        for card in cards[:20]:
            name = self._t(card, ["h3 a", "h2 a", ".supplier-name", "a[class*='name']"])
            if not name:
                continue
            country = self._t(card, [".country", "span[class*='country']", ".origin"])
            link = self._a(card, ["h3 a", "h2 a", "a[class*='name']"], "href")
            if link and not link.startswith("http"):
                link = "https://www.tridge.com" + link
            results.append(self._make_candidate(
                source_url=link or f"https://www.tridge.com/intelligences/search?query={urllib.parse.quote_plus(query)}",
                raw_name=name, raw_country=country, supplier_type="exporter",
            ))
        logger.info("Tridge results", count=len(results))
        return results

    def _t(self, n, ss):
        for s in ss:
            els = n.css(s)
            if els:
                t = els[0].text(strip=True)
                if t: return t
        return ""

    def _a(self, n, ss, attr):
        for s in ss:
            els = n.css(s)
            if els:
                v = els[0].attributes.get(attr, "")
                if v: return v
        return ""

    def _bh(self):
        return {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36", "Accept": "text/html"}
