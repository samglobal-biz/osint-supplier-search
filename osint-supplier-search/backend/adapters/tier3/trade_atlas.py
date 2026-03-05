from __future__ import annotations
import urllib.parse, structlog
from selectolax.parser import HTMLParser
from adapters.base import BaseAdapter

logger = structlog.get_logger()


class TradeAtlasAdapter(BaseAdapter):
    """TradeAtlas — multi-country customs data (Turkey, Russia, Ukraine, CIS, Latin America)."""
    name = "trade_atlas"
    rate_limit_rpm = 5
    cache_ttl_hours = 48

    async def search(self, job_id, query, filters):
        cached = await self._get_cached(query)
        if cached is not None:
            return cached
        results = []
        try:
            data = await self._get_json(
                "https://app.tradeatlas.com/api/v1/company/search",
                params={"q": query, "limit": 20},
                headers=self._bh(),
            )
            results = self._parse_json(data, query)
        except Exception:
            try:
                encoded = urllib.parse.quote_plus(query)
                html = await self._get(
                    f"https://tradeatlas.com/company/search?q={encoded}",
                    headers=self._bh(),
                )
                results = self._parse_html(html, query)
            except Exception as e:
                logger.warning("TradeAtlas failed", error=str(e))
        await self._set_cached(query, results)
        return results

    def _parse_json(self, data, query):
        results = []
        items = data.get("data") or data.get("companies") or data.get("results") or [] if isinstance(data, dict) else []
        for item in items[:20]:
            name = item.get("name") or item.get("company_name") or ""
            if not name:
                continue
            country = item.get("country") or item.get("country_code") or ""
            address = item.get("address") or item.get("city") or ""
            results.append(self._make_candidate(
                source_url=f"https://tradeatlas.com/company/{item.get('id', '')}",
                raw_name=name, raw_country=country, raw_address=address,
                supplier_type=item.get("type") or "trader",
                extra_fields={"data_source": "Customs declarations / Bill of Lading"},
            ))
        return results

    def _parse_html(self, html, query):
        tree = HTMLParser(html)
        results = []
        cards = tree.css("div.company-card") or tree.css("li.company-item") or tree.css("tr.result-row")
        for card in cards[:20]:
            name = self._t(card, ["h2 a", "h3 a", ".company-name a", "td.name a"])
            if not name:
                continue
            country = self._t(card, [".country", "td.country"])
            link = self._a(card, ["h2 a", "h3 a", "td.name a"], "href")
            if link and not link.startswith("http"):
                link = "https://tradeatlas.com" + link
            results.append(self._make_candidate(
                source_url=link or "https://tradeatlas.com",
                raw_name=name, raw_country=country, supplier_type="trader",
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
        return {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36", "Accept": "application/json, text/html"}
