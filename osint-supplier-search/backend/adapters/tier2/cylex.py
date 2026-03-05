from __future__ import annotations
import urllib.parse, structlog
from selectolax.parser import HTMLParser
from adapters.base import BaseAdapter

logger = structlog.get_logger()


class CylexAdapter(BaseAdapter):
    """Cylex — international business directory with 40M+ listings."""
    name = "cylex"
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
                f"https://www.cylex-uk.co.uk/search/{encoded}.html",
                headers=self._bh(),
            )
            results = self._parse(html, query, "GB")
            # Also check international
            if len(results) < 5:
                html2 = await self._get(
                    f"https://www.cylex.de/search/{encoded}.html",
                    headers=self._bh(),
                )
                results += self._parse(html2, query, "DE")
        except Exception as e:
            logger.warning("Cylex failed", error=str(e))
        await self._set_cached(query, results)
        return results

    def _parse(self, html, query, country):
        tree = HTMLParser(html)
        results = []
        cards = tree.css("div.result-entry") or tree.css("li.business-item") or tree.css("article.company")
        for card in cards[:15]:
            name = self._t(card, ["h2 a", "h3 a", ".company-name a", "span.fn a"])
            if not name:
                continue
            address = self._t(card, [".adr", ".address", "address"])
            phone = self._t(card, [".tel", "a[href^='tel:']"])
            link = self._a(card, ["h2 a", "h3 a"], "href")
            if link and not link.startswith("http"):
                link = "https://www.cylex-uk.co.uk" + link
            results.append(self._make_candidate(
                source_url=link or f"https://www.cylex-uk.co.uk/search/{urllib.parse.quote_plus(query)}.html",
                raw_name=name, raw_country=country, raw_address=address, raw_phone=phone,
            ))
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
