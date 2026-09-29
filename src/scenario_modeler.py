"""Supply Chain Scenario Stress-Tester — UC4 Supply Chain

Models the financial and operational impact of supply chain disruption scenarios.
Each scenario = a supplier or region failing / being sanctioned / export-controlled.

Usage:
    python3 src/scenario_modeler.py [--scenario SCENARIO_ID] [--all] [--json]
                                    [--product SKU] [--revenue FLOAT]

Scenarios:
    CATL_DEFAULT         CATL stops BEV battery deliveries (fire, insolvency, sanctions)
    XINJIANG_BAN         Full US/EU UFLPA ban on Xinjiang-origin goods
    NORILSK_FULL_SANC    Norilsk Nickel full secondary sanctions — class I nickel cut off
    RUSSIA_SUPPLY_HALT   Full Russia supply halt (invasion expansion, secondary sanctions)
    CHINA_EXPORT_CTRL    China export controls on rare earths + battery materials
    SSAB_STRIKE          SSAB strike — Scania high-strength steel supply disruption
    TASMAN_QUAKE         Hypothetical — Atacama/Chile earthquake, lithium brine disrupted
"""

import json
import os
import sys
import base64
import urllib.request
import argparse
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta


# ── Config ──────────────────────────────────────────────────────────────────
NEO4J_URL  = os.getenv("NEO4J_URL",  "http://localhost:7474")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "")

# Scania annual revenue (2023: ~SEK 223bn ≈ €19.5bn)
SCANIA_ANNUAL_REVENUE_EUR = 19_500_000_000

# Production days per year
PROD_DAYS = 250

# Daily revenue ≈ annual / prod days
DAILY_REV = SCANIA_ANNUAL_REVENUE_EUR / PROD_DAYS


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
        print(f"[Neo4j] offline: {e}", file=sys.stderr)
        return []


# ── Scenario definitions ─────────────────────────────────────────────────────

