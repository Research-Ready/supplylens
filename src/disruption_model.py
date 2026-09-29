"""UC4 Supply Chain Disruption Model

Given one or more disrupted suppliers, compute:
  - Which products are affected (reverse graph traversal)
  - Revenue at risk (EUR) based on product revenue data
  - Alternative suppliers available at same tier
  - Cascade risk: secondary suppliers knocked out if T1 has no other T2 source
  - Recovery time estimate (days)

Usage:
    python3 src/disruption_model.py "Infineon Technologies"
    python3 src/disruption_model.py "China Rare Earth Group" "Xinjiang Polysilicon Co"
    python3 src/disruption_model.py --scenario china-sanctions
    python3 src/disruption_model.py --scenario single-source-gearbox
    python3 src/disruption_model.py --list-scenarios
    python3 src/disruption_model.py --list-high-risk
    python3 src/disruption_model.py --dry-run "Vale SA"
"""

import json
import os
import sys
import argparse
import logging
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from neo4j_client import Neo4jClient

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

NEO4J_URL  = os.getenv("NEO4J_URL",      "http://localhost:7474")
NEO4J_USER = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "")

# ─── Predefined disruption scenarios ─────────────────────────────────────────

SCENARIOS: dict[str, dict] = {
    "china-sanctions": {
        "description": "China export controls on rare earths and semiconductors",
        "disrupted": ["China Rare Earth Group", "Xinjiang Polysilicon Co", "Shenzhen Metal Co"],
        "severity": "CRITICAL",
        "recovery_days": 365,
        "notes": "2023 gallium/germanium precedent — full ban escalation scenario",
    },
    "russia-gas": {
        "description": "Russian gas cutoff — BASF Ludwigshafen chemical synthesis halted",
        "disrupted": ["BASF SE"],
        "severity": "HIGH",
        "recovery_days": 180,
        "notes": "BASF Verbund site consumes ~4% of German gas; polymer/ABS output halted",
    },
    "drc-conflict": {
        "description": "DRC conflict escalation — tantalum/cobalt supply blocked",
        "disrupted": ["AVX Tantalum", "Umicore SA"],
        "severity": "HIGH",
        "recovery_days": 90,
        "notes": "Dodd-Frank 1502 triggers; alternative certified smelters limited",
    },
    "vale-disaster": {
        "description": "Vale tailings dam collapse — Brazilian iron ore supply halted",
        "disrupted": ["Vale SA"],
        "severity": "HIGH",
        "recovery_days": 120,
        "notes": "Brumadinho 2019 precedent; 11Mt/year iron ore to EU steelmakers at risk",
    },
    "single-source-gearbox": {
        "description": "ZF Friedrichshafen strike — SINGLE_SOURCE gearbox unavailable",
        "disrupted": ["ZF Friedrichshafen"],
        "severity": "CRITICAL",
        "recovery_days": 45,
        "notes": "TraXon automated gearbox: no qualified alternative for Scania R-500",
    },
    "xinjiang-sanctions": {
        "description": "US UFLPA enforcement — Xinjiang-origin polysilicon banned",
        "disrupted": ["Xinjiang Polysilicon Co"],
        "severity": "HIGH",
        "recovery_days": 270,
        "notes": "Uyghur Forced Labor Prevention Act; silicon wafer supply chain affected",
    },
    "glencore-sanctions": {
        "description": "Glencore sanctioned — cobalt and copper supply disrupted",
        "disrupted": ["Glencore"],
        "severity": "HIGH",
        "recovery_days": 60,
    },
    "norsk-hydro-strike": {
        "description": "Norsk Hydro aluminium workers strike — GKN Automotive affected",
        "disrupted": ["Norsk Hydro"],
        "severity": "MEDIUM",
        "recovery_days": 21,
    },
    "kiruna-landslide": {
        "description": "Kiruna mine landslide — LKAB iron ore production halted",
        "disrupted": ["LKAB Kiruna Mine", "LKAB Kiirunavaara Shaft"],
        "severity": "HIGH",
        "recovery_days": 90,
        "notes": "SSAB loses primary iron ore input; chassis steel supply threatened",
    },
}

