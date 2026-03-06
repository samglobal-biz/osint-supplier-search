from __future__ import annotations
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.session import get_pool, close_pool
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
    allow_origins=["*"],  # tighten in production to Vercel domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    try:
        await get_pool()
        logger.info("Database pool initialized")
    except Exception as e:
        logger.warning("Database pool not initialized (will retry on first request)", error=str(e))


@app.on_event("shutdown")
async def shutdown():
    await close_pool()


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/debug/db", tags=["health"])
async def debug_db():
    try:
        pool = await get_pool()
        result = await pool.fetchval("SELECT version()")
        return {"status": "ok", "pg_version": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# v1 routes
app.include_router(search.router, prefix="/v1")
app.include_router(jobs.router, prefix="/v1")
app.include_router(suppliers.router, prefix="/v1")
app.include_router(suppliers.router_export, prefix="/v1")
