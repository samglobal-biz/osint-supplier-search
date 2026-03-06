from __future__ import annotations
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import search, jobs, suppliers

logger = structlog.get_logger()

app = FastAPI(
    title="OSINT Supplier Search API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/debug/db", tags=["health"])
async def debug_db():
    from app.db.rest_client import db_select
    try:
        rows = await db_select("search_jobs", select="id", limit=1)
        return {"status": "ok", "transport": "supabase-rest-https", "test_rows": len(rows)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# v1 routes
app.include_router(search.router, prefix="/v1")
app.include_router(jobs.router, prefix="/v1")
app.include_router(suppliers.router, prefix="/v1")
app.include_router(suppliers.router_export, prefix="/v1")
