from __future__ import annotations
import urllib.parse, structlog
from selectolax.parser import HTMLParser
from adapters.base import BaseAdapter

logger = structlog.get_logger()


class DHgateAdapter(BaseAdapter):
    """DHgate — Chinese wholesale B2B marketplace."""
    name = "dhgate"
    rate_limit_rpm = 5
    cache_ttl_hours = 24

    async def search(self, job_id, query, filters):
        cached = await self._get_cached(query)
        if cached is not None:
            return cached
        results = []
        try:
            encoded = urllib.parse.quote_plus(query)
            html = await self._get(
                f"https://www.dhgate.com/wholesale/search.do?searchkey={encoded}",
                headers=self._bh(),
            )
            results = self._parse(html, query)
        except Exception as e:
            logger.warning("DHgate failed", error=str(e))
        await self._set_cached(query, results)
        return results

    def _parse(self, html, query):
        tree = HTMLParser(html)
        results = []
        seen = set()
        cards = tree.css("div.storeInfo") or tree.css("div[class*='seller']") or tree.css("span.storeName")
        for card in cards[:20]:
            name = self._t(card, ["a.storeName", "span.storeName", ".seller-name a", "h3 a"])
            if not name or name in seen:
                continue
            seen.add(name)
            link = self._a(card, ["a.storeName", "a[href*='/store/']"], "href")
            if link and not link.startswith("http"):
                link = "https://www.dhgate.com" + link
            results.append(self._make_candidate(
                source_url=link or f"https://www.dhgate.com/wholesale/search.do?searchkey={urllib.parse.quote_plus(query)}",
                raw_name=name, raw_country="CN", supplier_type="wholesaler",
            ))
        logger.info("DHgate results", count=len(results))
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
