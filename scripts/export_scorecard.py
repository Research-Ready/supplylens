"""export_scorecard.py — per-supplier scorecard PDF generator for UC4 / SupplyLens.

Usage:
    python3 scripts/export_scorecard.py                          # all suppliers
    python3 scripts/export_scorecard.py --supplier "Bosch"       # one supplier
    python3 scripts/export_scorecard.py --product SCANIA-R-500   # product T1 chain
    python3 scripts/export_scorecard.py --dry-run                # list only, no PDF
    python3 scripts/export_scorecard.py --output-dir /tmp/sc     # custom output dir

Dependencies: reportlab>=4.0  (stdlib only otherwise)
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

CertDict = dict[str, str]         # {name, valid_until}
EvidenceDict = dict[str, Any]      # {source_doc, excerpt, confidence, reviewed}

SupplierRecord = dict[str, Any]
"""Keys: name, country, tier, headquarters, founded_year, annual_revenue_eur,
         employee_count, risk_flags, certificates, risk_score, evidence,
         upstream_chain (list[str])"""

# ---------------------------------------------------------------------------
# Country flag text mapping (emoji flag via regional indicators)
# ---------------------------------------------------------------------------

_CC_TO_FLAG: dict[str, str] = {
    "DE": "\U0001f1e9\U0001f1ea",
    "SE": "\U0001f1f8\U0001f1ea",
    "FR": "\U0001f1eb\U0001f1f7",
    "US": "\U0001f1fa\U0001f1f8",
    "NL": "\U0001f1f3\U0001f1f1",
    "CN": "\U0001f1e8\U0001f1f3",
    "GB": "\U0001f1ec\U0001f1e7",
    "JP": "\U0001f1ef\U0001f1f5",
    "KR": "\U0001f1f0\U0001f1f7",
}


def country_flag(cc: str) -> str:
    return _CC_TO_FLAG.get((cc or "").upper(), "")


# ---------------------------------------------------------------------------
# Risk colour
# ---------------------------------------------------------------------------

def risk_colour(score: float) -> tuple[float, float, float]:
    """Return (R, G, B) normalised 0-1 for the risk ring fill."""
    if score < 0.3:
        return (34 / 255, 197 / 255, 94 / 255)    # green  #22c55e
    if score < 0.6:
        return (245 / 255, 158 / 255, 11 / 255)   # amber  #f59e0b
    return (239 / 255, 68 / 255, 68 / 255)         # red    #ef4444


# ---------------------------------------------------------------------------
# Flag pill colours
# ---------------------------------------------------------------------------

_FLAG_COLOURS: dict[str, tuple[float, float, float]] = {
    "SINGLE_SOURCE":         (0.93, 0.27, 0.27),
    "GEOPOLITICAL_RISK":     (0.96, 0.62, 0.04),
    "CONFLICT_MINERAL":      (0.93, 0.80, 0.04),
    "SANCTIONS_RISK":        (0.88, 0.20, 0.20),
    "CLIMATE_RISK":          (0.20, 0.60, 0.86),
    "ESG_RISK":              (0.55, 0.27, 0.07),
    "DEFORESTATION_RISK":    (0.13, 0.55, 0.13),
    "DODD_FRANK_REPORTABLE": (0.62, 0.13, 0.94),
    "CHILD_LABOUR_RISK":     (0.85, 0.10, 0.10),
    "ARCTIC_OPERATIONS":     (0.20, 0.50, 0.85),
    "TAILINGS_RISK":         (0.60, 0.40, 0.10),
}

_DEFAULT_PILL = (0.45, 0.45, 0.45)


def flag_colour(flag: str) -> tuple[float, float, float]:
    return _FLAG_COLOURS.get(flag, _DEFAULT_PILL)


# ---------------------------------------------------------------------------
# Slug helper
# ---------------------------------------------------------------------------

def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


# ---------------------------------------------------------------------------
# Demo data
# ---------------------------------------------------------------------------

DEMO_SUPPLIERS: list[SupplierRecord] = [
    {
        "name": "ZF Friedrichshafen",
        "country": "DE",
        "tier": 1,
        "headquarters": "Friedrichshafen, Germany",
        "founded_year": 1915,
        "annual_revenue_eur": 43800000000,
        "employee_count": 157000,
        "risk_flags": ["SINGLE_SOURCE"],
        "risk_score": 0.30,
        "certificates": [
            {"name": "ISO 9001:2015",   "valid_until": "2027-12-31"},
            {"name": "IATF 16949:2016", "valid_until": "2026-09-30"},
        ],
        "evidence": [
            {
                "source_doc": "ZF Annual Report 2023",
                "excerpt": "TraXon automated transmission supplied exclusively to Scania R-series; no alternative qualified.",
                "confidence": 0.92,
                "reviewed": True,
            },
            {
                "source_doc": "Scania Supplier Portal",
                "excerpt": "ZF listed as sole-source for 12-speed automated gearbox platform.",
                "confidence": 0.88,
                "reviewed": True,
            },
        ],
        "upstream_chain": ["ZF Friedrichshafen", "Saarstahl AG", "Iron Ore Pellets"],
    },
    {
        "name": "Bosch",
        "country": "DE",
        "tier": 1,
        "headquarters": "Stuttgart, Germany",
        "founded_year": 1886,
        "annual_revenue_eur": 91600000000,
        "employee_count": 429000,
        "risk_flags": ["CONFLICT_MINERAL", "GEOPOLITICAL_RISK"],
        "risk_score": 0.55,
        "certificates": [
            {"name": "ISO 9001:2015",   "valid_until": "2027-12-31"},
            {"name": "IATF 16949:2016", "valid_until": "2026-09-30"},
            {"name": "ISO 14001:2015",  "valid_until": "2026-06-30"},
        ],
        "evidence": [
            {
                "source_doc": "Bosch Sustainability Report 2023",
                "excerpt": "Conflict minerals (Ta, Sn, W, Au) present in fuel injection components; OECD DD in progress.",
                "confidence": 0.85,
                "reviewed": True,
            },
            {
                "source_doc": "LLM inference — Infineon data sheet",
                "excerpt": "Infineon semiconductors sourced from CN wafer fabs — geopolitical exposure flagged.",
                "confidence": 0.71,
                "reviewed": False,
            },
        ],
        "upstream_chain": ["Bosch", "Infineon Technologies", "China Rare Earth Group", "Rare Earth Elements"],
    },
    {
        "name": "SSAB",
        "country": "SE",
        "tier": 1,
        "headquarters": "Stockholm, Sweden",
        "founded_year": 1978,
        "annual_revenue_eur": 9200000000,
        "employee_count": 14600,
        "risk_flags": ["CLIMATE_RISK"],
        "risk_score": 0.15,
        "certificates": [
            {"name": "ISO 9001:2015",  "valid_until": "2027-12-31"},
            {"name": "ISO 14001:2015", "valid_until": "2026-06-30"},
            {"name": "REACH Compliance", "valid_until": "2030-01-01"},
        ],
        "evidence": [
            {
                "source_doc": "SSAB HYBRIT press release 2023",
                "excerpt": "Fossil-free steel production pilot operational; full-scale planned 2030.",
                "confidence": 0.95,
                "reviewed": True,
            },
        ],
        "upstream_chain": ["SSAB", "LKAB", "Iron Ore Pellets"],
    },
    {
        "name": "Michelin",
        "country": "FR",
        "tier": 1,
        "headquarters": "Clermont-Ferrand, France",
        "founded_year": 1889,
        "annual_revenue_eur": 28600000000,
        "employee_count": 132200,
        "risk_flags": ["DEFORESTATION_RISK"],
        "risk_score": 0.12,
        "certificates": [
            {"name": "ISO 9001:2015",  "valid_until": "2027-12-31"},
            {"name": "ISO 14001:2015", "valid_until": "2026-06-30"},
        ],
        "evidence": [
            {
                "source_doc": "Michelin Group Sustainability Report 2023",
                "excerpt": "Natural rubber sourced from SE Asia; deforestation risk flagged in tier-3 plantations.",
                "confidence": 0.80,
                "reviewed": True,
            },
        ],
        "upstream_chain": ["Michelin", "Natural Rubber (Thailand)", "Carbon Black (Russia)"],
    },
    {
        "name": "Dana Incorporated",
        "country": "US",
        "tier": 1,
        "headquarters": "Maumee, Ohio, USA",
        "founded_year": 1904,
        "annual_revenue_eur": 8900000000,
        "employee_count": 40000,
        "risk_flags": [],
        "risk_score": 0.08,
        "certificates": [
            {"name": "IATF 16949:2016", "valid_until": "2026-09-30"},
            {"name": "ISO 9001:2015",   "valid_until": "2027-12-31"},
        ],
        "evidence": [
            {
                "source_doc": "Dana Supplier Qualification Form 2022",
                "excerpt": "Axle and driveshaft assembly — multi-source qualified; no single-source risk.",
                "confidence": 0.87,
                "reviewed": True,
            },
        ],
        "upstream_chain": ["Dana Incorporated", "Steel Billets (Germany)"],
    },
    {
        "name": "Infineon Technologies",
        "country": "DE",
        "tier": 2,
        "headquarters": "Neubiberg, Germany",
        "founded_year": 1999,
        "annual_revenue_eur": 16300000000,
        "employee_count": 58060,
        "risk_flags": ["GEOPOLITICAL_RISK", "CONFLICT_MINERAL"],
        "risk_score": 0.62,
        "certificates": [
            {"name": "ISO 9001:2015",  "valid_until": "2027-12-31"},
            {"name": "IATF 16949:2016", "valid_until": "2026-09-30"},
        ],
        "evidence": [
            {
                "source_doc": "Infineon Conflict Minerals Report 2023",
                "excerpt": "Wafer fabrication uses tantalum capacitors; smelter list includes DRC-linked entities.",
                "confidence": 0.83,
                "reviewed": True,
            },
            {
                "source_doc": "LLM inference — supply chain database",
                "excerpt": "Rare earth elements sourced via China Rare Earth Group — geopolitical concentration risk.",
                "confidence": 0.68,
                "reviewed": False,
            },
        ],
        "upstream_chain": ["Infineon Technologies", "China Rare Earth Group", "Rare Earth Elements"],
    },
    {
        "name": "LKAB",
        "country": "SE",
        "tier": 2,
        "headquarters": "Lulea, Sweden",
        "founded_year": 1890,
        "annual_revenue_eur": 4100000000,
        "employee_count": 4800,
        "risk_flags": ["ARCTIC_OPERATIONS"],
        "risk_score": 0.10,
        "certificates": [
            {"name": "ISO 14001:2015", "valid_until": "2026-06-30"},
            {"name": "ISO 9001:2015",  "valid_until": "2027-12-31"},
        ],
        "evidence": [
            {
                "source_doc": "LKAB Annual Report 2023",
                "excerpt": "Underground iron ore mining in Kiruna (Arctic Circle); high-quality pellets, low-carbon ambition.",
                "confidence": 0.93,
                "reviewed": True,
            },
        ],
        "upstream_chain": ["LKAB", "Iron Ore Pellets"],
    },
    {
        "name": "China Rare Earth Group",
        "country": "CN",
        "tier": 3,
        "headquarters": "Ganzhou, Jiangxi, China",
        "founded_year": 2021,
        "annual_revenue_eur": 6700000000,
        "employee_count": 38000,
        "risk_flags": ["GEOPOLITICAL_RISK", "SANCTIONS_RISK", "CONFLICT_MINERAL"],
        "risk_score": 0.88,
        "certificates": [],
        "evidence": [
            {
                "source_doc": "LLM inference — SEC filing cross-reference",
                "excerpt": "State-owned enterprise; rare earth processing under Chinese export control regulation.",
                "confidence": 0.74,
                "reviewed": False,
            },
            {
                "source_doc": "EU Critical Raw Materials Act watchlist 2024",
                "excerpt": "Rare earth elements listed as critical; single-country sourcing flagged as strategic risk.",
                "confidence": 0.90,
                "reviewed": True,
            },
        ],
        "upstream_chain": ["China Rare Earth Group", "Rare Earth Elements (Jiangxi)"],
    },
    {
        "name": "AMS Buttons BV",
        "country": "NL",
        "tier": 1,
        "headquarters": "Amsterdam, Netherlands",
        "founded_year": 1987,
        "annual_revenue_eur": 12000000,
        "employee_count": 85,
        "risk_flags": [],
        "risk_score": 0.07,
        "certificates": [
            {"name": "ISO 9001:2015",    "valid_until": "2027-12-31"},
            {"name": "REACH Compliance", "valid_until": "2030-01-01"},
        ],
        "evidence": [
            {
                "source_doc": "Unstructured extraction — amsbuttons.nl",
                "excerpt": "ISO 9001:2015 certified; ABS plastic from BASF Germany, steel pins from Shenzhen.",
                "confidence": 0.79,
                "reviewed": True,
            },
        ],
        "upstream_chain": ["AMS Buttons BV", "Plastic Pellets (Germany)", "Metal Pins (China)"],
    },
]

# Index by name for fast lookup
_DEMO_INDEX: dict[str, SupplierRecord] = {s["name"]: s for s in DEMO_SUPPLIERS}


# ---------------------------------------------------------------------------
# Neo4j data loading
# ---------------------------------------------------------------------------

NEO4J_URL  = os.getenv("NEO4J_URL",      "http://localhost:7474")
NEO4J_USER = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "changeme")


def _neo4j_post(statements: list[dict]) -> list[dict] | None:
    """POST to Neo4j HTTP API. Returns None on any error."""
    import base64
    creds = base64.b64encode(f"{NEO4J_USER}:{NEO4J_PASS}".encode()).decode()
    url = NEO4J_URL.rstrip("/") + "/db/neo4j/tx/commit"
    payload = json.dumps({"statements": statements}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": "Basic " + creds},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        if data.get("errors"):
            return None
        return data["results"]
    except Exception:
        return None


def _rows(results: list[dict], idx: int = 0) -> list[dict]:
    if not results or idx >= len(results):
        return []
    cols = results[idx]["columns"]
    return [dict(zip(cols, row["row"])) for row in results[idx]["data"]]


def neo4j_available() -> bool:
    return _neo4j_post([{"statement": "RETURN 1"}]) is not None


def load_all_from_neo4j() -> list[SupplierRecord] | None:
    results = _neo4j_post([{"statement": "MATCH (s:Supplier) RETURN s"}])
    if results is None:
        return None
    raw_rows = _rows(results, 0)
    if not raw_rows:
        return None
    suppliers: list[SupplierRecord] = []
    for row in raw_rows:
        node: dict = row.get("s") or {}
        name: str = node.get("name", "Unknown")
        supplier = _build_record_from_node(node)
        _enrich_from_neo4j(supplier, name)
        suppliers.append(supplier)
    return suppliers or None


def _build_record_from_node(node: dict) -> SupplierRecord:
    flags = node.get("risk_flags") or []
    if isinstance(flags, str):
        flags = [f.strip() for f in flags.split(",") if f.strip()]
    return {
        "name":               node.get("name", "Unknown"),
        "country":            node.get("country", ""),
        "tier":               node.get("tier", 1),
        "headquarters":       node.get("headquarters", ""),
        "founded_year":       node.get("founded_year"),
        "annual_revenue_eur": node.get("annual_revenue_eur"),
        "employee_count":     node.get("employee_count"),
        "risk_flags":         flags,
        "risk_score":         float(node.get("risk_score") or 0.0),
        "certificates":       [],
        "evidence":           [],
        "upstream_chain":     [node.get("name", "")],
    }


def _enrich_from_neo4j(supplier: SupplierRecord, name: str) -> None:
    """Fetch certificates, evidence and upstream chain from Neo4j."""
    statements = [
        {"statement": (
            "MATCH (e:EvidenceClaim)-[:EVIDENCE_FOR]->(s:Supplier {name: $name}) "
            "RETURN e ORDER BY e.ingest_date DESC LIMIT 5"
        ), "parameters": {"name": name}},
        {"statement": (
            "MATCH (s:Supplier {name: $name})-[:CERTIFIED_BY]->(c:Certificate) RETURN c"
        ), "parameters": {"name": name}},
        {"statement": (
            "MATCH path=(s:Supplier {name: $name})-[:SOURCED_FROM*1..4]->(n) "
            "RETURN [node IN nodes(path) | node.name] AS chain LIMIT 1"
        ), "parameters": {"name": name}},
    ]
    results = _neo4j_post(statements)
    if results is None:
        return

    for row in _rows(results, 0):
        e = row.get("e") or {}
        supplier["evidence"].append({
            "source_doc":  e.get("source_doc", ""),
            "excerpt":     e.get("excerpt", ""),
            "confidence":  float(e.get("confidence") or 0.0),
            "reviewed":    bool(e.get("reviewed")),
        })

    for row in _rows(results, 1):
        c = row.get("c") or {}
        supplier["certificates"].append({
            "name":        c.get("name", ""),
            "valid_until": c.get("valid_until", ""),
        })

    chain_rows = _rows(results, 2)
    if chain_rows:
        chain = chain_rows[0].get("chain") or []
        if chain:
            supplier["upstream_chain"] = chain


def load_product_chain_from_neo4j(product_sku: str) -> list[SupplierRecord] | None:
    results = _neo4j_post([{
        "statement": (
            "MATCH (p:Product {sku: $sku})-[:SUPPLIED_BY]->(s:Supplier) RETURN s"
        ),
        "parameters": {"sku": product_sku},
    }])
    if results is None:
        return None
    raw_rows = _rows(results, 0)
    if not raw_rows:
        return None
    suppliers: list[SupplierRecord] = []
    for row in raw_rows:
        node: dict = row.get("s") or {}
        name: str = node.get("name", "Unknown")
        supplier = _build_record_from_node(node)
        _enrich_from_neo4j(supplier, name)
        suppliers.append(supplier)
    return suppliers or None


# ---------------------------------------------------------------------------
# PDF generation — layout constants
# ---------------------------------------------------------------------------

PAGE_W, PAGE_H = 595.28, 841.89   # A4 points

DARK_BLUE   = (30 / 255, 58 / 255, 95 / 255)   # #1e3a5f
WHITE       = (1.0, 1.0, 1.0)
LIGHT_GREY  = (0.93, 0.93, 0.93)
MID_GREY    = (0.55, 0.55, 0.55)
DARK_GREY   = (0.20, 0.20, 0.20)
BLACK       = (0.0, 0.0, 0.0)
ACCENT_BLUE = (0.10, 0.44, 0.78)

MARGIN_L = 36.0
MARGIN_R = 36.0
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def _set_fill(c: Any, rgb: tuple[float, float, float]) -> None:
    c.setFillColorRGB(*rgb)


def _set_stroke(c: Any, rgb: tuple[float, float, float]) -> None:
    c.setStrokeColorRGB(*rgb)


def _draw_rect(
    c: Any,
    x: float, y: float, w: float, h: float,
    fill: tuple[float, float, float],
    stroke: tuple[float, float, float] | None = None,
    radius: float = 0,
) -> None:
    _set_fill(c, fill)
    if stroke:
        _set_stroke(c, stroke)
        c.setLineWidth(0.5)
    else:
        c.setLineWidth(0)
    if radius:
        c.roundRect(x, y, w, h, radius, fill=1, stroke=1 if stroke else 0)
    else:
        c.rect(x, y, w, h, fill=1, stroke=1 if stroke else 0)


def _draw_text(
    c: Any,
    text: str,
    x: float, y: float,
    font: str = "Helvetica",
    size: float = 10,
    colour: tuple[float, float, float] = BLACK,
) -> None:
    _set_fill(c, colour)
    c.setFont(font, size)
    c.drawString(x, y, text)


def _draw_text_right(
    c: Any,
    text: str,
    x: float, y: float,
    font: str = "Helvetica",
    size: float = 10,
    colour: tuple[float, float, float] = BLACK,
) -> None:
    _set_fill(c, colour)
    c.setFont(font, size)
    c.drawRightString(x, y, text)


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 1] + "\u2026"


# ---------------------------------------------------------------------------
# Section: header band
# ---------------------------------------------------------------------------

def _draw_header(c: Any, gen_date: str) -> float:
    """Draw top header band. Returns y position below band."""
    band_h = 48.0
    y_top  = PAGE_H - band_h
    _draw_rect(c, 0, y_top, PAGE_W, band_h, fill=DARK_BLUE)

    _draw_text(c, "SupplyLens Scorecard", MARGIN_L, y_top + 17,
               font="Helvetica-Bold", size=16, colour=WHITE)
    _draw_text(c, "Scania AB", PAGE_W - MARGIN_R - 80, y_top + 22,
               font="Helvetica-Bold", size=10, colour=WHITE)
    _draw_text(c, f"Generated: {gen_date}", PAGE_W - MARGIN_R - 80, y_top + 10,
               font="Helvetica", size=7, colour=(0.75, 0.75, 0.85))
    return y_top - 8.0


# ---------------------------------------------------------------------------
# Section: supplier hero
# ---------------------------------------------------------------------------

def _draw_hero(c: Any, supplier: SupplierRecord, y: float) -> float:
    """Supplier name, flag, tier badge, HQ, founded. Returns y below section."""
    tier = supplier.get("tier", 1)
    name = supplier["name"]
    cc   = (supplier.get("country") or "").upper()
    flag = country_flag(cc)
    hq   = supplier.get("headquarters") or cc or "—"
    yr   = supplier.get("founded_year")

    _draw_text(c, f"{flag}  {name}", MARGIN_L, y - 4,
               font="Helvetica-Bold", size=18, colour=DARK_GREY)

    # Tier badge
    badge_label = f"T{tier}"
    _draw_rect(c, MARGIN_L, y - 30, 28, 16, fill=ACCENT_BLUE, radius=3)
    _draw_text(c, badge_label, MARGIN_L + 5, y - 24,
               font="Helvetica-Bold", size=9, colour=WHITE)

    sub = f"Headquarters: {hq}"
    if yr:
        sub += f"   |   Founded: {yr}"
    _draw_text(c, sub, MARGIN_L + 36, y - 24,
               font="Helvetica", size=9, colour=MID_GREY)

    # Thin rule
    y2 = y - 38
    _set_stroke(c, LIGHT_GREY)
    c.setLineWidth(0.5)
    c.line(MARGIN_L, y2, PAGE_W - MARGIN_R, y2)
    return y2 - 8.0


# ---------------------------------------------------------------------------
# Section: risk ring
# ---------------------------------------------------------------------------

def _draw_risk_ring(c: Any, score: float, cx: float, cy: float, r: float = 28.0) -> None:
    """Draw a filled circle with score percentage text."""
    from reportlab.lib.colors import Color  # type: ignore

    rgb = risk_colour(score)
    fill_col = Color(rgb[0], rgb[1], rgb[2], alpha=1)
    ring_col = Color(rgb[0] * 0.7, rgb[1] * 0.7, rgb[2] * 0.7, alpha=1)

    c.saveState()
    c.setFillColor(fill_col)
    c.setStrokeColor(ring_col)
    c.setLineWidth(2)
    c.circle(cx, cy, r, fill=1, stroke=1)

    pct = f"{int(score * 100)}%"
    _set_fill(c, WHITE)
    c.setFont("Helvetica-Bold", 13)
    tw = c.stringWidth(pct, "Helvetica-Bold", 13)
    c.drawString(cx - tw / 2, cy - 5, pct)
    c.restoreState()


# ---------------------------------------------------------------------------
# Section: risk flags
# ---------------------------------------------------------------------------

def _draw_flags_section(c: Any, supplier: SupplierRecord, y: float) -> float:
    """Draw risk ring + flag pills side by side. Returns y below section."""
    score = float(supplier.get("risk_score") or 0.0)
    flags: list[str] = supplier.get("risk_flags") or []

    ring_cx = MARGIN_L + 30
    ring_cy = y - 36
    _draw_risk_ring(c, score, ring_cx, ring_cy, r=28)

    # Risk label
    if score >= 0.6:
        lvl, lc = "HIGH RISK",   (0.8, 0.1, 0.1)
    elif score >= 0.3:
        lvl, lc = "MEDIUM RISK", (0.75, 0.40, 0.0)
    else:
        lvl, lc = "LOW RISK",    (0.13, 0.53, 0.13)
    _draw_text(c, lvl, ring_cx - 22, ring_cy - 38,
               font="Helvetica-Bold", size=7, colour=lc)

    # Flags as coloured pills
    pill_x = MARGIN_L + 75
    pill_y = y - 16
    pill_h = 14.0
    for flag in flags:
        label = flag.replace("_", " ")
        c.setFont("Helvetica-Bold", 7)
        tw = c.stringWidth(label, "Helvetica-Bold", 7)
        pw = tw + 10
        if pill_x + pw > PAGE_W - MARGIN_R:
            pill_x = MARGIN_L + 75
            pill_y -= pill_h + 4
        _draw_rect(c, pill_x, pill_y - 2, pw, pill_h,
                   fill=flag_colour(flag), radius=3)
        _draw_text(c, label, pill_x + 5, pill_y + 2,
                   font="Helvetica-Bold", size=7, colour=WHITE)
        pill_x += pw + 6

    if not flags:
        _draw_text(c, "No risk flags", MARGIN_L + 75, y - 16,
                   font="Helvetica", size=9, colour=MID_GREY)

    y_bottom = min(ring_cy - 44, pill_y - 8)
    _set_stroke(c, LIGHT_GREY)
    c.setLineWidth(0.5)
    c.line(MARGIN_L, y_bottom, PAGE_W - MARGIN_R, y_bottom)
    return y_bottom - 8.0


# ---------------------------------------------------------------------------
# Section: 2-column table helper
# ---------------------------------------------------------------------------

def _draw_two_col_table(
    c: Any,
    title: str,
    rows: list[tuple[str, str]],
    y: float,
    col1_w: float = 140.0,
) -> float:
    """Draw a titled 2-column table. Returns y below table."""
    _draw_text(c, title, MARGIN_L, y,
               font="Helvetica-Bold", size=9, colour=ACCENT_BLUE)
    y -= 4

    row_h = 14.0
    for i, (k, v) in enumerate(rows):
        bg = LIGHT_GREY if i % 2 == 0 else WHITE
        _draw_rect(c, MARGIN_L, y - row_h + 2, CONTENT_W, row_h, fill=bg)
        _draw_text(c, k, MARGIN_L + 4, y - 9, font="Helvetica-Bold", size=8, colour=DARK_GREY)
        _draw_text(c, _truncate(str(v), 60), MARGIN_L + col1_w, y - 9,
                   font="Helvetica", size=8, colour=DARK_GREY)
        y -= row_h

    y -= 6
    _set_stroke(c, LIGHT_GREY)
    c.setLineWidth(0.5)
    c.line(MARGIN_L, y, PAGE_W - MARGIN_R, y)
    return y - 8.0


# ---------------------------------------------------------------------------
# Section: financial snapshot
# ---------------------------------------------------------------------------

def _fmt_revenue(eur: Any) -> str:
    if eur is None:
        return "—"
    val = int(eur)
    if val >= 1_000_000_000:
        return f"\u20ac{val / 1_000_000_000:.1f}B"
    if val >= 1_000_000:
        return f"\u20ac{val / 1_000_000:.0f}M"
    return f"\u20ac{val:,}"


def _draw_financial_snapshot(c: Any, supplier: SupplierRecord, y: float) -> float:
    rows = [
        ("Revenue (EUR)", _fmt_revenue(supplier.get("annual_revenue_eur"))),
        ("Employees",     f"{supplier.get('employee_count') or '—':,}" if supplier.get("employee_count") else "—"),
        ("Founded",       str(supplier.get("founded_year") or "—")),
        ("Headquarters",  supplier.get("headquarters") or "—"),
    ]
    return _draw_two_col_table(c, "Financial Snapshot", rows, y)


# ---------------------------------------------------------------------------
# Section: compliance grid
# ---------------------------------------------------------------------------

def _draw_compliance_grid(c: Any, supplier: SupplierRecord, y: float) -> float:
    certs: list[CertDict] = supplier.get("certificates") or []
    if not certs:
        rows = [("No certificates recorded", "")]
    else:
        rows = [(cert["name"], f"Valid until: {cert.get('valid_until', '?')}") for cert in certs]
    return _draw_two_col_table(c, "Compliance & Certificates", rows, y, col1_w=200.0)


# ---------------------------------------------------------------------------
# Section: evidence claims
# ---------------------------------------------------------------------------

def _draw_evidence(c: Any, supplier: SupplierRecord, y: float) -> float:
    evidence: list[EvidenceDict] = (supplier.get("evidence") or [])[:5]
    _draw_text(c, "Evidence Claims", MARGIN_L, y,
               font="Helvetica-Bold", size=9, colour=ACCENT_BLUE)
    y -= 4

    if not evidence:
        _draw_text(c, "No evidence claims recorded.", MARGIN_L + 4, y - 10,
                   font="Helvetica", size=8, colour=MID_GREY)
        return y - 22

    row_h = 26.0
    for i, ev in enumerate(evidence):
        bg = LIGHT_GREY if i % 2 == 0 else WHITE
        _draw_rect(c, MARGIN_L, y - row_h + 2, CONTENT_W, row_h, fill=bg)

        src = _truncate(ev.get("source_doc", ""), 50)
        _draw_text(c, src, MARGIN_L + 4, y - 8,
                   font="Helvetica-Bold", size=7, colour=DARK_GREY)

        excerpt = _truncate(ev.get("excerpt", ""), 120)
        _draw_text(c, excerpt, MARGIN_L + 4, y - 18,
                   font="Helvetica", size=7, colour=MID_GREY)

        # Confidence badge
        conf = float(ev.get("confidence") or 0.0)
        conf_label = f"{int(conf * 100)}%"
        badge_col = (0.13, 0.53, 0.13) if conf >= 0.75 else (0.75, 0.40, 0.0)
        _draw_rect(c, PAGE_W - MARGIN_R - 52, y - 22, 28, 12, fill=badge_col, radius=2)
        _draw_text(c, conf_label, PAGE_W - MARGIN_R - 47, y - 16,
                   font="Helvetica-Bold", size=7, colour=WHITE)

        # Reviewed tick / cross
        reviewed = ev.get("reviewed", False)
        tick_sym = "\u2713" if reviewed else "\u2717"
        tick_col = (0.13, 0.53, 0.13) if reviewed else (0.8, 0.1, 0.1)
        _draw_text(c, tick_sym, PAGE_W - MARGIN_R - 16, y - 14,
                   font="Helvetica-Bold", size=10, colour=tick_col)

        y -= row_h

    y -= 6
    _set_stroke(c, LIGHT_GREY)
    c.setLineWidth(0.5)
    c.line(MARGIN_L, y, PAGE_W - MARGIN_R, y)
    return y - 8.0


# ---------------------------------------------------------------------------
# Section: supply chain path
# ---------------------------------------------------------------------------

def _draw_chain_path(c: Any, supplier: SupplierRecord, y: float) -> float:
    chain: list[str] = supplier.get("upstream_chain") or [supplier["name"]]
    _draw_text(c, "Upstream Supply Chain Path", MARGIN_L, y,
               font="Helvetica-Bold", size=9, colour=ACCENT_BLUE)
    y -= 14

    chain_text = " \u2192 ".join(str(n) for n in chain if n)
    # Word-wrap at content width
    c.setFont("Helvetica", 8)
    max_w = CONTENT_W
    words = chain_text.split(" ")
    line = ""
    for word in words:
        test = (line + " " + word).strip()
        if c.stringWidth(test, "Helvetica", 8) <= max_w:
            line = test
        else:
            _draw_text(c, line, MARGIN_L + 4, y, font="Helvetica", size=8, colour=DARK_GREY)
            y -= 12
            line = word
    if line:
        _draw_text(c, line, MARGIN_L + 4, y, font="Helvetica", size=8, colour=DARK_GREY)
        y -= 12

    return y - 6.0


# ---------------------------------------------------------------------------
# Section: footer
# ---------------------------------------------------------------------------

def _draw_footer(c: Any) -> None:
    footer_text = (
        "Data source: SupplyLens / Neo4j  |  Confidence: DEMO  |  Not for redistribution"
    )
    _draw_rect(c, 0, 0, PAGE_W, 22, fill=DARK_BLUE)
    _draw_text(c, footer_text, MARGIN_L, 7,
               font="Helvetica", size=7, colour=(0.75, 0.75, 0.85))


# ---------------------------------------------------------------------------
# Main PDF builder
# ---------------------------------------------------------------------------

def generate_pdf(supplier: SupplierRecord, output_dir: str) -> str:
    """Generate a one-page PDF scorecard. Returns output file path."""
    from reportlab.pdfgen import canvas as rl_canvas  # type: ignore

    os.makedirs(output_dir, exist_ok=True)
    filename = slugify(supplier["name"]) + ".pdf"
    filepath = os.path.join(output_dir, filename)

    c = rl_canvas.Canvas(filepath, pagesize=(PAGE_W, PAGE_H))
    gen_date = datetime.date.today().isoformat()

    y = _draw_header(c, gen_date)
    y = _draw_hero(c, supplier, y)
    y = _draw_flags_section(c, supplier, y)
    y = _draw_financial_snapshot(c, supplier, y)
    y = _draw_compliance_grid(c, supplier, y)
    y = _draw_evidence(c, supplier, y)
    y = _draw_chain_path(c, supplier, y)
    _draw_footer(c)

    c.save()
    return filepath


# ---------------------------------------------------------------------------
# Data loading orchestration
# ---------------------------------------------------------------------------

def load_suppliers(
    supplier_name: str | None = None,
    product_sku: str | None = None,
) -> list[SupplierRecord]:
    """Return supplier list from Neo4j if available, else from DEMO_SUPPLIERS."""
    use_neo4j = neo4j_available()
    if use_neo4j:
        print("Neo4j available — loading from graph.", file=sys.stderr)
        if product_sku:
            records = load_product_chain_from_neo4j(product_sku)
        else:
            records = load_all_from_neo4j()
        if records:
            if supplier_name:
                records = [r for r in records if r["name"] == supplier_name]
            return records
        print("Neo4j returned no data — falling back to demo data.", file=sys.stderr)
    else:
        print("Neo4j unavailable — using embedded demo data.", file=sys.stderr)

    # Fallback: demo data
    if supplier_name:
        match = _DEMO_INDEX.get(supplier_name)
        return [match] if match else []
    if product_sku == "SCANIA-R-500":
        scania_t1 = ["ZF Friedrichshafen", "Bosch", "SSAB", "Michelin", "Dana Incorporated"]
        return [_DEMO_INDEX[n] for n in scania_t1 if n in _DEMO_INDEX]
    return list(DEMO_SUPPLIERS)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Generate per-supplier scorecard PDFs (UC4 SupplyLens)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--supplier",    default=None, help="Export one named supplier")
    p.add_argument("--product",     default=None, help="Export T1 chain for product SKU")
    p.add_argument("--dry-run",     action="store_true", help="Print list only; no PDF output")
    p.add_argument("--output-dir",  default=None, help="Output directory (default: output/scorecards/)")
    return p


def default_output_dir() -> str:
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(repo, "output", "scorecards")


def main() -> None:
    args = build_arg_parser().parse_args()

    output_dir = args.output_dir or default_output_dir()
    suppliers  = load_suppliers(
        supplier_name=args.supplier,
        product_sku=args.product,
    )

    if not suppliers:
        print("No suppliers found for given filters.", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print(f"Would generate {len(suppliers)} scorecard(s) in {output_dir}/:")
        for s in suppliers:
            fname = slugify(s["name"]) + ".pdf"
            score = float(s.get("risk_score") or 0.0)
            flags = ", ".join(s.get("risk_flags") or []) or "none"
            tier  = s.get("tier", "?")
            print(f"  {fname:<45}  score={score:.2f}  tier=T{tier}  flags=[{flags}]")
        sys.exit(0)

    os.makedirs(output_dir, exist_ok=True)
    generated: list[str] = []
    failed: list[str] = []

    for supplier in suppliers:
        try:
            path = generate_pdf(supplier, output_dir)
            generated.append(path)
            print(f"  OK  {path}")
        except Exception as exc:
            failed.append(supplier["name"])
            print(f"  FAIL  {supplier['name']}: {exc}", file=sys.stderr)

    print(f"\n{len(generated)} PDF(s) written to {output_dir}/")
    if failed:
        print(f"{len(failed)} failed: {', '.join(failed)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
