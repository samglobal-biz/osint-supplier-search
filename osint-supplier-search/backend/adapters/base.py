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
            from app.db.rest_client import db_select
            import datetime
            rows = await db_select(
                "adapter_cache",
                select="response_data,expires_at",
                cache_key=self._cache_key(query),
            )
            if rows:
                expires_at = rows[0].get("expires_at", "")
                if expires_at:
                    exp = datetime.datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                    if exp > datetime.datetime.now(datetime.timezone.utc):
                        rd = rows[0]["response_data"]
                        # PostgREST returns JSONB already parsed as Python object
                        return rd if isinstance(rd, list) else json.loads(rd)
        except Exception as e:
            logger.warning("Cache read error", adapter=self.name, error=str(e))
        return None

    async def _set_cached(self, query: str, data: list[dict]):
        try:
            from app.db.rest_client import db_select, db_insert, db_update
            import datetime
            expires = (
                datetime.datetime.now(datetime.timezone.utc)
                + datetime.timedelta(hours=self.cache_ttl_hours)
            ).isoformat()
            key = self._cache_key(query)
            # Upsert: check if exists first, then update or insert
            existing = await db_select("adapter_cache", select="cache_key", cache_key=key)
            if existing:
                await db_update("adapter_cache", {
                    "response_data": data,  # JSONB — pass as object
                    "expires_at": expires,
                }, cache_key=key)
            else:
                await db_insert("adapter_cache", {
                    "cache_key": key,
                    "adapter": self.name,
                    "response_data": data,  # JSONB — pass as object
                    "expires_at": expires,
                })
        except Exception as e:
            logger.warning("Cache write error", adapter=self.name, error=str(e))

    # ── Normalization helpers ──────────────────────────────────────────────────

    def _make_candidate(self, **kwargs) -> dict:
        """Build a raw candidate dict with adapter name always set."""
        kwargs["adapter"] = self.name
        kwargs.setdefault("extra_fields", "{}")
        return kwargs
