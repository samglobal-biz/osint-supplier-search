from __future__ import annotations
import csv, io, structlog
from adapters.base import BaseAdapter

logger = structlog.get_logger()

OFAC_CSV_URL = "https://www.treasury.gov/ofac/downloads/sdn.csv"


class OFACAdapter(BaseAdapter):
    """OFAC Specially Designated Nationals list — USA sanctions."""
    name = "ofac"
    rate_limit_rpm = 1
    cache_ttl_hours = 168  # 1 week — rarely updated

    async def search(self, job_id, query, filters):
        cached = await self._get_cached(query)
        if cached is not None:
            return cached
        results = []
        try:
            csv_text = await self._get(OFAC_CSV_URL)
            results = self._parse(csv_text, query)
        except Exception as e:
            logger.warning("OFAC failed", error=str(e))
        await self._set_cached(query, results)
        return results

    def _parse(self, csv_text, query):
        results = []
        q_lower = query.lower()
        try:
            reader = csv.reader(io.StringIO(csv_text))
            for row in reader:
                if len(row) < 5:
                    continue
                name = row[1].strip()
                if not name or q_lower not in name.lower():
                    continue
                entity_type = row[2].strip()  # "entity", "individual", "vessel"
                if entity_type.lower() == "individual":
                    continue  # skip persons, we want companies
                program = row[3].strip()
                results.append(self._make_candidate(
                    source_url="https://sanctionssearch.ofac.treas.gov/",
                    raw_name=name,
                    raw_country=row[9].strip() if len(row) > 9 else "",
                    extra_fields={"sanction_flag": True, "program": program, "type": entity_type},
                ))
                if len(results) >= 20:
                    break
        except Exception as e:
            logger.warning("OFAC parse error", error=str(e))
        logger.info("OFAC results", count=len(results))
        return results
