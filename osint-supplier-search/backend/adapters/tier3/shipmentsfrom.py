from __future__ import annotations
import urllib.parse, structlog
from selectolax.parser import HTMLParser
from adapters.base import BaseAdapter

logger = structlog.get_logger()


class ShipmentsFromAdapter(BaseAdapter):
    """ShipmentsFrom.com — aggregated US Bill of Lading / customs shipment data."""
    name = "shipments_from"
    rate_limit_rpm = 5
    cache_ttl_hours = 48

    async def search(self, job_id, query, filters):
        cached = await self._get_cached(query)
        if cached is not None:
            return cached
        results = []
        try:
            encoded = urllib.parse.quote_plus(query)
            html = await self._get(
                f"https://shipmentsfrom.com/search?q={encoded}",
                headers=self._bh(),
            )
            results = self._parse(html, query)
        except Exception as e:
            logger.warning("ShipmentsFrom failed", error=str(e))
        await self._set_cached(query, results)
        return results

    def _parse(self, html, query):
        tree = HTMLParser(html)
        results = []
        cards = (
            tree.css("div.company-result") or
            tree.css("tr.shipper-row") or
            tree.css("div[class*='supplier']") or
            tree.css("li.result")
        )
        for card in cards[:20]:
            name = self._t(card, ["h2 a", "h3 a", ".company-name a", ".shipper-name", "td.shipper a"])
            if not name:
                continue
            country = self._t(card, [".country", "td.origin", "span[class*='country']"])
            shipments = self._t(card, [".shipments", "td.shipments", ".count"])
            link = self._a(card, ["h2 a", "h3 a", "a[class*='company']"], "href")
            if link and not link.startswith("http"):
                link = "https://shipmentsfrom.com" + link
            results.append(self._make_candidate(
                source_url=link or f"https://shipmentsfrom.com/search?q={urllib.parse.quote_plus(query)}",
                raw_name=name, raw_country=country, supplier_type="exporter",
                extra_fields={"data_source": "US Customs Bill of Lading", "shipment_count": shipments},
            ))
        logger.info("ShipmentsFrom results", count=len(results))
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
