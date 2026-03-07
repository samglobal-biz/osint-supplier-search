from __future__ import annotations
import urllib.parse
import structlog
from selectolax.parser import HTMLParser
from adapters.base import BaseAdapter

logger = structlog.get_logger()


class ExportersSGAdapter(BaseAdapter):
    """Exporters.SG — Singapore-based global exporters directory."""
    name = "exporters_sg"
    rate_limit_rpm = 8
    cache_ttl_hours = 24

    async def search(self, job_id: str, query: str, filters) -> list[dict]:
        cached = await self._get_cached(query)
        if cached is not None:
            return cached

        results = []
        try:
            encoded = urllib.parse.quote_plus(query)
            url = f"http://www.exporters.sg/search/search.asp?query={encoded}&catid=0&country=0"
            html = await self._get(url, headers=self._bh())
            if "Verifying you are human" in html or "Just a moment" in html:
                logger.info("ExportersSG blocked by bot check", query=query)
            else:
                results = self._parse(html, query)
        except Exception as e:
            logger.warning("ExportersSG failed", error=str(e), query=query)

        await self._set_cached(query, results)
        return results

    def _parse(self, html: str, query: str) -> list[dict]:
        tree = HTMLParser(html)
        results = []
        seen: set[str] = set()

        # JSON-LD first
        import json
        for script in tree.css('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.text())
                items = []
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict):
                    items = data.get("itemListElement", []) or (
                        [data] if data.get("@type") == "Organization" else []
                    )
                for item in items:
                    org = item.get("item", item) if isinstance(item, dict) else {}
                    name = (org.get("name") or "").strip()
                    if not name or name in seen:
                        continue
                    seen.add(name)
                    addr = org.get("address", {})
                    results.append(self._make_candidate(
                        source_url=org.get("url") or f"http://www.exporters.sg/search/search.asp?query={urllib.parse.quote_plus(query)}",
                        raw_name=name,
                        raw_country=addr.get("addressCountry") if isinstance(addr, dict) else None,
                        raw_address=addr.get("streetAddress") if isinstance(addr, dict) else None,
                        supplier_type="exporter",
                    ))
            except Exception:
                continue

        if results:
            return results[:25]

        # CSS fallback
        for card in tree.css("div.MONOC_PITEM_DIV, div.company_item, div[class*='exporter'], li.result-item")[:25]:
            for sel in ["h2 a", "h3 a", ".company_name a", "a.name", ".COMPANY_NAME"]:
                els = card.css(sel)
                if els:
                    name = els[0].text(strip=True)
                    if not name or name in seen:
                        break
                    seen.add(name)
                    href = els[0].attributes.get("href", "")
                    if href and not href.startswith("http"):
                        href = "http://www.exporters.sg" + href
                    country = ""
                    for c_sel in [".country", "span[class*='country']", ".location"]:
                        c_els = card.css(c_sel)
                        if c_els:
                            country = c_els[0].text(strip=True)
                            break
                    results.append(self._make_candidate(
                        source_url=href or f"http://www.exporters.sg/search/search.asp?query={urllib.parse.quote_plus(query)}",
                        raw_name=name,
                        raw_country=country or None,
                        supplier_type="exporter",
                    ))
                    break

        logger.info("ExportersSG results", count=len(results), query=query)
        return results

    def _bh(self):
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