# ─── Product revenue data ─────────────────────────────────────────────────────
# Realistic estimates for Scania AB revenue exposure per product line

PRODUCT_REVENUE: dict[str, dict] = {
    "SCANIA-R-500":   {"annual_eur": 13_500_000_000, "unit_eur": 150_000, "daily_units": 246},
    "SCANIA-T-500":   {"annual_eur":  2_000_000_000, "unit_eur": 140_000, "daily_units":  39},
    "SCANIA-BUS-K":   {"annual_eur":  1_500_000_000, "unit_eur": 300_000, "daily_units":  14},
    "SCANIA-ENG-DC13":{"annual_eur":    800_000_000, "unit_eur":  25_000, "daily_units":  87},
    "BTN-001":        {"annual_eur":      5_000_000, "unit_eur":    0.15, "daily_units": 91324},
}

# Default recovery multiplier by tier: deeper = slower to substitute
TIER_RECOVERY_DAYS: dict[int, int] = {1: 45, 2: 90, 3: 180, 4: 270}


# ─── Credential loading ───────────────────────────────────────────────────────

def _load_password() -> str:
    if NEO4J_PASS:
        return NEO4J_PASS
    try:
        from pykeepass import PyKeePass
        kp_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "passwords.kdbx")
        if os.path.exists(kp_path):
            kp = PyKeePass(kp_path, password="SupplyChainBaby100!")
            entry = kp.find_entries(title="Neo4j", first=True)
            if entry:
                return entry.password
    except Exception:
        pass
    return input("Neo4j password: ").strip()


# ─── Core graph queries ───────────────────────────────────────────────────────

def get_affected_products(db: Neo4jClient, disrupted_names: list[str]) -> list[dict]:
    """Reverse-traverse from disrupted suppliers to find impacted products."""
    query = """
    UNWIND $names AS dname
    MATCH (disrupted {name: dname})
    MATCH path = (product:Product)-[:SUPPLIED_BY|SOURCED_FROM*1..6]->(disrupted)
    WITH product, disrupted, length(path) AS depth
    ORDER BY product.sku, depth
    RETURN DISTINCT
        product.sku        AS sku,
        product.name       AS product_name,
        collect(DISTINCT disrupted.name) AS via_suppliers,
        min(depth)         AS min_depth
    """
    rows = db.query(query, {"names": disrupted_names})
    return rows


def get_dependent_suppliers(db: Neo4jClient, disrupted_names: list[str]) -> list[dict]:
    """Find T1/T2 suppliers that depend on the disrupted node(s)."""
    query = """
    UNWIND $names AS dname
    MATCH (disrupted {name: dname})
    MATCH (dep:Supplier)-[:SOURCED_FROM*1..4]->(disrupted)
    RETURN DISTINCT
        dep.name    AS name,
        dep.country AS country,
        dep.tier    AS tier,
        disrupted.name AS depends_on
    ORDER BY dep.tier, dep.name
    """
    return db.query(query, {"names": disrupted_names})


def get_disrupted_node_info(db: Neo4jClient, names: list[str]) -> list[dict]:
    """Fetch node metadata for the disrupted suppliers."""
    query = """
    UNWIND $names AS n
    MATCH (s {name: n})
    RETURN s.name AS name, s.country AS country, s.tier AS tier,
           s.risk_flags AS risk_flags,
           labels(s) AS labels
    """
    return db.query(query, {"names": names})


def get_alternative_suppliers(db: Neo4jClient, disrupted_names: list[str]) -> list[dict]:
    """Find suppliers at the same tier that could substitute, excluding disrupted ones."""
    query = """
    UNWIND $names AS dname
    MATCH (disrupted:Supplier {name: dname})
    // Find what the disrupted supplier provides upstream
    MATCH (customer:Supplier)-[rel:SOURCED_FROM]->(disrupted)
    // Find alternatives at same tier, not disrupted, not same country (for geo diversity)
    MATCH (alt:Supplier)
    WHERE alt.tier = disrupted.tier
      AND NOT alt.name IN $names
      AND alt.country <> disrupted.country
    RETURN DISTINCT
        disrupted.name  AS disrupted,
        disrupted.tier  AS tier,
        alt.name        AS alternative,
        alt.country     AS alt_country,
        alt.risk_flags  AS alt_risk_flags
    ORDER BY disrupted.name, alt.name
    LIMIT 20
    """
    return db.query(query, {"names": disrupted_names})


