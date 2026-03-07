from __future__ import annotations
import urllib.parse
import json
import structlog
from selectolax.parser import HTMLParser
from adapters.base import BaseAdapter

logger = structlog.get_logger()


class ExportPagesAdapter(BaseAdapter):
    """ExportPages — European/global B2B exporters directory (Germany-based)."""
    name = "exportpages"
    rate_limit_rpm = 8
    cache_ttl_hours = 24

    async def search(self, job_id: str, query: str, filters) -> list[dict]:
        cached = await self._get_cached(query)
        if cached is not None:
            return cached

        results = []
        try:
            encoded = urllib.parse.quote_plus(query)
            url = f"https://www.exportpages.com/en/search.htm?query={encoded}"
            html = await self._get(url, headers=self._bh())
            results = self._parse(html, query)
        except Exception as e:
            logger.warning("ExportPages failed", error=str(e), query=query)

        await self._set_cached(query, results)
        return results

    def _parse(self, html: str, query: str) -> list[dict]:
        tree = HTMLParser(html)
        results = []
        seen: set[str] = set()
        base_url = f"https://www.exportpages.com/en/search.htm?query={urllib.parse.quote_plus(query)}"

        # JSON-LD
        for script in tree.css('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.text())
                if not isinstance(data, (list, dict)):
                    continue
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if item.get("@type") not in ("ItemList", "Organization"):
                        for sub in item.get("itemListElement", []):
                            org = sub.get("item", sub) if isinstance(sub, dict) else {}
                            name = (org.get("name") or "").strip()
                            if name and name not in seen:
                                seen.add(name)
                                addr = org.get("address", {})
                                results.append(self._make_candidate(
                                    source_url=org.get("url") or base_url,
                                    raw_name=name,
                                    raw_country=addr.get("addressCountry") if isinstance(addr, dict) else None,
                                    raw_address=addr.get("streetAddress") if isinstance(addr, dict) else None,
                                    supplier_type="exporter",
                                ))
            except Exception:
                continue

        if results:
            return results[:25]

        # CSS fallback — exportpages uses provider/supplier cards
        for sel in [
            "div.provider-item", "div.search-result-item", "div[class*='provider']",
            "article.company", "div.company-card", "li.search-item",
        ]:
            for card in tree.css(sel)[:25]:
                name = ""
                for n_sel in ["h2 a", "h3 a", ".provider-name", ".company-name", "a[class*='name']"]:
                    els = card.css(n_sel)
                    if els:
                        name = els[0].text(strip=True)
                        if name:
                            break
                if not name or name in seen:
                    continue
                seen.add(name)
                href = ""
                for l_sel in ["h2 a", "h3 a", "a[class*='name']", "a.provider-link"]:
                    els = card.css(l_sel)
                    if els:
                        href = els[0].attributes.get("href", "")
                        if href:
                            break
                if href and not href.startswith("http"):
                    href = "https://www.exportpages.com" + href
                country = ""
                for c_sel in [".country", ".location", "span[class*='country']", ".address"]:
                    els = card.css(c_sel)
                    if els:
                        country = els[0].text(strip=True)
                        break
                results.append(self._make_candidate(
                    source_url=href or base_url,
                    raw_name=name,
                    raw_country=country or None,
                    supplier_type="exporter",
                ))
            if results:
                break

        logger.info("ExportPages results", count=len(results), query=query)
        return results

    def _bh(self):
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
