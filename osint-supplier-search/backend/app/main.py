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


@app.get("/debug/adapters", tags=["health"])
async def debug_adapters():
    """Test HTTP connectivity to key adapter sources from this server."""
    import httpx
    tests = [
        ("gleif", "https://api.gleif.org/api/v1/lei-records?filter%5Bentity.legalName%5D=test&page%5Bsize%5D=1"),
        ("opencorporates", "https://api.opencorporates.com/v0.4/companies/search?q=test&per_page=1&format=json"),
        ("europages", "https://www.europages.co.uk/en/search?text=steel+pipe"),
        ("importyeti", "https://www.importyeti.com/company/corona"),
        ("wlw", "https://www.wlw.de/search?q=stahl"),
        ("tradekey", "https://www.tradekey.com/products/steel-pipe.html"),
        ("go4worldbusiness", "https://go4worldbusiness.com/search/steel-pipe.html"),
        ("b2brazil", "https://www.b2brazil.com.br/search?q=steel"),
        ("ec21", "https://www.ec21.com/trade/steel-pipe/"),
        ("thomasnet", "https://www.thomasnet.com/search/?what=steel+pipe"),
        ("kompass", "https://www.kompass.com/searchCompanies?text=steel+pipe"),
        ("directindustry", "https://www.directindustry.com/industrial-manufacturer/steel-pipe-127631.html"),
        ("tridge", "https://www.tridge.com/intelligences/steel-pipe"),
        ("wikidata", "https://www.wikidata.org/w/api.php?action=wbsearchentities&search=steel+pipe&language=en&format=json"),
    ]
    results = {}
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        for name, url in tests:
            try:
                r = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
                results[name] = {"status": r.status_code, "size": len(r.text)}
            except Exception as e:
                results[name] = {"status": "error", "error": str(e)}
    return results


@app.get("/debug/cf", tags=["health"])
async def debug_cf():
    """Test curl-cffi CF bypass for Cloudflare-protected sites."""
    cf_sites = [
        ("importyeti", "https://www.importyeti.com/company/corona"),
        ("thomasnet", "https://www.thomasnet.com/search/?what=steel+pipe"),
        ("directindustry", "https://www.directindustry.com/industrial-manufacturer/steel-pipe-127631.html"),
    ]
    results = {}
    try:
        from curl_cffi.requests import AsyncSession
        async with AsyncSession(impersonate="chrome120") as session:
            for name, url in cf_sites:
                try:
                    r = await session.get(url, timeout=20, allow_redirects=True)
                    cf_blocked = "Just a moment" in r.text or "cf-browser-verification" in r.text
                    results[name] = {"status": r.status_code, "size": len(r.text), "cf_blocked": cf_blocked}
                except Exception as e:
                    results[name] = {"status": "error", "error": str(e)}
        results["curl_cffi"] = "available"
    except ImportError:
        results["curl_cffi"] = "NOT INSTALLED"
    return results


# v1 routes
app.include_router(search.router, prefix="/v1")
app.include_router(jobs.router, prefix="/v1")
app.include_router(suppliers.router, prefix="/v1")
app.include_router(suppliers.router_export, prefix="/v1")
