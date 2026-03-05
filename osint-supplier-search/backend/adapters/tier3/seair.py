from __future__ import annotations
import urllib.parse, structlog
from selectolax.parser import HTMLParser
from adapters.base import BaseAdapter

logger = structlog.get_logger()


class SeairAdapter(BaseAdapter):
    """Seair Exim — India and global customs import/export shipment data."""
    name = "seair"
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
                f"https://www.seair.co.in/india-import-data/{encoded}.aspx",
                headers=self._bh(),
            )
            results = self._parse(html, query, "importer")
            html2 = await self._get(
                f"https://www.seair.co.in/india-export-data/{encoded}.aspx",
                headers=self._bh(),
            )
            results += self._parse(html2, query, "exporter")
        except Exception as e:
            logger.warning("Seair failed", error=str(e))
        await self._set_cached(query, results)
        return results

    def _parse(self, html, query, stype):
        tree = HTMLParser(html)
        results = []
        rows = tree.css("table.table tr") or tree.css("div.company-row") or tree.css("li.company-item")
        for row in rows[:20]:
            name = self._t(row, ["td.importer a", "td.exporter a", "td.company a", ".company-name"])
            if not name or len(name) < 3:
                continue
            city = self._t(row, ["td.city", "td.port", ".port"])
            quantity = self._t(row, ["td.quantity", "td.qty", ".quantity"])
            results.append(self._make_candidate(
                source_url=f"https://www.seair.co.in/india-import-data/{urllib.parse.quote_plus(query)}.aspx",
                raw_name=name, raw_country="IN", raw_address=city,
                supplier_type=stype,
                extra_fields={"data_source": "India Customs Shipment Data", "quantity": quantity},
            ))
        return results

    def _t(self, n, ss):
        for s in ss:
            els = n.css(s)
            if els:
                t = els[0].text(strip=True)
                if t: return t
        return ""

    def _bh(self):
        return {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36", "Accept": "text/html"}