SCENARIOS = {
    "CATL_DEFAULT": {
        "id":          "CATL_DEFAULT",
        "name":        "CATL Supply Failure",
        "description": "CATL stops BEV battery deliveries — factory fire, insolvency, or EU sanctions",
        "trigger":     "Supplier failure: CATL (CN, T1)",
        "affected_suppliers": ["CATL"],
        "affected_products":  ["SCANIA-L-340-BEV"],
        # Financial impact parameters
        "production_halt_days":    {"best": 30, "base": 90, "worst": 180},
        "contract_value_eur":      820_000_000,
        "inventory_buffer_days":   14,
        "alternative_cost_premium": 0.35,  # alts cost 35% more (Samsung SDI, LG, Northvolt)
        "qualification_days":       {"best": 60, "base": 120, "worst": 240},
        "cbam_change_eur":          0,      # no CBAM for batteries (yet)
        "legal_exposure_eur":       50_000_000,  # contract penalties
        "reputation_risk":          "HIGH",
        "alternatives": [
            {"name": "Samsung SDI",       "country": "KR", "capacity_pct": 0.60, "lead_wks": 24},
            {"name": "LG Energy Solution","country": "KR", "capacity_pct": 0.80, "lead_wks": 28},
            {"name": "Northvolt",         "country": "SE", "capacity_pct": 0.30, "lead_wks": 52},
        ],
    },
    "XINJIANG_BAN": {
        "id":          "XINJIANG_BAN",
        "name":        "Full UFLPA Xinjiang Import Ban",
        "description": "EU adopts UFLPA-equivalent; full ban on Xinjiang-origin goods",
        "trigger":     "Regulatory: UFLPA expansion to EU",
        "affected_suppliers": ["Shanshan Advanced Materials", "Ganfeng Lithium", "CATL"],
        "affected_products":  ["SCANIA-L-340-BEV"],
        "production_halt_days":    {"best": 45, "base": 120, "worst": 300},
        "contract_value_eur":      920_000_000,   # CATL + Shanshan + Ganfeng
        "inventory_buffer_days":   10,
        "alternative_cost_premium": 0.28,
        "qualification_days":       {"best": 90, "base": 180, "worst": 360},
        "cbam_change_eur":          -15_000_000,  # Xinjiang coal-heavy → replacement reduces CBAM
        "legal_exposure_eur":       120_000_000,
        "reputation_risk":          "CRITICAL",
        "alternatives": [
            {"name": "BASF Battery Materials","country": "DE", "capacity_pct": 0.40, "lead_wks": 16},
            {"name": "Umicore BM",            "country": "BE", "capacity_pct": 0.50, "lead_wks": 12},
            {"name": "Albemarle",             "country": "US", "capacity_pct": 0.35, "lead_wks": 20},
        ],
    },
    "NORILSK_FULL_SANC": {
        "id":          "NORILSK_FULL_SANC",
        "name":        "Norilsk Nickel Full Secondary Sanctions",
        "description": "US/EU secondary sanctions freeze Norilsk Nickel — class I nickel supply cut",
        "trigger":     "Sanctions: OFAC secondary sanctions on Norilsk",
        "affected_suppliers": ["Norilsk Nickel"],
        "affected_products":  ["SCANIA-L-340-BEV"],
        "production_halt_days":    {"best": 20, "base": 60, "worst": 150},
        "contract_value_eur":      95_000_000,
        "inventory_buffer_days":   21,
        "alternative_cost_premium": 0.22,
        "qualification_days":       {"best": 30, "base": 90, "worst": 180},
        "cbam_change_eur":          22_500_000,   # Norilsk CBAM saved → replaced by Western nickel
        "legal_exposure_eur":       200_000_000,  # sanctions compliance breach fines
        "reputation_risk":          "CRITICAL",
        "alternatives": [
            {"name": "BHP Nickel West",  "country": "AU", "capacity_pct": 0.70, "lead_wks": 8},
            {"name": "Vale (nickel)",    "country": "BR", "capacity_pct": 0.60, "lead_wks": 10},
            {"name": "Wyloo Metals",     "country": "AU", "capacity_pct": 0.30, "lead_wks": 14},
        ],
    },
    "RUSSIA_SUPPLY_HALT": {
        "id":          "RUSSIA_SUPPLY_HALT",
        "name":        "Full Russia Supply Halt",
        "description": "Escalating sanctions halt all Russian-origin materials (nickel, palladium, steel)",
        "trigger":     "Geopolitical: Russia-origin supply cut (secondary sanctions)",
        "affected_suppliers": ["Norilsk Nickel", "Severstal (steel slab)"],
        "affected_products":  ["SCANIA-R-500", "SCANIA-L-340-BEV", "SCANIA-G-410"],
        "production_halt_days":    {"best": 14, "base": 45, "worst": 120},
        "contract_value_eur":      180_000_000,
        "inventory_buffer_days":   30,
        "alternative_cost_premium": 0.18,
        "qualification_days":       {"best": 30, "base": 60, "worst": 120},
        "cbam_change_eur":          22_500_000,
        "legal_exposure_eur":       350_000_000,
        "reputation_risk":          "HIGH",
        "alternatives": [
            {"name": "SSAB (extra capacity)",  "country": "SE", "capacity_pct": 0.80, "lead_wks": 4},
            {"name": "BHP Nickel West",        "country": "AU", "capacity_pct": 0.70, "lead_wks": 8},
        ],
    },
    "CHINA_EXPORT_CTRL": {
        "id":          "CHINA_EXPORT_CTRL",
        "name":        "China Rare Earth & Battery Export Controls",
        "description": "China imposes export controls on rare earths, graphite, and battery materials",
        "trigger":     "Regulatory: PRC MoC export licence requirement",
        "affected_suppliers": ["CATL", "Ganfeng Lithium", "Shanshan Advanced Materials", "Proterial Ltd"],
        "affected_products":  ["SCANIA-L-340-BEV"],
        "production_halt_days":    {"best": 60, "base": 150, "worst": 365},
        "contract_value_eur":      980_000_000,
        "inventory_buffer_days":   7,
        "alternative_cost_premium": 0.45,   # rare earths hard to substitute quickly
        "qualification_days":       {"best": 180, "base": 360, "worst": 720},
        "cbam_change_eur":          -20_000_000,
        "legal_exposure_eur":       80_000_000,
        "reputation_risk":          "CRITICAL",
        "alternatives": [
            {"name": "MP Materials",     "country": "US", "capacity_pct": 0.15, "lead_wks": 52},
            {"name": "Lynas Rare Earths","country": "AU", "capacity_pct": 0.20, "lead_wks": 40},
            {"name": "Northvolt (Li)",   "country": "SE", "capacity_pct": 0.25, "lead_wks": 52},
        ],
    },
    "SSAB_STRIKE": {
        "id":          "SSAB_STRIKE",
        "name":        "SSAB Industrial Strike",
        "description": "SSAB Sweden strike — high-strength steel (chassis, cab) supply disruption",
        "trigger":     "Industrial action: Swedish Metalworkers Union (IF Metall)",
        "affected_suppliers": ["SSAB"],
        "affected_products":  ["SCANIA-R-500", "SCANIA-G-410"],
        "production_halt_days":    {"best": 7, "base": 21, "worst": 60},
        "contract_value_eur":      35_000_000,
        "inventory_buffer_days":   14,
        "alternative_cost_premium": 0.12,
        "qualification_days":       {"best": 0, "base": 7, "worst": 30},
        "cbam_change_eur":          0,
        "legal_exposure_eur":       5_000_000,
        "reputation_risk":          "MEDIUM",
        "alternatives": [
            {"name": "ArcelorMittal",   "country": "LU", "capacity_pct": 0.90, "lead_wks": 2},
            {"name": "Salzgitter",      "country": "DE", "capacity_pct": 0.70, "lead_wks": 3},
            {"name": "ThyssenKrupp",    "country": "DE", "capacity_pct": 0.80, "lead_wks": 2},
        ],
    },
    "ATACAMA_QUAKE": {
        "id":          "ATACAMA_QUAKE",
        "name":        "Atacama Desert Earthquake — Lithium Brine Disruption",
        "description": "7.8M earthquake damages SQM / Albemarle lithium extraction facilities",
        "trigger":     "Natural disaster: Atacama, Chile",
        "affected_suppliers": ["SQM", "Albemarle", "Lithium Brine (Atacama)"],
        "affected_products":  ["SCANIA-L-340-BEV"],
        "production_halt_days":    {"best": 30, "base": 90, "worst": 180},
        "contract_value_eur":      65_000_000,
        "inventory_buffer_days":   21,
        "alternative_cost_premium": 0.30,
        "qualification_days":       {"best": 14, "base": 45, "worst": 90},
        "cbam_change_eur":          0,
        "legal_exposure_eur":       10_000_000,
        "reputation_risk":          "LOW",
        "alternatives": [
            {"name": "Ganfeng Lithium",   "country": "CN", "capacity_pct": 0.60, "lead_wks": 6},
            {"name": "Livent",            "country": "US", "capacity_pct": 0.40, "lead_wks": 8},
            {"name": "Piedmont Lithium",  "country": "US", "capacity_pct": 0.25, "lead_wks": 16},
        ],
    },
}


