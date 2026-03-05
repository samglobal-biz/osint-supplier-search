from __future__ import annotations
from adapters.base import BaseAdapter
from adapters.tier1.opencorporates import OpenCorporatesAdapter
from adapters.tier1.gleif import GleifAdapter
from adapters.tier2.europages import EuropagesAdapter
from adapters.tier2.ec21 import EC21Adapter
from adapters.tier2.exporthub import ExportHubAdapter
from adapters.tier2.tradekey import TradekeyAdapter
from adapters.tier2.go4worldbusiness import Go4WorldBusinessAdapter
from adapters.tier2.importyeti import ImportYetiAdapter
from adapters.tier2.thomasnet import ThomasNetAdapter
from adapters.tier2.direct_website import DirectWebsiteAdapter

# ── Adapter registry ───────────────────────────────────────────────────────────
# Add new adapters here — one line per source.
# All are enabled by default. Set adapter.enabled = False to disable globally.

ADAPTERS: dict[str, BaseAdapter] = {
    # Tier 1 — Business registries (API-based, high trust)
    "opencorporates": OpenCorporatesAdapter(),
    "gleif":          GleifAdapter(),

    # Tier 2 — B2B catalogs & directories
    "europages":         EuropagesAdapter(),
    "ec21":              EC21Adapter(),
    "exporthub":         ExportHubAdapter(),
    "tradekey":          TradekeyAdapter(),
    "go4worldbusiness":  Go4WorldBusinessAdapter(),
    "thomasnet":         ThomasNetAdapter(),

    # Tier 2 — Trade documents (import/export records)
    "importyeti":        ImportYetiAdapter(),

    # Tier 2 — Contact enrichment (scrapes company websites)
    "direct_website":    DirectWebsiteAdapter(),

    # Tier 1 — B2B catalogs (Playwright, added in Phase 3)
    # "kompass":           KompassAdapter(),
    # "alibaba":           AlibabaAdapter(),

    # Tier 2 — More trading platforms (Phase 3)
    # "panjiva":           PanjivaAdapter(),
    # "volza":             VolzaAdapter(),
    # "yellowpages":       YellowPagesAdapter(),
    # "exporters_india":   ExportersIndiaAdapter(),
    # "tradeindia":        TradeIndiaAdapter(),
    # "tridge":            TridgeAdapter(),

    # Tier 3 — Paid APIs (Phase 4)
    # "google_places":     GooglePlacesAdapter(),

    # Tier 3 — Negative signals (Phase 4)
    # "ofac":              OFACAdapter(),
}
