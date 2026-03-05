from __future__ import annotations
import urllib.parse, structlog
from adapters.base import BaseAdapter

logger = structlog.get_logger()

# UN Comtrade free API — returns country-level trade flows + top trading partners
# Useful for identifying which countries export a given product (HS code context)
COMTRADE_URL = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"


class UNComtradeAdapter(BaseAdapter):
    """UN Comtrade — official UN international trade statistics.
    Returns top exporting countries for a product (not individual companies).
    Used to guide country-level sourcing strategy."""
    name = "un_comtrade"
    rate_limit_rpm = 5
    cache_ttl_hours = 168  # 1 week

    async def search(self, job_id, query, filters):
        cached = await self._get_cached(query)
        if cached is not None:
            return cached
        results = []
        try:
            # Search by description (not HS code) via the public preview endpoint
            data = await self._get_json(
                "https://comtradeapi.un.org/public/v1/preview/C/A/HS",
                params={
                    "cmdDesc": query,
                    "flowCode": "X",  # exports
                    "period": "2023",
                    "limit": 20,
                },
                headers={"Accept": "application/json", "User-Agent": "OSINTSupplierBot/1.0"},
            )
            results = self._parse(data, query)
        except Exception as e:
            logger.warning("UNComtrade failed", error=str(e))
        await self._set_cached(query, results)
        return results

    def _parse(self, data, query):
        results = []
        records = []
        if isinstance(data, dict):
            records = data.get("data") or data.get("results") or []
        for r in records[:20]:
            reporter = r.get("reporterDesc") or r.get("reporter") or ""
            partner = r.get("partnerDesc") or r.get("partner") or ""
            cmd = r.get("cmdDesc") or r.get("commodity") or query
            flow_value = r.get("primaryValue") or r.get("tradeValue") or 0
            if not reporter:
                continue
            # UN Comtrade gives us country-level data; create a "country entry"
            results.append(self._make_candidate(
                source_url="https://comtradeplus.un.org/",
                raw_name=f"{reporter} (exporter of {cmd})",
                raw_country=r.get("reporterISO") or reporter,
                raw_description=f"Top exporter to {partner}. Trade value: ${flow_value:,.0f}",
                supplier_type="exporter",
                extra_fields={
                    "data_source": "UN Comtrade",
                    "hs_code": r.get("cmdCode"),
                    "trade_value_usd": flow_value,
                    "year": r.get("period"),
                },
            ))
        logger.info("UNComtrade results", count=len(results))
        return results
