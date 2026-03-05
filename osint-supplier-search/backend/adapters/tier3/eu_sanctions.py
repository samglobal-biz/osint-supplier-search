from __future__ import annotations
import json, structlog
from adapters.base import BaseAdapter

logger = structlog.get_logger()

# EU Consolidated Financial Sanctions list (JSON format)
EU_SANCTIONS_URL = "https://webgate.ec.europa.eu/fsd/fsf/public/files/jsonFullSanctionsList_1_1/content"


class EUSanctionsAdapter(BaseAdapter):
    """EU Consolidated Financial Sanctions list."""
    name = "eu_sanctions"
    rate_limit_rpm = 1
    cache_ttl_hours = 168  # 1 week

    async def search(self, job_id, query, filters):
        cached = await self._get_cached(query)
        if cached is not None:
            return cached
        results = []
        try:
            data = await self._get_json(EU_SANCTIONS_URL, headers={"Accept": "application/json"})
            results = self._parse(data, query)
        except Exception as e:
            logger.warning("EUSanctions failed", error=str(e))
        await self._set_cached(query, results)
        return results

    def _parse(self, data, query):
        results = []
        q_lower = query.lower()
        entities = []
        if isinstance(data, dict):
            entities = data.get("sanctionEntity") or data.get("entities") or []
        for entity in entities:
            names = entity.get("nameAlias") or entity.get("names") or []
            matched_name = ""
            for n in names:
                nm = n.get("wholeName") or n.get("firstName", "") + " " + n.get("lastName", "")
                nm = nm.strip()
                if nm and q_lower in nm.lower():
                    matched_name = nm
                    break
            if not matched_name:
                continue
            country = ""
            addresses = entity.get("address") or []
            addr_str = ""
            if addresses:
                a = addresses[0]
                country = a.get("countryIso2Code") or ""
                addr_str = ", ".join(filter(None, [a.get("street"), a.get("city"), a.get("zipCode")]))
            results.append(self._make_candidate(
                source_url="https://data.europa.eu/data/datasets/consolidated-list-of-persons-groups-and-entities-subject-to-eu-financial-sanctions",
                raw_name=matched_name,
                raw_country=country,
                raw_address=addr_str,
                extra_fields={"sanction_flag": True, "regulation": entity.get("regulation", {}).get("regulationSummary")},
            ))
            if len(results) >= 20:
                break
        logger.info("EUSanctions results", count=len(results))
        return results