def get_single_source_cascade(db: Neo4jClient, disrupted_names: list[str]) -> list[dict]:
    """Find suppliers where the disrupted node is their ONLY source — cascade risk."""
    query = """
    UNWIND $names AS dname
    MATCH (disrupted {name: dname})
    MATCH (customer:Supplier)-[:SOURCED_FROM]->(disrupted)
    // Check if customer has any other sources
    WITH customer, disrupted,
         COUNT { (customer)-[:SOURCED_FROM]->(other) WHERE other.name <> dname } AS other_sources
    WHERE other_sources = 0
    RETURN customer.name AS supplier, customer.tier AS tier,
           disrupted.name AS sole_source,
           'SINGLE_SOURCE_CASCADE' AS cascade_type
    ORDER BY customer.tier, customer.name
    """
    return db.query(query, {"names": disrupted_names})


# ─── Impact calculation ───────────────────────────────────────────────────────

def calc_revenue_at_risk(
    affected_products: list[dict],
    recovery_days: int,
) -> dict:
    """Compute revenue at risk over the recovery period."""
    total_eur = 0
    breakdown: list[dict] = []

    for row in affected_products:
        sku = row.get("sku", "")
        rev = PRODUCT_REVENUE.get(sku, {})
        if not rev:
            breakdown.append({"sku": sku, "eur_at_risk": None, "note": "no revenue data"})
            continue
        daily_revenue = rev["annual_eur"] / 365
        eur_at_risk = daily_revenue * recovery_days
        total_eur += eur_at_risk
        breakdown.append({
            "sku": sku,
            "name": row.get("product_name", sku),
            "daily_revenue_eur": round(daily_revenue),
            "recovery_days": recovery_days,
            "eur_at_risk": round(eur_at_risk),
        })

    return {"total_eur": round(total_eur), "breakdown": breakdown}


def severity_from_score(score: float) -> str:
    if score >= 0.8: return "CRITICAL"
    if score >= 0.6: return "HIGH"
    if score >= 0.35: return "MEDIUM"
    return "LOW"


# ─── Report builder ───────────────────────────────────────────────────────────

def build_report(
    disrupted_names: list[str],
    scenario_meta: dict | None,
    node_info: list[dict],
    affected_products: list[dict],
    dependent_suppliers: list[dict],
    alternatives: list[dict],
    cascade: list[dict],
    recovery_days: int,
    dry_run: bool,
) -> dict:
    revenue = calc_revenue_at_risk(affected_products, recovery_days)
    severity = scenario_meta.get("severity", "HIGH") if scenario_meta else \
               severity_from_score(min(1.0, revenue["total_eur"] / 1e10))

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scenario": scenario_meta.get("description") if scenario_meta else "Custom disruption",
        "disrupted_suppliers": disrupted_names,
        "disrupted_details": node_info,
        "severity": severity,
        "recovery_estimate_days": recovery_days,
        "affected_products_count": len(affected_products),
        "affected_products": affected_products,
        "dependent_suppliers_affected": dependent_suppliers,
        "cascade_risks": cascade,
        "alternative_suppliers": alternatives,
        "revenue_at_risk": revenue,
        "notes": scenario_meta.get("notes", "") if scenario_meta else "",
    }
    return report


