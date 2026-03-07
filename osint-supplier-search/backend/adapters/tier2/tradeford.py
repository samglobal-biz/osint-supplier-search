from __future__ import annotations
import urllib.parse
import json
import structlog
from selectolax.parser import HTMLParser
from adapters.base import BaseAdapter

logger = structlog.get_logger()


class TradefordAdapter(BaseAdapter):
    """Tradeford — global B2B marketplace for suppliers and exporters."""
    name = "tradeford"
    rate_limit_rpm = 8
    cache_ttl_hours = 24

    async def search(self, job_id: str, query: str, filters) -> list[dict]:
        cached = await self._get_cached(query)
        if cached is not None:
            return cached

        results = []
        try:
            encoded = urllib.parse.quote_plus(query)
            url = f"https://supplier.tradeford.com/?search={encoded}"
            html = await self._get(url, headers=self._bh())
            results = self._parse(html, query)
        except Exception as e:
            logger.warning("Tradeford failed", error=str(e), query=query)

        await self._set_cached(query, results)
        return results

    def _parse(self, html: str, query: str) -> list[dict]:
        tree = HTMLParser(html)
        results = []
        seen: set[str] = set()
        base_url = f"https://supplier.tradeford.com/?search={urllib.parse.quote_plus(query)}"

        # JSON-LD
        for script in tree.css('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.text())
                items = data if isinstance(data, list) else [data]
                for item in items:
                    for sub in (item.get("itemListElement") or []):
                        org = sub.get("item", sub) if isinstance(sub, dict) else {}
                        name = (org.get("name") or "").strip()
                        if name and name not in seen:
                            seen.add(name)
                            addr = org.get("address", {})
                            results.append(self._make_candidate(
                                source_url=org.get("url") or base_url,
                                raw_name=name,
                                raw_country=addr.get("addressCountry") if isinstance(addr, dict) else None,
                                supplier_type="exporter",
                            ))
            except Exception:
                continue

        if results:
            return results[:25]

        # CSS fallback
        for sel in [
            "div.supplier-item", "div.member-item", "div[class*='supplier']",
            "li.supplier", "div.company", "article",
        ]:
            for card in tree.css(sel)[:25]:
                name = ""
                for n_sel in ["h2 a", "h3 a", ".company-name", ".supplier-name", "a.name"]:
                    els = card.css(n_sel)
                    if els:
                        name = els[0].text(strip=True)
                        if name:
                            break
                if not name or name in seen:
                    continue
                seen.add(name)
                href = ""
                for l_sel in ["h2 a", "h3 a", "a.name", "a[class*='title']"]:
                    els = card.css(l_sel)
                    if els:
                        href = els[0].attributes.get("href", "")
                        if href:
                            break
                if href and not href.startswith("http"):
                    href = "https://supplier.tradeford.com" + href
                country = ""
                for c_sel in [".country", ".location", "span[class*='flag']"]:
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

        logger.info("Tradeford results", count=len(results), query=query)
        return results

    def _bh(self):
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
