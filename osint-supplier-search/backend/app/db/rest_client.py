"""
Supabase REST client — replaces asyncpg for Render IPv6 compatibility.
db.[ref].supabase.co resolves to IPv6-only; Render free tier has no IPv6 outbound.
This client uses HTTPS (PostgREST) which is always IPv4-accessible.
"""
from __future__ import annotations
from typing import Any
import httpx
from app.config import settings


def _base() -> str:
    return f"{settings.supabase_url}/rest/v1"


def _headers(**extra: str) -> dict:
    return {
        "apikey": settings.supabase_service_key,
        "Authorization": f"Bearer {settings.supabase_service_key}",
        "Content-Type": "application/json",
        **extra,
    }


async def db_insert(table: str, data: dict | list[dict]) -> list[dict]:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            f"{_base()}/{table}",
            headers=_headers(Prefer="return=representation"),
            json=data,
        )
        r.raise_for_status()
        result = r.json()
        return result if isinstance(result, list) else [result]


async def db_select(
    table: str,
    select: str = "*",
    order: str | None = None,
    limit: int | None = None,
    **filters: Any,
) -> list[dict]:
    params: dict[str, Any] = {"select": select}
    for k, v in filters.items():
        params[k] = f"eq.{v}"
    if order:
        params["order"] = order
    if limit:
        params["limit"] = limit
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{_base()}/{table}", headers=_headers(), params=params)
        r.raise_for_status()
        return r.json()


async def db_update(table: str, data: dict, **filters: Any) -> None:
    params = {k: f"eq.{v}" for k, v in filters.items()}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.patch(f"{_base()}/{table}", headers=_headers(), params=params, json=data)
        r.raise_for_status()


async def db_update_in(table: str, data: dict, id_field: str, ids: list) -> None:
    """PATCH rows where id_field IN ids list."""
    id_list = ",".join(str(i) for i in ids)
    params = {id_field: f"in.({id_list})"}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.patch(f"{_base()}/{table}", headers=_headers(), params=params, json=data)
        r.raise_for_status()


async def db_delete(table: str, **filters: Any) -> None:
    params = {k: f"eq.{v}" for k, v in filters.items()}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.delete(f"{_base()}/{table}", headers=_headers(), params=params)
        r.raise_for_status()


async def db_count(table: str, **filters: Any) -> int:
    params: dict[str, Any] = {"select": "id"}
    for k, v in filters.items():
        params[k] = f"eq.{v}"
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(
            f"{_base()}/{table}",
            headers=_headers(Prefer="count=exact"),
            params=params,
        )
        r.raise_for_status()
        content_range = r.headers.get("Content-Range", "*/0")
        return int(content_range.split("/")[-1] or 0)


async def db_rpc(func: str, params: dict) -> Any:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            f"{_base()}/rpc/{func}",
            headers=_headers(),
            json=params,
        )
        r.raise_for_status()
        return r.json()