def _compute_revenue_at_risk(scenario: dict, annual_rev: float = SCANIA_ANNUAL_REVENUE_EUR) -> dict:
    """Compute revenue-at-risk for a scenario across best/base/worst cases."""
    prod_days = PROD_DAYS
    daily_rev = annual_rev / prod_days
    buf = scenario["inventory_buffer_days"]
    alt_premium = scenario["alternative_cost_premium"]
    contract_v = scenario["contract_value_eur"]

    results = {}
    for case in ["best", "base", "worst"]:
        halt = scenario["production_halt_days"][case]
        # Effective halt after buffer exhausted
        effective_halt = max(0, halt - buf)
        rev_at_risk = effective_halt * daily_rev

        # Alternative sourcing premium during transition
        qual_days = scenario["qualification_days"][case]
        alt_cost_extra = contract_v * alt_premium * (qual_days / 365)

        # CBAM savings (if switch to Western suppliers reduces CBAM)
        cbam_change = scenario.get("cbam_change_eur", 0)

        total_impact = rev_at_risk + alt_cost_extra + scenario["legal_exposure_eur"] - max(0, cbam_change)

        results[case] = {
            "halt_days":          halt,
            "effective_halt_days": effective_halt,
            "revenue_at_risk_eur": round(rev_at_risk),
            "alt_transition_cost": round(alt_cost_extra),
            "legal_exposure_eur":  scenario["legal_exposure_eur"],
            "cbam_change_eur":     cbam_change,
            "total_impact_eur":    round(total_impact),
            "daily_rev_eur":       round(daily_rev),
        }
    return results


