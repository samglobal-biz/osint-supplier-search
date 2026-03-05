from __future__ import annotations
import urllib.parse, structlog
from selectolax.parser import HTMLParser
from adapters.base import BaseAdapter

logger = structlog.get_logger()


class MadeInChinaAdapter(BaseAdapter):
    name = "made_in_china"
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
                f"https://www.made-in-china.com/multi-search/{encoded}/F1/",
                headers=self._bh(),
            )
            results = self._parse(html, query)
        except Exception as e:
            logger.warning("MadeInChina failed", error=str(e))
        await self._set_cached(query, results)
        return results

    def _parse(self, html, query):
        tree = HTMLParser(html)
        results = []
        cards = tree.css("div.product-item") or tree.css("li.company-item") or tree.css("div[class*='product-list'] > div")
        for card in cards[:20]:
            name = self._t(card, ["a.company-name", ".comp-name", "strong.comp-name", "h2 a"])
            if not name:
                continue
            results.append(self._make_candidate(
                source_url=self._a(card, ["a.company-name", "h2 a"], "href") or f"https://www.made-in-china.com/multi-search/{urllib.parse.quote_plus(query)}/F1/",
                raw_name=name,
                raw_country="CN",
                raw_description=self._t(card, [".product-name", "h2", ".item-title"]),
                supplier_type="manufacturer",
            ))
        logger.info("MadeInChina results", count=len(results))
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
