from __future__ import annotations
import urllib.parse, structlog
from adapters.base import BaseAdapter

logger = structlog.get_logger()


class AlibabaAdapter(BaseAdapter):
    """Alibaba.com — world's largest B2B marketplace. Uses public search API."""
    name = "alibaba"
    rate_limit_rpm = 3
    cache_ttl_hours = 24

    async def search(self, job_id, query, filters):
        cached = await self._get_cached(query)
        if cached is not None:
            return cached
        results = []
        try:
            # Alibaba has a product search API endpoint
            data = await self._get_json(
                "https://www.alibaba.com/trade/search/global-product/search.html",
                params={"SearchText": query, "page": 1, "pageSize": 20},
                headers=self._bh(),
            )
            results = self._parse_json(data, query)
        except Exception:
            # Fallback: try HTML search page
            try:
                encoded = urllib.parse.quote_plus(query)
                import httpx
                async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
                    resp = await c.get(
                        f"https://www.alibaba.com/trade/search?SearchText={encoded}",
                        headers=self._bh(),
                    )
                    from selectolax.parser import HTMLParser
                    results = self._parse_html(resp.text, query)
            except Exception as e:
                logger.warning("Alibaba failed", error=str(e))
        await self._set_cached(query, results)
        return results

    def _parse_json(self, data, query):
        results = []
        items = []
        if isinstance(data, dict):
            items = data.get("result", {}).get("resultList") or data.get("items") or []
        for item in items[:20]:
            company = item.get("company") or item.get("supplierName") or ""
            if not company:
                continue
            country = item.get("country") or item.get("supplierCountry") or ""
            results.append(self._make_candidate(
                source_url=item.get("url") or f"https://www.alibaba.com/trade/search?SearchText={urllib.parse.quote_plus(query)}",
                raw_name=company, raw_country=country, supplier_type="manufacturer",
            ))
        return results

    def _parse_html(self, html, query):
        from selectolax.parser import HTMLParser
        tree = HTMLParser(html)
        results = []
        cards = tree.css("div.organic-list-offer") or tree.css("div[class*='J-offer-wrapper']") or tree.css("div.offer-item")
        for card in cards[:20]:
            company = ""
            for sel in ["a.company-name", ".supplier-name a", ".company-name-section a"]:
                els = card.css(sel)
                if els:
                    company = els[0].text(strip=True)
                    break
            if not company:
                continue
            country = ""
            for sel in [".supplier-region", ".location"]:
                els = card.css(sel)
                if els:
                    country = els[0].text(strip=True)
                    break
            results.append(self._make_candidate(
                source_url=f"https://www.alibaba.com/trade/search?SearchText={urllib.parse.quote_plus(query)}",
                raw_name=company, raw_country=country, supplier_type="manufacturer",
            ))
        logger.info("Alibaba results", count=len(results))
        return results

    def _bh(self):
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json, text/html",
            "Referer": "https://www.alibaba.com/",
        }
