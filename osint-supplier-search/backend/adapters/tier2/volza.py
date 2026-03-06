from __future__ import annotations
import urllib.parse
import json
import structlog
import httpx
from adapters.base import BaseAdapter

logger = structlog.get_logger()

# Shared session cache (per worker process)
_session_cookies: dict | None = None


async def _get_volza_session() -> dict | None:
    """Login to Volza SSO and return session cookies."""
    global _session_cookies
    if _session_cookies:
        return _session_cookies

    from app.config import settings
    if not settings.volza_email or not settings.volza_password:
        return None

    try:
        async with httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36"},
        ) as client:
            # Step 1: GET login page
            r = await client.get("https://volza.ssoone.com/")
            cookies = dict(r.cookies)

            # Step 2: POST credentials
            r2 = await client.post(
                "https://volza.ssoone.com/",
                data={
                    "name": settings.volza_email,
                    "password": settings.volza_password,
                },
                cookies=cookies,
            )

            # Step 3: Capture session cookies after redirect
            all_cookies = {}
            for resp in [r, r2]:
                all_cookies.update(dict(resp.cookies))

            r3 = await client.get("https://app.volza.com/", cookies=all_cookies)
            all_cookies.update(dict(r3.cookies))

            if all_cookies:
                _session_cookies = all_cookies
                logger.info("Volza login successful", url=str(r3.url))
                return _session_cookies

    except Exception as e:
        logger.warning("Volza login failed", error=str(e))
    return None


class VolzaAdapter(BaseAdapter):
    """Volza — global trade data (exporters/importers from customs records)."""
    name = "volza"
    rate_limit_rpm = 5
    cache_ttl_hours = 48

    async def search(self, job_id, query, filters):
        cached = await self._get_cached(query)
        if cached is not None:
            return cached

        results = []
        try:
            cookies = await _get_volza_session()
            if cookies:
                results = await self._search_authenticated(query, cookies)
            else:
                results = await self._search_public(query)
        except Exception as e:
            logger.warning("Volza failed", error=str(e))

        await self._set_cached(query, results)
        return results

    async def _search_authenticated(self, query: str, cookies: dict) -> list[dict]:
        """Search via app.volza.com (authenticated)."""
        encoded = urllib.parse.quote_plus(query)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://app.volza.com/",
        }

        async with httpx.AsyncClient(timeout=30, follow_redirects=True,
                                      headers=headers, cookies=cookies) as client:
            # Try known API endpoint patterns
            for endpoint in [
                f"https://app.volza.com/api/v1/exporters?product={encoded}&limit=30",
                f"https://app.volza.com/api/search?query={encoded}&type=exporter&limit=30",
                f"https://app.volza.com/search/exporters?q={encoded}&limit=30",
            ]:
                try:
                    r = await client.get(endpoint)
                    if r.status_code == 200:
                        try:
                            data = r.json()
                            parsed = self._parse_json(data, query)
                            if parsed:
                                logger.info("Volza API results", count=len(parsed), endpoint=endpoint)
                                return parsed
                        except Exception:
                            pass
                except Exception:
                    continue

            # Fallback: HTML page (authenticated, bypasses Cloudflare via session)
            try:
                r = await client.get(f"https://app.volza.com/p/{encoded}/export/")
                if r.status_code == 200 and "Just a moment" not in r.text:
                    results = self._parse_html(r.text, query)
                    logger.info("Volza HTML results (auth)", count=len(results))
                    return results
            except Exception:
                pass

        return []

    async def _search_public(self, query: str) -> list[dict]:
        """Fallback public search (usually blocked by Cloudflare)."""
        encoded = urllib.parse.quote_plus(query)
        try:
            html = await self._get(f"https://www.volza.com/p/{encoded}/export/", headers=self._bh())
            if "Just a moment" in html or "Enable JavaScript" in html:
                return []
            return self._parse_html(html, query)
        except Exception:
            return []

    def _parse_json(self, data, query: str) -> list[dict]:
        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            for key in ("data", "exporters", "importers", "results", "companies", "list"):
                if key in data and isinstance(data[key], list):
                    items = data[key]
                    break

        results = []
        for item in items[:30]:
            if not isinstance(item, dict):
                continue
            name = (
                item.get("company_name") or item.get("name") or
                item.get("exporter_name") or item.get("companyName") or ""
            ).strip()
            if not name:
                continue
            href = item.get("url") or item.get("profile_url") or item.get("link") or ""
            if href and not href.startswith("http"):
                href = "https://app.volza.com" + href
            results.append(self._make_candidate(
                source_url=href or f"https://app.volza.com/p/{urllib.parse.quote_plus(query)}/export/",
                raw_name=name,
                raw_country=item.get("country") or item.get("country_name") or None,
                raw_address=item.get("address") or item.get("city") or None,
                raw_phone=item.get("phone") or item.get("contact_number") or None,
                raw_email=item.get("email") or None,
                raw_website=item.get("website") or item.get("website_url") or None,
                supplier_type="exporter",
            ))
        return results

    def _parse_html(self, html: str, query: str) -> list[dict]:
        from selectolax.parser import HTMLParser
        tree = HTMLParser(html)
        results = []
        seen: set[str] = set()

        # Try JSON-LD first
        for script in tree.css('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.text())
                if isinstance(data, dict) and data.get("@type") == "ItemList":
                    for li in data.get("itemListElement", []):
                        org = li.get("item", {}) if isinstance(li, dict) else {}
                        name = org.get("name", "").strip()
                        if name and name not in seen:
                            seen.add(name)
                            addr = org.get("address", {})
                            results.append(self._make_candidate(
                                source_url=org.get("url") or f"https://app.volza.com/p/{urllib.parse.quote_plus(query)}/export/",
                                raw_name=name,
                                raw_country=addr.get("addressCountry") if isinstance(addr, dict) else None,
                                supplier_type="exporter",
                            ))
            except Exception:
                continue

        if results:
            return results[:30]

        # CSS fallback
        for sel in ["div.company-card", "tr.company-row", "div.exporter-item", "li.company-item"]:
            for card in tree.css(sel)[:30]:
                for name_sel in ["a.company-name", "h3 a", "h4 a", ".name a"]:
                    els = card.css(name_sel)
                    if els:
                        name = els[0].text(strip=True)
                        if name and name not in seen:
                            seen.add(name)
                            href = els[0].attributes.get("href", "")
                            if href and not href.startswith("http"):
                                href = "https://app.volza.com" + href
                            results.append(self._make_candidate(
                                source_url=href or f"https://app.volza.com/p/{urllib.parse.quote_plus(query)}/export/",
                                raw_name=name,
                                supplier_type="exporter",
                            ))
                        break

        logger.info("Volza HTML parsed", count=len(results))
        return results[:30]

    def _bh(self):
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html",
        }
