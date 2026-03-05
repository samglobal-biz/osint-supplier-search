from __future__ import annotations
import urllib.parse, structlog
from selectolax.parser import HTMLParser
from adapters.base import BaseAdapter

logger = structlog.get_logger()


class ExportersIndiaAdapter(BaseAdapter):
    name = "exporters_india"
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
                f"https://www.exportersindia.com/search-result/{encoded}-exporters-manufacturers.htm",
                headers=self._bh(),
            )
            results = self._parse(html, query)
        except Exception as e:
            logger.warning("ExportersIndia failed", error=str(e))
        await self._set_cached(query, results)
        return results

    def _parse(self, html, query):
        tree = HTMLParser(html)
        results = []
        cards = tree.css("div.company-details") or tree.css("li.company-listing") or tree.css("div.srchResultBox")
        for card in cards[:20]:
            name = self._t(card, ["h3 a", "h2 a", ".company-name a", "strong a"])
            if not name:
                continue
            city = self._t(card, [".city", ".location", ".address"])
            phone = self._t(card, [".phone", "a[href^='tel:']"])
            link = self._a(card, ["h3 a", "h2 a"], "href")
            if link and not link.startswith("http"):
                link = "https://www.exportersindia.com" + link
            results.append(self._make_candidate(
                source_url=link or f"https://www.exportersindia.com/search-result/{urllib.parse.quote_plus(query)}-exporters-manufacturers.htm",
                raw_name=name,
                raw_country="IN",
                raw_address=city,
                raw_phone=phone,
                supplier_type="exporter",
            ))
        logger.info("ExportersIndia results", count=len(results))
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
