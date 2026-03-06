from __future__ import annotations
import ssl
import socket
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

        parsed = urllib.parse.urlparse(settings.database_url)
        hostname = parsed.hostname or ""
        port = parsed.port or 5432

        # Force IPv4 — Render free tier doesn't support IPv6 outbound
        try:
            ipv4 = socket.getaddrinfo(hostname, port, socket.AF_INET)[0][4][0]
        except (socket.gaierror, IndexError):
            ipv4 = hostname  # fall back to hostname if no IPv4 found

        _pool = await asyncpg.create_pool(
            host=ipv4,
            port=port,
            user=urllib.parse.unquote(parsed.username or ""),
            password=urllib.parse.unquote(parsed.password or ""),
            database=(parsed.path or "/postgres").lstrip("/"),
            min_size=1,
            max_size=5,
            command_timeout=30,
            ssl=ssl_ctx,
            statement_cache_size=0,
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
