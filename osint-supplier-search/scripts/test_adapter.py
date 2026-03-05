"""
CLI to test a single adapter.
Usage: python scripts/test_adapter.py opencorporates "Corona beer"
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))


async def main():
    if len(sys.argv) < 3:
        print("Usage: python test_adapter.py <adapter_name> <query>")
        sys.exit(1)

    adapter_name = sys.argv[1]
    query = " ".join(sys.argv[2:])

    from adapters.registry import ADAPTERS
    from app.models.schemas import SearchFilters

    adapter = ADAPTERS.get(adapter_name)
    if not adapter:
        print(f"Adapter '{adapter_name}' not found. Available: {list(ADAPTERS.keys())}")
        sys.exit(1)

    print(f"Testing adapter: {adapter_name}")
    print(f"Query: {query}")
    print("-" * 40)

    results = await adapter.search("test-job-id", query, SearchFilters())

    print(f"Found {len(results)} candidates:\n")
    for i, r in enumerate(results[:5], 1):
        print(f"{i}. {r.get('raw_name', '—')}")
        print(f"   Country: {r.get('raw_country', '—')}")
        print(f"   Address: {r.get('raw_address', '—')}")
        print(f"   Phone:   {r.get('raw_phone', '—')}")
        print(f"   Email:   {r.get('raw_email', '—')}")
        print(f"   Website: {r.get('raw_website', '—')}")
        print(f"   URL:     {r.get('source_url', '—')}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
