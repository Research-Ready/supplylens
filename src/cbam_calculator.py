"""CBAM Compliance Cost Calculator — UC4 Supply Chain

Carbon Border Adjustment Mechanism (EU CBAM, Reg 2023/956).
Sectors in scope (Phase 1 — 2026 full): steel, aluminium, cement, fertilisers,
electricity, hydrogen, and upstream precursors.

Usage:
    python3 src/cbam_calculator.py [--product SKU] [--all] [--json]
                                   [--carbon-price FLOAT] [--year INT]

Reads from Neo4j CT114 (or uses demo data if offline).
Writes CBAM liability back to Neo4j supplier nodes when --write-neo4j flag set.
"""

import json
import math
import os
import sys
import urllib.error
import urllib.request
import base64
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# ── Config ──────────────────────────────────────────────────────────────────
NEO4J_URL  = os.getenv("NEO4J_URL",  "http://10.0.1.114:7474")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "")

# EU ETS carbon price (EUR/tonne CO2) — 2024 average; override with --carbon-price
DEFAULT_CARBON_PRICE = 65.0

# CBAM sectors & product codes (CN code prefixes)
CBAM_SECTORS = {
    "steel":        {"cn_prefix": ["7206","7207","7208","7209","7210","7211","7212","7213","7214","7215","7216","7217","7218","7219","7220","7221","7222","7223","7224","7225","7226","7227","7228","7229","7301","7302","7303","7304","7305","7306"],
                     "default_co2_intensity": 1.9},  # tonne CO2 per tonne steel
    "aluminium":    {"cn_prefix": ["7601","7602","7603","7604","7605","7606","7607","7608","7609","7610","7611","7612","7613","7614","7616"],
                     "default_co2_intensity": 11.5},  # tonne CO2 per tonne Al (global avg)
    "cement":       {"cn_prefix": ["2523","6810","6811"],
                     "default_co2_intensity": 0.83},
    "fertilisers":  {"cn_prefix": ["2808","2814","2834","3102","3105"],
                     "default_co2_intensity": 2.2},
    "electricity":  {"cn_prefix": ["2716"],
                     "default_co2_intensity": 0.4},  # tonne CO2 per MWh
    "hydrogen":     {"cn_prefix": ["2804"],
                     "default_co2_intensity": 9.5},
    "chemicals":    {"cn_prefix": ["2825","2826"],  # NiO, cobalt compounds
                     "default_co2_intensity": 3.2},
    "battery_materials": {"cn_prefix": ["8507","2841","2846"],
                          "default_co2_intensity": 15.0},  # cathode materials (high)
}

# Supplier → sector mapping (demo / fallback)
SUPPLIER_SECTOR_MAP = {
    "Saarstahl AG":                ("steel",   850_000),   # (sector, volume_tonnes/yr)
    "Ovako AB":                    ("steel",   120_000),
    "SSAB":                        ("steel",   650_000),
    "TimkenSteel":                 ("steel",   180_000),
    "North Star BlueScope":        ("steel",   300_000),
    "Vale (iron ore)":             ("steel",   2_100_000),
    "Norilsk Nickel":              ("chemicals", 120_000),  # nickel sulfate
    "Umicore Battery Materials":   ("battery_materials", 45_000),
    "Shanshan Advanced Materials": ("battery_materials", 38_000),
    "Ganfeng Lithium":             ("battery_materials", 22_000),
    "Glencore (cobalt)":           ("battery_materials", 12_000),
    "Eramet":                      ("chemicals", 28_000),
}

# Countries with free ETS allowances (CBAM not applicable to imports from these)
ETS_EQUIVALENT_COUNTRIES = {"CH", "GB", "NO", "IS", "LI", "NZ"}

# Countries of concern — no carbon pricing → full CBAM
HIGH_CBAM_COUNTRIES = {"CN", "RU", "IN", "UA", "TR", "EG", "MA", "TN"}


def _neo4j_query(query: str, params: dict = None) -> List[dict]:
    if not NEO4J_PASS:
        return []
    auth = base64.b64encode(f"{NEO4J_USER}:{NEO4J_PASS}".encode()).decode()
    body = {"statements": [{"statement": query, "parameters": params or {}}]}
    req = urllib.request.Request(
        f"{NEO4J_URL}/db/neo4j/tx/commit",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Basic {auth}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read())
        if d.get("errors"):
            raise RuntimeError(d["errors"][0]["message"])
        rows = d["results"][0]["data"]
        cols = d["results"][0]["columns"]
        return [{cols[i]: row["row"][i] for i in range(len(cols))} for row in rows]
    except Exception as e:
        print(f"[Neo4j] offline or error: {e}", file=sys.stderr)
        return []


def _write_neo4j(name: str, cbam_eur: float, sector: str) -> None:
    q = """
    MATCH (s:Supplier {name: $name})
    SET s.cbam_liability_eur = $cbam_eur,
        s.cbam_sector = $sector,
        s.cbam_calculated_at = $ts
    """
    _neo4j_query(q, {"name": name, "cbam_eur": round(cbam_eur),
                     "sector": sector, "ts": datetime.utcnow().isoformat()})


