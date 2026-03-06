from __future__ import annotations
import ssl
import urllib.parse
import asyncpg
from app.config import settings

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        # Parse DSN to extract components — avoids percent-encoding issues in password
        parsed = urllib.parse.urlparse(settings.database_url)
        _pool = await asyncpg.create_pool(
            host=parsed.hostname,
            port=parsed.port or 5432,
            user=urllib.parse.unquote(parsed.username or ""),
            password=urllib.parse.unquote(parsed.password or ""),
            database=(parsed.path or "/postgres").lstrip("/"),
            min_size=1,
            max_size=5,
            command_timeout=30,
            ssl=ssl_ctx,
            statement_cache_size=0,  # Required for PgBouncer transaction mode
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