def print_report(report: dict) -> None:
    W = "\033[0m"; R = "\033[91m"; Y = "\033[93m"; G = "\033[92m"; B = "\033[94m"; BOLD = "\033[1m"

    sev = report["severity"]
    sev_color = R if sev == "CRITICAL" else Y if sev == "HIGH" else G
    eur = report["revenue_at_risk"]["total_eur"]

    print(f"\n{BOLD}{'═'*64}{W}")
    print(f"{BOLD}  UC4 Disruption Impact Analysis{W}")
    print(f"{'═'*64}")
    print(f"  Scenario   : {report['scenario']}")
    print(f"  Disrupted  : {', '.join(report['disrupted_suppliers'])}")
    print(f"  Severity   : {sev_color}{BOLD}{sev}{W}")
    print(f"  Recovery   : {report['recovery_estimate_days']} days")
    print(f"  Revenue risk: {R}{BOLD}€{eur:,.0f}{W}")
    if report["notes"]:
        print(f"  Notes      : {report['notes']}")

    print(f"\n{BOLD}  Affected Products ({report['affected_products_count']}){W}")
    print(f"  {'SKU':<20} {'Product':<35} {'Depth'}")
    print(f"  {'-'*70}")
    for p in report["affected_products"]:
        print(f"  {p.get('sku','?'):<20} {p.get('product_name','?'):<35} T{p.get('min_depth','?')}")

    if report["dependent_suppliers_affected"]:
        print(f"\n{BOLD}  Dependent Suppliers Affected ({len(report['dependent_suppliers_affected'])}){W}")
        for s in report["dependent_suppliers_affected"]:
            print(f"  [T{s.get('tier','?')}] {s.get('name','?')} ({s.get('country','?')}) ← {s.get('depends_on','?')}")

    if report["cascade_risks"]:
        print(f"\n{R}{BOLD}  Cascade Risks (single-source customers){W}")
        for c in report["cascade_risks"]:
            print(f"  {R}CASCADE: {c.get('supplier','?')} has no other source — also goes dark{W}")

    if report["alternative_suppliers"]:
        print(f"\n{G}{BOLD}  Alternative Suppliers (geographic diversity){W}")
        seen = set()
        for a in report["alternative_suppliers"]:
            key = (a.get("disrupted"), a.get("alternative"))
            if key in seen: continue
            seen.add(key)
            flags = a.get("alt_risk_flags") or []
            flag_str = f" [{', '.join(flags[:2])}]" if flags else ""
            print(f"  For {a.get('disrupted','?')}: {G}{a.get('alternative','?')}{W} ({a.get('alt_country','?')}){flag_str}")

    print(f"\n{BOLD}  Revenue at Risk Breakdown{W}")
    for b in report["revenue_at_risk"]["breakdown"]:
        if b.get("eur_at_risk") is None:
            print(f"  {b['sku']:<20} (no revenue data)")
        else:
            print(f"  {b['sku']:<20} €{b['eur_at_risk']:>15,.0f}  ({report['recovery_estimate_days']} days)")

    print(f"\n  {BOLD}Total revenue at risk: {R}€{eur:,.0f}{W}")
    print(f"{'═'*64}\n")


# ─── Neo4j write-back ────────────────────────────────────────────────────────

