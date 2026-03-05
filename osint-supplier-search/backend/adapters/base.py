from __future__ import annotations
import hashlib
import json
import time
from abc import ABC, abstractmethod
from typing import Any
import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = structlog.get_logger()

# Robots.txt cache: {domain: {allowed: bool, crawl_delay: float}}
_robots_cache: dict[str, dict] = {}
# Rate limit counters: {adapter_name: [timestamp, ...]}
_rate_counters: dict[str, list[float]] = {}


class RawCandidate(dict):
    """Typed dict-like for raw candidate data."""
    pass


class BaseAdapter(ABC):
    name: str = "base"
    rate_limit_rpm: int = 10
    cache_ttl_hours: int = 24
    requires_js: bool = False
    enabled: bool = True

    # ── Public entry point ─────────────────────────────────────────────────────

    async def search_sync(self, job_id: str, query: str, filters: Any) -> list[dict]:
        """Called by Celery worker (sync context via asyncio.run)."""
        return await self.search(job_id, query, filters)

    @abstractmethod
    async def search(self, job_id: str, query: str, filters: Any) -> list[dict]:
        """Fetch candidates for query. Return list of raw candidate dicts."""
        ...

    # ── HTTP helpers ───────────────────────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    )
    async def _get(self, url: str, params: dict | None = None, headers: dict | None = None) -> str:
        self._check_rate_limit()
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url, params=params, headers=headers or self._default_headers())
            resp.raise_for_status()
            return resp.text

    async def _get_json(self, url: str, params: dict | None = None, headers: dict | None = None) -> Any:
        self._check_rate_limit()
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url, params=params, headers=headers or self._default_headers())
            resp.raise_for_status()
            return resp.json()

    def _default_headers(self) -> dict:
        return {
            "User-Agent": f"OSINTSupplierBot/1.0 (+https://osint-supplier.com/bot)",
            "Accept": "application/json, text/html",
        }

    # ── Rate limiting ──────────────────────────────────────────────────────────

    def _check_rate_limit(self):
        now = time.time()
        window = 60.0
        if self.name not in _rate_counters:
            _rate_counters[self.name] = []
        # Remove timestamps older than 1 minute
        _rate_counters[self.name] = [t for t in _rate_counters[self.name] if now - t < window]
        if len(_rate_counters[self.name]) >= self.rate_limit_rpm:
            sleep_time = window - (now - _rate_counters[self.name][0]) + 0.5
            if sleep_time > 0:
                logger.debug("Rate limit sleep", adapter=self.name, seconds=round(sleep_time, 1))
                time.sleep(sleep_time)
        _rate_counters[self.name].append(time.time())

    # ── Cache helpers ──────────────────────────────────────────────────────────

    def _cache_key(self, query: str) -> str:
        raw = f"{self.name}::{query.lower().strip()}"
        return hashlib.sha256(raw.encode()).hexdigest()

    async def _get_cached(self, query: str) -> list[dict] | None:
        """Check Supabase adapter_cache for a recent result."""
        try:
            from app.db.session import get_pool
            pool = await get_pool()
            row = await pool.fetchrow(
                "SELECT response_data FROM adapter_cache WHERE cache_key=$1 AND expires_at > NOW()",
                self._cache_key(query),
            )
            if row:
                return json.loads(row["response_data"])
        except Exception as e:
            logger.warning("Cache read error", adapter=self.name, error=str(e))
        return None

    async def _set_cached(self, query: str, data: list[dict]):
        try:
            from app.db.session import get_pool
            pool = await get_pool()
            await pool.execute(
                """
                INSERT INTO adapter_cache (cache_key, adapter, response_data, expires_at)
                VALUES ($1, $2, $3::jsonb, NOW() + $4 * interval '1 hour')
                ON CONFLICT (cache_key) DO UPDATE
                    SET response_data=EXCLUDED.response_data, expires_at=EXCLUDED.expires_at
                """,
                self._cache_key(query),
                self.name,
                json.dumps(data),
                self.cache_ttl_hours,
            )
        except Exception as e:
            logger.warning("Cache write error", adapter=self.name, error=str(e))

    # ── Normalization helpers ──────────────────────────────────────────────────

    def _make_candidate(self, **kwargs) -> dict:
        """Build a raw candidate dict with adapter name always set."""
        kwargs["adapter"] = self.name
        kwargs.setdefault("extra_fields", "{}")
        return kwargs
