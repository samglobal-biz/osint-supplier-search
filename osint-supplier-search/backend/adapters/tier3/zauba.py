from __future__ import annotations
import urllib.parse, structlog
from selectolax.parser import HTMLParser
from adapters.base import BaseAdapter

logger = structlog.get_logger()


class ZaubaAdapter(BaseAdapter):
    """Zauba — India import/export customs data (Bill of Lading, shipping records)."""
    name = "zauba"
    rate_limit_rpm = 5
    cache_ttl_hours = 48

    async def search(self, job_id, query, filters):
        cached = await self._get_cached(query)
        if cached is not None:
            return cached
        results = []
        try:
            encoded = urllib.parse.quote_plus(query)
            # Search importers
            html = await self._get(
                f"https://www.zauba.com/import-{encoded}.html",
                headers=self._bh(),
            )
            results += self._parse(html, query, "importer")
            # Search exporters
            html2 = await self._get(
                f"https://www.zauba.com/export-{encoded}.html",
                headers=self._bh(),
            )
            results += self._parse(html2, query, "exporter")
        except Exception as e:
            logger.warning("Zauba failed", error=str(e))
        await self._set_cached(query, results)
        return results

    def _parse(self, html, query, stype):
        tree = HTMLParser(html)
        results = []
        rows = tree.css("table.trade-table tr") or tree.css("tr.data-row") or tree.css("div.shipment-item")
        for row in rows[:20]:
            name = self._t(row, ["td.importer-name a", "td.exporter-name a", "td a", ".company-name"])
            if not name or name.lower() in ("importer", "exporter", "company"):
                continue
            city = self._t(row, ["td.city", "td.port", ".city"])
            link = self._a(row, ["td a", ".company-name a"], "href")
            if link and not link.startswith("http"):
                link = "https://www.zauba.com" + link
            results.append(self._make_candidate(
                source_url=link or f"https://www.zauba.com/import-{urllib.parse.quote_plus(query)}.html",
                raw_name=name, raw_country="IN", raw_address=city,
                supplier_type=stype,
                extra_fields={"data_source": "India Customs Bill of Lading"},
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
        return {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36", "Accept": "text/html", "Accept-Language": "en-US,en;q=0.9"}