def write_scenario_event(db: Neo4jClient, report: dict, scenario_key: str) -> None:
    """Persist disruption scenario as an Event node in Neo4j."""
    eur = report["revenue_at_risk"]["total_eur"]
    ts  = report["generated_at"]
    desc = report["scenario"]
    sev  = report["severity"]
    skus = [p.get("sku") for p in report["affected_products"] if p.get("sku")]

    query = """
    MERGE (evt:Event {
        event_type: 'DISRUPTION_SCENARIO',
        description: $desc,
        date: $ts
    })
    ON CREATE SET
        evt.severity          = $sev,
        evt.revenue_at_risk   = $eur,
        evt.recovery_days     = $recovery,
        evt.disrupted_names   = $disrupted,
        evt.affected_skus     = $skus,
        evt.demo              = true
    ON MATCH SET
        evt.severity          = $sev,
        evt.revenue_at_risk   = $eur,
        evt.updated_at        = $ts
    WITH evt
    UNWIND $disrupted AS dname
    MATCH (s {name: dname})
    MERGE (s)-[:AFFECTED_BY {type: 'DISRUPTION', scenario: $desc, demo: true}]->(evt)
    """
    db.query(query, {
        "desc":     desc,
        "ts":       ts,
        "sev":      sev,
        "eur":      float(eur),
        "recovery": report["recovery_estimate_days"],
        "disrupted": report["disrupted_suppliers"],
        "skus":     skus,
    })
    log.info("Scenario event written to Neo4j.")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="UC4 Supply Chain Disruption Model")
    parser.add_argument("suppliers", nargs="*", help="Supplier name(s) to disrupt")
    parser.add_argument("--scenario",      help="Predefined scenario key")
    parser.add_argument("--list-scenarios",action="store_true", help="List available scenarios")
    parser.add_argument("--list-high-risk",action="store_true", help="Show HIGH/CRITICAL risk suppliers from Neo4j")
    parser.add_argument("--dry-run",       action="store_true", help="Print report only, no Neo4j write")
    parser.add_argument("--recovery-days", type=int, default=0,
                        help="Override recovery days (default: from scenario or tier estimate)")
    parser.add_argument("--output-json",   help="Write JSON report to file")
    args = parser.parse_args()

    if args.list_scenarios:
        print("\nAvailable disruption scenarios:")
        for key, meta in SCENARIOS.items():
            print(f"  {key:<30} [{meta['severity']:<8}] {meta['description']}")
        print()
        return

    pw = _load_password()
    db = Neo4jClient(NEO4J_URL, NEO4J_USER, pw)

    if args.list_high_risk:
        rows = db.query("""
            MATCH (s:Supplier)
            WHERE s.risk_score >= 0.6
            RETURN s.name AS name, s.country AS country, s.tier AS tier,
                   s.risk_score AS score, s.risk_summary AS flags
            ORDER BY s.risk_score DESC
        """, {})
        print(f"\nHIGH/CRITICAL risk suppliers ({len(rows)} found):")
        for r in rows:
            score = r.get("score") or 0
            sev = "CRITICAL" if score >= 0.8 else "HIGH"
            print(f"  [{sev}] {r['name']} ({r.get('country','?')}, T{r.get('tier','?')}) "
                  f"score={score:.2f}  flags={r.get('flags','')}")
        print()
        return

    # Resolve disrupted names from scenario or CLI
    scenario_meta: dict | None = None
    disrupted_names: list[str] = []

    if args.scenario:
        if args.scenario not in SCENARIOS:
            print(f"Unknown scenario '{args.scenario}'. Use --list-scenarios.")
            sys.exit(1)
        scenario_meta = SCENARIOS[args.scenario]
        disrupted_names = scenario_meta["disrupted"]
    elif args.suppliers:
        disrupted_names = list(args.suppliers)
    else:
        parser.print_help()
        sys.exit(1)

    # Override recovery if specified
    if args.recovery_days > 0:
        recovery_days = args.recovery_days
    elif scenario_meta:
        recovery_days = scenario_meta.get("recovery_days", 90)
    else:
        # Estimate from tier of disrupted nodes
        node_info_tmp = get_disrupted_node_info(db, disrupted_names)
        max_tier = max((r.get("tier") or 1 for r in node_info_tmp), default=1)
        recovery_days = TIER_RECOVERY_DAYS.get(max_tier, 90)

    log.info("Querying Neo4j for disruption impact...")

    node_info           = get_disrupted_node_info(db, disrupted_names)
    affected_products   = get_affected_products(db, disrupted_names)
    dependent_suppliers = get_dependent_suppliers(db, disrupted_names)
    alternatives        = get_alternative_suppliers(db, disrupted_names)
    cascade             = get_single_source_cascade(db, disrupted_names)

    if not node_info:
        log.warning("No matching nodes found in Neo4j for: %s", disrupted_names)
        log.info("Hint: check supplier names with `MATCH (s:Supplier) RETURN s.name ORDER BY s.name`")

    report = build_report(
        disrupted_names     = disrupted_names,
        scenario_meta       = scenario_meta,
        node_info           = node_info,
        affected_products   = affected_products,
        dependent_suppliers = dependent_suppliers,
        alternatives        = alternatives,
        cascade             = cascade,
        recovery_days       = recovery_days,
        dry_run             = args.dry_run,
    )

    print_report(report)

    if not args.dry_run:
        scenario_key = args.scenario or "custom"
        write_scenario_event(db, report, scenario_key)

    if args.output_json:
        with open(args.output_json, "w") as f:
            json.dump(report, f, indent=2)
        print(f"JSON report written to {args.output_json}")
    else:
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
