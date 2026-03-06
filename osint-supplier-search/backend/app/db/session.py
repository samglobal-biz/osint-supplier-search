"""Backward-compat stub — DB operations now use app.db.rest_client (HTTPS/PostgREST).
Supabase DB host is IPv6-only; Render free tier has no outbound IPv6.
"""
from __future__ import annotations


async def get_pool():
    raise RuntimeError(
        "asyncpg pool unavailable: Supabase DB is IPv6-only, Render free tier lacks outbound IPv6. "
        "Use app.db.rest_client instead."
    )


async def close_pool() -> None:
    pass
