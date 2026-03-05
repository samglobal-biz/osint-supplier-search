from __future__ import annotations
import re
import urllib.parse
import structlog
from selectolax.parser import HTMLParser
from adapters.base import BaseAdapter

logger = structlog.get_logger()

# Regex patterns for contact extraction
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?\d[\d\s\-().]{7,}\d)")


class DirectWebsiteAdapter(BaseAdapter):
    """Scrapes company websites directly for contact info (email, phone, address)."""
    name = "direct_website"
    rate_limit_rpm = 20
    cache_ttl_hours = 72

    async def search(self, job_id: str, query: str, filters) -> list[dict]:
        """This adapter enriches existing clusters rather than discovering new ones.
        When called standalone, it searches Google-like for contact pages."""
        return []

    async def enrich(self, website_url: str) -> dict:
        """Fetch a company website and extract contact info."""
        try:
            html = await self._get(website_url, headers=self._browser_headers())
            return self._extract_contacts(html, website_url)
        except Exception as e:
            logger.warning("Direct website enrich failed", url=website_url, error=str(e))
            return {}

    async def enrich_contact_page(self, base_url: str) -> dict:
        """Try /contact and /about pages for richer contact info."""
        contacts = {}
        domain = urllib.parse.urlparse(base_url).scheme + "://" + urllib.parse.urlparse(base_url).netloc

        for path in ["/contact", "/contact-us", "/about", "/about-us", "/contacts"]:
            try:
                html = await self._get(domain + path, headers=self._browser_headers())
                found = self._extract_contacts(html, domain + path)
                for k, v in found.items():
                    if v and not contacts.get(k):
                        contacts[k] = v
                if contacts.get("email"):
                    break  # Got what we need
            except Exception:
                continue

        return contacts

    def _extract_contacts(self, html: str, url: str) -> dict:
        tree = HTMLParser(html)

        # Remove script/style noise
        for node in tree.css("script, style, noscript"):
            node.decompose()

        text = tree.root.text(separator=" ", strip=True) if tree.root else ""

        emails = list(set(_EMAIL_RE.findall(text)))
        # Filter out common non-contact emails
        emails = [e for e in emails if not any(x in e.lower() for x in [
            "example.com", "sentry", "webpack", "noreply", "no-reply", "@2x", ".png", ".jpg"
        ])]

        phones = list(set(_PHONE_RE.findall(text)))
        phones = [p.strip() for p in phones if len(p.strip()) >= 7]

        # Try structured address fields
        address = self._text(tree, [
            "address", "[itemtype*='PostalAddress']", ".address",
            "[class*='address']", "footer address",
        ])

        return {
            "emails": emails[:5],
            "phones": phones[:5],
            "address": address,
        }

    def _text(self, tree, selectors):
        for sel in selectors:
            els = tree.css(sel)
            if els:
                t = els[0].text(strip=True)
                if t:
                    return t
        return ""

    def _browser_headers(self):
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        }
