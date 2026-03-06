from __future__ import annotations
import urllib.parse
import structlog
from selectolax.parser import HTMLParser
from adapters.base import BaseAdapter

logger = structlog.get_logger()


class TradekeyAdapter(BaseAdapter):
    """Tradekey — global B2B marketplace."""
    name = "tradekey"
    rate_limit_rpm = 10
    cache_ttl_hours = 24

    async def search(self, job_id: str, query: str, filters) -> list[dict]:
        cached = await self._get_cached(query)
        if cached is not None:
            return cached

        results = []
        try:
            encoded = urllib.parse.quote_plus(query)
            url = f"https://www.tradekey.com/products/{encoded}.html"
            html = await self._get(url, headers=self._browser_headers())
            results = self._parse(html, query)
        except Exception as e:
            logger.warning("Tradekey search failed", error=str(e), query=query)

        await self._set_cached(query, results)
        return results

    def _parse(self, html: str, query: str) -> list[dict]:
        tree = HTMLParser(html)
        results = []
        seen_names: set[str] = set()

        # Company links: <a class="company" title="CompanyName" href="/company/...">
        company_links = tree.css("a.company[title]")

        for a in company_links[:30]:
            name = a.attributes.get("title", "").strip() or a.text(strip=True)
            if not name or name in seen_names:
                continue
            seen_names.add(name)

            href = a.attributes.get("href", "")
            if href and not href.startswith("http"):
                href = "https://www.tradekey.com" + href

            # Country: nearest span.country font
            country = ""
            parent = a.parent
            for _ in range(5):
                if parent is None:
                    break
                font_els = parent.css("span.country font")
                if not font_els:
                    font_els = parent.css("span[class*='country'] font")
                if font_els:
                    country = font_els[0].text(strip=True)
                    break
                parent = parent.parent

            # Supplier type from td text like [Distributors/Wholesalers]
            supplier_type = "trader"
            if parent is not None:
                for td in parent.css("td"):
                    td_text = td.text(strip=True)
                    if td_text.startswith("[") and td_text.endswith("]"):
                        raw_type = td_text[1:-1].lower()
                        if "manufacturer" in raw_type:
                            supplier_type = "manufacturer"
                        elif "distributor" in raw_type or "wholesaler" in raw_type:
                            supplier_type = "distributor"
                        elif "exporter" in raw_type:
                            supplier_type = "exporter"
                        elif "importer" in raw_type:
                            supplier_type = "importer"
                        break

            results.append(self._make_candidate(
                source_url=href or f"https://www.tradekey.com/products/{urllib.parse.quote_plus(query)}.html",
                raw_name=name,
                raw_country=country or None,
                supplier_type=supplier_type,
            ))

        logger.info("Tradekey results", count=len(results), query=query)
        return results

    def _text(self, node, selectors):
        for sel in selectors:
            els = node.css(sel)
            if els:
                t = els[0].text(strip=True)
                if t:
                    return t
        return ""

    def _attr(self, node, selectors, attr):
        for sel in selectors:
            els = node.css(sel)
            if els:
                v = els[0].attributes.get(attr, "")
                if v:
                    return v
        return ""

    def _browser_headers(self):
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        }