def run_scenario(sid: str, annual_rev: float = SCANIA_ANNUAL_REVENUE_EUR) -> dict:
    scenario = SCENARIOS.get(sid)
    if not scenario:
        raise ValueError(f"Unknown scenario: {sid}. Available: {list(SCENARIOS.keys())}")

    impacts = _compute_revenue_at_risk(scenario, annual_rev)
    base = impacts["base"]
    worst = impacts["worst"]

    # Best alternative coverage (best alt by capacity %)
    alts = scenario.get("alternatives", [])
    best_alt = max(alts, key=lambda a: a["capacity_pct"]) if alts else None

    # Time to recovery
    qual_base = scenario["qualification_days"]["base"]
    recovery_date = (datetime.utcnow() + timedelta(days=qual_base)).strftime("%Y-%m")

    return {
        "scenario_id":       sid,
        "scenario_name":     scenario["name"],
        "description":       scenario["description"],
        "trigger":           scenario["trigger"],
        "affected_suppliers": scenario["affected_suppliers"],
        "affected_products":  scenario["affected_products"],
        "reputation_risk":   scenario["reputation_risk"],
        "contract_value_eur": scenario["contract_value_eur"],
        "impacts":            impacts,
        "base_impact_eur":    base["total_impact_eur"],
        "worst_impact_eur":   worst["total_impact_eur"],
        "best_alt":           best_alt,
        "alternatives":       alts,
        "recovery_target":    recovery_date,
        "cbam_change_eur":    scenario.get("cbam_change_eur", 0),
        "assessed_at":        datetime.utcnow().isoformat(),
    }


def run_all(annual_rev: float = SCANIA_ANNUAL_REVENUE_EUR,
            product_filter: Optional[str] = None) -> List[dict]:
    results = []
    for sid, sc in SCENARIOS.items():
        if product_filter and product_filter not in sc["affected_products"]:
            continue
        results.append(run_scenario(sid, annual_rev))
    results.sort(key=lambda r: r["worst_impact_eur"], reverse=True)
    return results


def _fmt(v: float) -> str:
    if abs(v) >= 1e9:  return f"€{v/1e9:.2f}B"
    if abs(v) >= 1e6:  return f"€{v/1e6:.1f}M"
    if abs(v) >= 1e3:  return f"€{v/1e3:.0f}K"
    return f"€{v:.0f}"


