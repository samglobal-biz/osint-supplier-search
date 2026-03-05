from __future__ import annotations
import urllib.parse, structlog
from adapters.base import BaseAdapter

logger = structlog.get_logger()

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"


class WikidataAdapter(BaseAdapter):
    """Wikidata — open knowledge base with company/org structured data."""
    name = "wikidata"
    rate_limit_rpm = 5
    cache_ttl_hours = 72

    async def search(self, job_id, query, filters):
        cached = await self._get_cached(query)
        if cached is not None:
            return cached
        results = []
        try:
            # Search Wikidata for organizations matching query
            sparql = f"""
SELECT DISTINCT ?item ?itemLabel ?countryLabel ?websiteLabel ?inceptionLabel WHERE {{
  ?item wdt:P31/wdt:P279* wd:Q4830453 .
  ?item rdfs:label ?itemLabel .
  FILTER(CONTAINS(LCASE(?itemLabel), "{query.lower()}"))
  OPTIONAL {{ ?item wdt:P17 ?country }}
  OPTIONAL {{ ?item wdt:P856 ?website }}
  OPTIONAL {{ ?item wdt:P571 ?inception }}
  FILTER(LANG(?itemLabel) = "en")
}} LIMIT 15"""
            data = await self._get_json(
                SPARQL_ENDPOINT,
                params={"query": sparql, "format": "json"},
                headers={"Accept": "application/sparql-results+json", "User-Agent": "OSINTSupplierBot/1.0"},
            )
            results = self._parse(data, query)
        except Exception as e:
            logger.warning("Wikidata failed", error=str(e))
        await self._set_cached(query, results)
        return results

    def _parse(self, data, query):
        results = []
        bindings = data.get("results", {}).get("bindings", []) if isinstance(data, dict) else []
        for b in bindings:
            name = b.get("itemLabel", {}).get("value", "")
            if not name or name.startswith("Q"):
                continue
            item_url = b.get("item", {}).get("value", "")
            country = b.get("countryLabel", {}).get("value", "")
            website = b.get("websiteLabel", {}).get("value", "")
            results.append(self._make_candidate(
                source_url=item_url,
                raw_name=name,
                raw_country=country,
                raw_website=website,
            ))
        logger.info("Wikidata results", count=len(results))
        return results