def get_cbam_suppliers(sku: Optional[str] = None) -> List[dict]:
    """Fetch suppliers flagged with cbam_applicable from Neo4j."""
    if sku:
        q = """
        MATCH (p:Product {sku: $sku})-[:SUPPLIED_BY|SOURCED_FROM*1..5]->(s:Supplier)
        WHERE s.cbam_applicable = true OR s.cbam_risk = 'HIGH'
        RETURN s.name AS name, s.country AS country, s.tier AS tier,
               s.cbam_product AS cbam_product, s.cbam_risk AS cbam_risk,
               s.cbam_co2_intensity_kg_per_tonne AS co2_intensity,
               s.contract_value AS contract_value, s.volume_tonnes AS volume_tonnes
        """
        rows = _neo4j_query(q, {"sku": sku})
    else:
        q = """
        MATCH (s:Supplier)
        WHERE s.cbam_applicable = true OR s.cbam_risk = 'HIGH'
        RETURN s.name AS name, s.country AS country, s.tier AS tier,
               s.cbam_product AS cbam_product, s.cbam_risk AS cbam_risk,
               s.cbam_co2_intensity_kg_per_tonne AS co2_intensity,
               s.contract_value AS contract_value, s.volume_tonnes AS volume_tonnes
        """
        rows = _neo4j_query(q)
    return rows


def compute_cbam_liability(
    name: str,
    country: str,
    sector: str,
    volume_tonnes: float,
    co2_intensity_kg_per_tonne: float,
    carbon_price_eur_per_tonne: float = DEFAULT_CARBON_PRICE,
) -> dict:
    """Calculate CBAM liability for one supplier.

    CBAM liability = volume × CO2_intensity × carbon_price × (1 - free_allowance_ratio)

    Returns dict with all calculation steps.
    """
    if country in ETS_EQUIVALENT_COUNTRIES:
        return {
            "name": name, "country": country, "sector": sector,
            "volume_tonnes": volume_tonnes,
            "co2_intensity": co2_intensity_kg_per_tonne,
            "cbam_exempt": True,
            "reason": f"{country} has equivalent carbon pricing (ETS-linked)",
            "cbam_eur": 0.0,
            "cbam_certificates_needed": 0,
        }

    co2_tonne_per_tonne = co2_intensity_kg_per_tonne / 1000.0
    embedded_co2_tonnes  = volume_tonnes * co2_tonne_per_tonne

    # Free allowance phase-out: 2026=2.5%, 2027=0% (fully phased out)
    year = datetime.utcnow().year
    free_ratio = max(0.0, min(1.0, (2030 - year) * 0.025)) if year < 2030 else 0.0

    taxable_co2 = embedded_co2_tonnes * (1 - free_ratio)
    cbam_eur    = taxable_co2 * carbon_price_eur_per_tonne

    # Country-specific carbon price already paid (reduces CBAM)
    country_carbon_price = {
        "CN": 8.0, "RU": 0.0, "IN": 3.0, "TR": 12.0,
        "UA": 1.0, "EG": 0.0, "KR": 15.0, "JP": 5.0,
    }.get(country, 0.0)
    country_credit = embedded_co2_tonnes * country_carbon_price
    net_cbam = max(0.0, cbam_eur - country_credit)
    certificates = math.ceil(taxable_co2)

    return {
        "name":                    name,
        "country":                 country,
        "sector":                  sector,
        "volume_tonnes":           volume_tonnes,
        "co2_intensity_kg_t":      co2_intensity_kg_per_tonne,
        "embedded_co2_tonnes":     round(embedded_co2_tonnes, 1),
        "free_allowance_ratio":    round(free_ratio, 3),
        "taxable_co2_tonnes":      round(taxable_co2, 1),
        "carbon_price_eur_t":      carbon_price_eur_per_tonne,
        "country_credit_eur":      round(country_credit),
        "cbam_gross_eur":          round(cbam_eur),
        "cbam_net_eur":            round(net_cbam),
        "cbam_certificates_needed":certificates,
        "cbam_exempt":             False,
        "high_risk":               country in HIGH_CBAM_COUNTRIES,
    }