def print_report(results: List[dict]) -> None:
    W = 115
    print("=" * W)
    print(f"  SUPPLY CHAIN SCENARIO STRESS TEST — UC4 Scania  |  {datetime.utcnow().strftime('%Y-%m-%d')}")
    print("=" * W)

    total_worst = sum(r["worst_impact_eur"] for r in results)
    print(f"  Scenarios: {len(results)}   |   Combined worst-case exposure: {_fmt(total_worst)}")
    print()
    print(f"  {'Scenario':<32} {'Suppliers':<28} {'Base':>10} {'Worst':>12} {'Recovery':<12} {'Rep.'}")
    print("-" * W)

    for r in results:
        sups = ", ".join(r["affected_suppliers"][:2])
        if len(r["affected_suppliers"]) > 2:
            sups += f" +{len(r['affected_suppliers'])-2}"
        rr = r["reputation_risk"]
        rr_str = {"CRITICAL":"***CRITICAL***", "HIGH":"**HIGH**", "MEDIUM":"*MED*", "LOW":"low"}.get(rr, rr)
        print(f"  {r['scenario_name']:<32} {sups:<28} {_fmt(r['base_impact_eur']):>10} {_fmt(r['worst_impact_eur']):>12} {r['recovery_target']:<12} {rr_str}")

    print()
    print("  TOP 3 SCENARIOS — DETAIL:")
    for r in results[:3]:
        print()
        print(f"  ┌─ {r['scenario_name']} ({'|'.join(r['affected_products'])})")
        print(f"  │  Trigger: {r['trigger']}")
        print(f"  │  Affected: {', '.join(r['affected_suppliers'])}")
        print()
        for case in ["best", "base", "worst"]:
            imp = r["impacts"][case]
            print(f"  │  [{case.upper():5}] halt={imp['halt_days']}d  rev@risk={_fmt(imp['revenue_at_risk_eur'])}  "
                  f"alt_cost={_fmt(imp['alt_transition_cost'])}  legal={_fmt(imp['legal_exposure_eur'])}  "
                  f"TOTAL={_fmt(imp['total_impact_eur'])}")
        if r["cbam_change_eur"]:
            sign = "+" if r["cbam_change_eur"] > 0 else ""
            print(f"  │  CBAM change on switch: {sign}{_fmt(r['cbam_change_eur'])}")
        if r["best_alt"]:
            b = r["best_alt"]
            print(f"  │  Best alt: {b['name']} ({b['country']}, {b['capacity_pct']*100:.0f}% cap, {b['lead_wks']}wk lead)")
        print(f"  └─ Recovery target: {r['recovery_target']}")

    print()
    print("  RECOMMENDATIONS:")
    critical = [r for r in results if r["reputation_risk"] == "CRITICAL"]
    for r in critical:
        print(f"   ! {r['scenario_name']}: Begin alternative qualification NOW (worst case: {_fmt(r['worst_impact_eur'])})")
    print("=" * W)


def main():
    parser = argparse.ArgumentParser(description="Supply chain scenario stress-tester")
    parser.add_argument("--scenario", default=None, choices=list(SCENARIOS.keys()), help="Single scenario")
    parser.add_argument("--all",      action="store_true", help="Run all scenarios")
    parser.add_argument("--product",  default=None, help="Filter by product SKU")
    parser.add_argument("--revenue",  type=float, default=SCANIA_ANNUAL_REVENUE_EUR,
                        help="Annual revenue EUR (default: Scania 2023)")
    parser.add_argument("--json",     action="store_true")
    parser.add_argument("--list",     action="store_true", help="List scenario IDs")
    args = parser.parse_args()

    if args.list:
        for sid, sc in SCENARIOS.items():
            print(f"  {sid:<30} {sc['name']}")
        return

    if args.scenario:
        results = [run_scenario(args.scenario, args.revenue)]
    else:
        results = run_all(args.revenue, args.product)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_report(results)

    # CI: exit 2 if any scenario worst-case > €500M
    over_threshold = [r for r in results if r["worst_impact_eur"] > 500_000_000]
    if over_threshold:
        sys.exit(2)


if __name__ == "__main__":
    main()
