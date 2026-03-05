from __future__ import annotations
from adapters.base import BaseAdapter
from adapters.tier1.opencorporates import OpenCorporatesAdapter
from adapters.tier1.gleif import GleifAdapter

# ── Adapter registry ───────────────────────────────────────────────────────────
# Add new adapters here — one line per source.
# All are enabled by default. Set adapter.enabled = False to disable globally.

ADAPTERS: dict[str, BaseAdapter] = {
    # Tier 1 — Business registries (API-based, high trust)
    "opencorporates": OpenCorporatesAdapter(),
    "gleif":          GleifAdapter(),

    # Tier 1 — B2B catalogs (added in Phase 2)
    # "kompass":     KompassAdapter(),
    # "europages":   EuropagesAdapter(),
    # "alibaba":     AlibabaAdapter(),

    # Tier 2 — Trade documents (added in Phase 4-5)
    # "panjiva":     PanjivaAdapter(),
    # "importyeti":  ImportYetiAdapter(),
    # "volza":       VolzaAdapter(),

    # Tier 2 — Directories
    # "yellowpages": YellowPagesAdapter(),
    # "thomasnet":   ThomasNetAdapter(),

    # Tier 2 — Trading platforms
    # "ec21":              EC21Adapter(),
    # "exporthub":         ExportHubAdapter(),
    # "tradekey":          TradekeyAdapter(),
    # "go4worldbusiness":  Go4WorldBusinessAdapter(),
    # "tridge":            TridgeAdapter(),
    # "exporters_india":   ExportersIndiaAdapter(),
    # "tradeindia":        TradeIndiaAdapter(),

    # Tier 3 — Email & supplemental
    # "direct_website":    DirectWebsiteAdapter(),
    # "google_places":     GooglePlacesAdapter(),

    # Tier 3 — Negative signals
    # "ofac":              OFACAdapter(),
}