def run_full_assessment(
    sku: Optional[str] = None,
    carbon_price: float = DEFAULT_CARBON_PRICE,
    write_neo4j: bool = False,
) -> List[dict]:
    """Run CBAM assessment for all relevant suppliers."""
    results = []

    # Try Neo4j first
    neo4j_rows = get_cbam_suppliers(sku)

    if neo4j_rows:
        for row in neo4j_rows:
            name    = row["name"] or "Unknown"
            country = row["country"] or "XX"
            sector  = "steel"  # default
            for s, info in CBAM_SECTORS.items():
                if row.get("cbam_product") and any(
                    row["cbam_product"].lower() in p.lower() for p in [s]
                ):
                    sector = s
                    break
            co2_int = float(row.get("co2_intensity") or
                            CBAM_SECTORS.get(sector, {}).get("default_co2_intensity", 2.0) * 1000)
            # contract_value "€123M" → parse to float tonnes estimate
            vol = float(row.get("volume_tonnes") or
                        SUPPLIER_SECTOR_MAP.get(name, (None, 100_000))[1])
            result = compute_cbam_liability(name, country, sector, vol, co2_int, carbon_price)
            results.append(result)
    else:
        # Fallback: demo data
        for name, (sector, volume) in SUPPLIER_SECTOR_MAP.items():
            country = {
                "Saarstahl AG": "DE", "Ovako AB": "SE", "SSAB": "SE",
                "TimkenSteel": "US", "North Star BlueScope": "US",
                "Vale (iron ore)": "BR", "Norilsk Nickel": "RU",
                "Umicore Battery Materials": "BE",
                "Shanshan Advanced Materials": "CN",
                "Ganfeng Lithium": "CN", "Glencore (cobalt)": "CH",
                "Eramet": "FR",
            }.get(name, "XX")
            co2_int = CBAM_SECTORS[sector]["default_co2_intensity"] * 1000  # kg/tonne
            result = compute_cbam_liability(name, country, sector, volume, co2_int, carbon_price)
            results.append(result)
            if write_neo4j:
                _write_neo4j(name, result["cbam_net_eur"], sector)

    results.sort(key=lambda r: r.get("cbam_net_eur", 0), reverse=True)
    return results


def _fmt_eur(v: float) -> str:
    if v >= 1_000_000:
        return f"€{v/1_000_000:.1f}M"
    if v >= 1_000:
        return f"€{v/1_000:.0f}K"
    return f"€{v:.0f}"


def print_report(results: List[dict], carbon_price: float) -> None:
    total = sum(r.get("cbam_net_eur", 0) for r in results)
    exempt = [r for r in results if r.get("cbam_exempt")]
    liable = [r for r in results if not r.get("cbam_exempt")]

    W = 100
    print("=" * W)
    print(f"  CBAM COMPLIANCE REPORT — UC4 Supply Chain  |  Carbon price: €{carbon_price}/tCO2  |  {datetime.utcnow().strftime('%Y-%m-%d')}")
    print("=" * W)
    print(f"  Suppliers assessed: {len(results)}   |   CBAM-exempt: {len(exempt)}   |   Total annual liability: {_fmt_eur(total)}")
    print("-" * W)
    print(f"  {'Supplier':<32} {'Cty':>4} {'Sector':<16} {'Vol (t)':>10} {'CO2 (t)':>10} {'Certificates':>12} {'Net CBAM':>12} {'Risk'}")
    print("-" * W)

    for r in liable:
        flag = "CRITICAL" if r["country"] in {"RU"} else ("HIGH" if r.get("high_risk") else "")
        print(f"  {r['name']:<32} {r['country']:>4} {r['sector']:<16} "
              f"{r['volume_tonnes']:>10,.0f} {r['embedded_co2_tonnes']:>10,.0f} "
              f"{r['cbam_certificates_needed']:>12,} {_fmt_eur(r['cbam_net_eur']):>12} "
              f"{'[' + flag + ']' if flag else ''}")

    if exempt:
        print()
        print("  ETS-EQUIVALENT (CBAM exempt):")
        for r in exempt:
            print(f"  {r['name']:<32} {r['country']:>4} — {r['reason']}")

    print("=" * W)
    print(f"  TOTAL ANNUAL CBAM COST: {_fmt_eur(total)}")

    # Breakdown by sector
    sector_totals: dict[str, float] = {}
    for r in liable:
        sector_totals[r["sector"]] = sector_totals.get(r["sector"], 0) + r.get("cbam_net_eur", 0)
    print()
    print("  Breakdown by sector:")
    for s, t in sorted(sector_totals.items(), key=lambda x: x[1], reverse=True):
        print(f"    {s:<20} {_fmt_eur(t):>12}  ({t/total*100:.1f}% of total)" if total else f"    {s}")

    # Top risk: Norilsk Nickel sanctions + CBAM
    ru_suppliers = [r for r in liable if r["country"] == "RU"]
    if ru_suppliers:
        print()
        print("  SANCTIONS + CBAM WARNING:")
        for r in ru_suppliers:
            print(f"    {r['name']}: {_fmt_eur(r['cbam_net_eur'])} CBAM + potential sanctions freeze → immediate alt-sourcing required")

    print("=" * W)


def main():
    parser = argparse.ArgumentParser(description="CBAM liability calculator")
    parser.add_argument("--product",       default=None,                   help="Product SKU to filter")
    parser.add_argument("--all",           action="store_true",             help="All CBAM-applicable suppliers")
    parser.add_argument("--carbon-price",  type=float, default=DEFAULT_CARBON_PRICE)
    parser.add_argument("--json",          action="store_true",             help="JSON output")
    parser.add_argument("--write-neo4j",   action="store_true",             help="Write liability back to Neo4j")
    args = parser.parse_args()

    sku = args.product
    results = run_full_assessment(sku, args.carbon_price, args.write_neo4j)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_report(results, args.carbon_price)

    total = sum(r.get("cbam_net_eur", 0) for r in results)
    if total > 5_000_000:
        sys.exit(2)   # exit 2 = significant exposure (for CI alerting)


if __name__ == "__main__":
    main()
