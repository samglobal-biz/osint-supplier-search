from __future__ import annotations
import urllib.parse, structlog
from selectolax.parser import HTMLParser
from adapters.base import BaseAdapter

logger = structlog.get_logger()


class WLWAdapter(BaseAdapter):
    """Wer liefert was (WLW) — leading B2B supplier directory in DE/AT/CH."""
    name = "wlw"
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
                f"https://www.wlw.de/de/suche?keywords={encoded}",
                headers=self._bh(),
            )
            results = self._parse(html, query)
        except Exception as e:
            logger.warning("WLW failed", error=str(e))
        await self._set_cached(query, results)
        return results

    def _parse(self, html, query):
        tree = HTMLParser(html)
        results = []
        cards = tree.css("article.company-card") or tree.css("div[class*='CompanyCard']") or tree.css("li.result-item")
        for card in cards[:20]:
            name = self._t(card, ["h2 a", "h3 a", ".company-name", "a[class*='name']"])
            if not name:
                continue
            city = self._t(card, [".city", ".location", "span[class*='city']"])
            country = "DE"
            link = self._a(card, ["h2 a", "h3 a", "a[class*='company']"], "href")
            if link and not link.startswith("http"):
                link = "https://www.wlw.de" + link
            results.append(self._make_candidate(
                source_url=link or f"https://www.wlw.de/de/suche?keywords={urllib.parse.quote_plus(query)}",
                raw_name=name, raw_country=country, raw_address=city, supplier_type="manufacturer",
            ))
        logger.info("WLW results", count=len(results))
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
        return {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36", "Accept": "text/html", "Accept-Language": "de-DE,de;q=0.9"}
