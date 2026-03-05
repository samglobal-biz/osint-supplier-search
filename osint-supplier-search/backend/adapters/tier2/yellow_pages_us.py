from __future__ import annotations
import urllib.parse, structlog
from selectolax.parser import HTMLParser
from adapters.base import BaseAdapter

logger = structlog.get_logger()


class YellowPagesUSAdapter(BaseAdapter):
    """Yellow Pages USA — large US business directory."""
    name = "yellow_pages_us"
    rate_limit_rpm = 8
    cache_ttl_hours = 48

    async def search(self, job_id, query, filters):
        cached = await self._get_cached(query)
        if cached is not None:
            return cached
        results = []
        try:
            encoded = urllib.parse.quote_plus(query)
            html = await self._get(
                f"https://www.yellowpages.com/search?search_terms={encoded}",
                headers=self._bh(),
            )
            results = self._parse(html, query)
        except Exception as e:
            logger.warning("YellowPagesUS failed", error=str(e))
        await self._set_cached(query, results)
        return results

    def _parse(self, html, query):
        tree = HTMLParser(html)
        results = []
        cards = tree.css("div.result") or tree.css("div[class*='organic']") or tree.css("article.result")
        for card in cards[:20]:
            name = self._t(card, ["a.business-name", "h2 a", "h3.n a", ".business-name span"])
            if not name:
                continue
            address = self._t(card, [".adr", "p.adr", ".street-address"])
            phone = self._t(card, [".phones.phone", "a[href^='tel:']", ".phone"])
            city = self._t(card, [".locality", ".city"])
            full_addr = ", ".join(filter(None, [address, city]))
            link = self._a(card, ["a.business-name", "h2 a"], "href")
            if link and not link.startswith("http"):
                link = "https://www.yellowpages.com" + link
            results.append(self._make_candidate(
                source_url=link or f"https://www.yellowpages.com/search?search_terms={urllib.parse.quote_plus(query)}",
                raw_name=name, raw_country="US", raw_address=full_addr, raw_phone=phone,
            ))
        logger.info("YellowPagesUS results", count=len(results))
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
        return {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36", "Accept": "text/html", "Accept-Language": "en-US,en;q=0.9"}
