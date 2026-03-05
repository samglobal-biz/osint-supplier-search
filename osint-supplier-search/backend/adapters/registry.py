from __future__ import annotations
from adapters.base import BaseAdapter

# Tier 1 — Official registries & APIs
from adapters.tier1.opencorporates import OpenCorporatesAdapter
from adapters.tier1.gleif import GleifAdapter

# Tier 2 — B2B catalogs & directories
from adapters.tier2.europages import EuropagesAdapter
from adapters.tier2.ec21 import EC21Adapter
from adapters.tier2.exporthub import ExportHubAdapter
from adapters.tier2.tradekey import TradekeyAdapter
from adapters.tier2.go4worldbusiness import Go4WorldBusinessAdapter
from adapters.tier2.thomasnet import ThomasNetAdapter
from adapters.tier2.kompass import KompassAdapter
from adapters.tier2.directindustry import DirectIndustryAdapter
from adapters.tier2.wlw import WLWAdapter

# Tier 2 — Asian B2B platforms
from adapters.tier2.made_in_china import MadeInChinaAdapter
from adapters.tier2.global_sources import GlobalSourcesAdapter
from adapters.tier2.exporters_india import ExportersIndiaAdapter
from adapters.tier2.tradeindia import TradeIndiaAdapter
from adapters.tier2.indiamart import IndiaMartAdapter
from adapters.tier2.alibaba_suppliers import AlibabaAdapter
from adapters.tier2.dhgate import DHgateAdapter

# Tier 2 — Trade data (import/export records)
from adapters.tier2.importyeti import ImportYetiAdapter
from adapters.tier2.volza import VolzaAdapter
from adapters.tier2.tridge import TridgeAdapter

# Tier 2 — Regional directories
from adapters.tier2.yellow_pages_us import YellowPagesUSAdapter
from adapters.tier2.yell_uk import YellUKAdapter
from adapters.tier2.gelbeseiten import GelbeSeitenAdapter
from adapters.tier2.pagine_gialle import PagineGialleAdapter
from adapters.tier2.manta import MantaAdapter
from adapters.tier2.cylex import CylexAdapter
from adapters.tier2.b2brazil import B2BrazilAdapter

# Tier 2 — Contact enrichment
from adapters.tier2.direct_website import DirectWebsiteAdapter

# Tier 3 — Compliance & sanctions
from adapters.tier3.ofac import OFACAdapter
from adapters.tier3.eu_sanctions import EUSanctionsAdapter
from adapters.tier3.open_sanctions import OpenSanctionsAdapter

# Tier 3 — Official registries
from adapters.tier3.companies_house_uk import CompaniesHouseUKAdapter
from adapters.tier3.wikidata import WikidataAdapter
from adapters.tier3.panjiva import PanjivaAdapter

# Tier 3 — Maritime / customs / Bill of Lading
from adapters.tier3.zauba import ZaubaAdapter
from adapters.tier3.seair import SeairAdapter
from adapters.tier3.import_genius import ImportGeniusAdapter
from adapters.tier3.export_genius import ExportGeniusAdapter
from adapters.tier3.trade_atlas import TradeAtlasAdapter
from adapters.tier3.shipmentsfrom import ShipmentsFromAdapter
from adapters.tier3.un_comtrade import UNComtradeAdapter

# ── Adapter registry ───────────────────────────────────────────────────────────
# All adapters enabled by default.
# Add new adapter: 1 file + 1 import + 1 line here.

ADAPTERS: dict[str, BaseAdapter] = {

    # ── Official registries (highest trust) ────────────────────────────────────
    "opencorporates":    OpenCorporatesAdapter(),
    "gleif":             GleifAdapter(),
    "companies_house_uk": CompaniesHouseUKAdapter(),
    "wikidata":          WikidataAdapter(),

    # ── Global B2B catalogs ────────────────────────────────────────────────────
    "kompass":           KompassAdapter(),
    "europages":         EuropagesAdapter(),
    "directindustry":    DirectIndustryAdapter(),
    "wlw":               WLWAdapter(),          # DE/AT/CH
    "thomasnet":         ThomasNetAdapter(),    # USA industrial

    # ── Asian B2B platforms ────────────────────────────────────────────────────
    "alibaba":           AlibabaAdapter(),
    "made_in_china":     MadeInChinaAdapter(),
    "global_sources":    GlobalSourcesAdapter(),
    "dhgate":            DHgateAdapter(),
    "indiamart":         IndiaMartAdapter(),
    "exporters_india":   ExportersIndiaAdapter(),
    "tradeindia":        TradeIndiaAdapter(),

    # ── Trading platforms / marketplaces ──────────────────────────────────────
    "ec21":              EC21Adapter(),
    "exporthub":         ExportHubAdapter(),
    "tradekey":          TradekeyAdapter(),
    "go4worldbusiness":  Go4WorldBusinessAdapter(),

    # ── Trade data (customs / shipping records / Bill of Lading) ─────────────
    "importyeti":        ImportYetiAdapter(),   # USA Bill of Lading (free)
    "volza":             VolzaAdapter(),        # Global customs data
    "tridge":            TridgeAdapter(),       # Food & agri
    "panjiva":           PanjivaAdapter(),      # S&P Global trade data
    "zauba":             ZaubaAdapter(),        # India customs BoL
    "seair":             SeairAdapter(),        # India import/export shipments
    "import_genius":     ImportGeniusAdapter(), # US customs BoL
    "export_genius":     ExportGeniusAdapter(), # Global customs (India, China, Vietnam)
    "trade_atlas":       TradeAtlasAdapter(),   # Turkey, Russia, CIS customs
    "shipments_from":    ShipmentsFromAdapter(), # USA BoL aggregator
    "un_comtrade":       UNComtradeAdapter(),   # UN official trade stats

    # ── Regional directories ───────────────────────────────────────────────────
    "yellow_pages_us":   YellowPagesUSAdapter(),
    "yell_uk":           YellUKAdapter(),
    "gelbeseiten":       GelbeSeitenAdapter(),  # Germany
    "pagine_gialle":     PagineGialleAdapter(), # Italy
    "manta":             MantaAdapter(),        # USA SMB
    "cylex":             CylexAdapter(),        # International
    "b2brazil":          B2BrazilAdapter(),     # Brazil

    # ── Compliance / sanctions ─────────────────────────────────────────────────
    "ofac":              OFACAdapter(),
    "eu_sanctions":      EUSanctionsAdapter(),
    "open_sanctions":    OpenSanctionsAdapter(),

    # ── Contact enrichment ─────────────────────────────────────────────────────
    "direct_website":    DirectWebsiteAdapter(),
}
