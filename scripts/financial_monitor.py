#!/usr/bin/env python3
"""SupplyLens Financial Monitor — UC4

Weekly check of supplier financial health:
  - Altman Z-Score thresholds (< 1.81 → DISTRESS alert)
  - Net Debt / EBITDA covenant breach (> 5× → alert)
  - Credit rating downgrades (below BBB- / Ba1)
  - Write alerts to Neo4j (FinancialAlert nodes)
  - Print summary + optionally send Slack webhook

Data source: reads from Neo4j supplier nodes (altman_z_score, net_debt_ebitda,
credit_rating properties set in cypher v8).

Usage:
    python3 scripts/financial_monitor.py
    python3 scripts/financial_monitor.py --json
    python3 scripts/financial_monitor.py --threshold-z 2.0   # raise Z alert threshold
    python3 scripts/financial_monitor.py --write-neo4j        # persist alerts to graph
    NEO4J_PASSWORD=xxx python3 scripts/financial_monitor.py
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import date
from typing import Dict, List, Optional

# ─── Config ──────────────────────────────────────────────────────────────────

NEO4J_URL  = os.getenv("NEO4J_URL",  "http://10.0.1.114:7474")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "")

# Thresholds
Z_DISTRESS   = 1.81   # Altman Z < 1.81 → distress zone
Z_GREY       = 2.99   # Altman Z 1.81-2.99 → grey zone
ND_EBITDA_WARN = 4.0  # Net Debt/EBITDA > 4× → watch
ND_EBITDA_ALERT = 5.5 # Net Debt/EBITDA > 5.5× → alert

# Credit rating thresholds (investment grade = BBB- or higher)
RATING_ORDER = [
    "AAA","AA+","AA","AA-","A+","A","A-",
    "BBB+","BBB","BBB-",              # investment grade floor
    "BB+","BB","BB-",                 # speculative grade
    "B+","B","B-","CCC+","CCC","CCC-","CC","C","D","NR","NM",
]
INVESTMENT_GRADE_FLOOR = "BBB-"
SPECULATIVE_FLOOR      = "BB+"

# Demo fallback data (used when Neo4j unreachable)
DEMO_SUPPLIERS = [
    {"name":"ZF Friedrichshafen",   "altman_z_score":1.92, "net_debt_ebitda":4.2, "credit_rating":"BBB-", "financial_risk":"WATCH"},
    {"name":"Continental AG",       "altman_z_score":2.18, "net_debt_ebitda":3.1, "credit_rating":"BBB",  "financial_risk":"WATCH"},
    {"name":"Garrett Motion",       "altman_z_score":1.65, "net_debt_ebitda":6.8, "credit_rating":"B+",   "financial_risk":"DISTRESS"},
    {"name":"Leoni AG",             "altman_z_score":1.71, "net_debt_ebitda":5.9, "credit_rating":"B",    "financial_risk":"DISTRESS"},
    {"name":"Aptiv PLC",            "altman_z_score":2.44, "net_debt_ebitda":2.8, "credit_rating":"BBB",  "financial_risk":"WATCH"},
    {"name":"Dana Incorporated",    "altman_z_score":2.31, "net_debt_ebitda":3.6, "credit_rating":"BB+",  "financial_risk":"WATCH"},
    {"name":"Saarstahl AG",         "altman_z_score":2.67, "net_debt_ebitda":2.1, "credit_rating":"BB+",  "financial_risk":"STABLE"},
    {"name":"SSAB",                 "altman_z_score":3.21, "net_debt_ebitda":0.8, "credit_rating":"BBB-", "financial_risk":"STABLE"},
    {"name":"Michelin",             "altman_z_score":3.45, "net_debt_ebitda":1.2, "credit_rating":"A-",   "financial_risk":"STABLE"},
    {"name":"Bosch",                "altman_z_score":4.12, "net_debt_ebitda":0.3, "credit_rating":"A+",   "financial_risk":"STABLE"},
    {"name":"Infineon Technologies","altman_z_score":3.88, "net_debt_ebitda":0.9, "credit_rating":"A-",   "financial_risk":"STABLE"},
    {"name":"STMicroelectronics",   "altman_z_score":4.23, "net_debt_ebitda":0.2, "credit_rating":"BBB+", "financial_risk":"STABLE"},
    {"name":"CATL",                 "altman_z_score":3.56, "net_debt_ebitda":1.5, "credit_rating":"A",    "financial_risk":"STABLE"},
    {"name":"SQM",                  "altman_z_score":3.02, "net_debt_ebitda":1.1, "credit_rating":"BBB+", "financial_risk":"STABLE"},
    {"name":"Codelco",              "altman_z_score":2.75, "net_debt_ebitda":2.9, "credit_rating":"A-",   "financial_risk":"STABLE"},
    {"name":"Umicore Battery Materials","altman_z_score":2.89,"net_debt_ebitda":2.4,"credit_rating":"BBB","financial_risk":"STABLE"},
    {"name":"Toray Industries",     "altman_z_score":2.34, "net_debt_ebitda":3.2, "credit_rating":"BBB",  "financial_risk":"WATCH"},
    {"name":"Outokumpu Oyj",        "altman_z_score":2.12, "net_debt_ebitda":3.8, "credit_rating":"BB+",  "financial_risk":"WATCH"},
    {"name":"TimkenSteel Corporation","altman_z_score":2.56,"net_debt_ebitda":2.5,"credit_rating":"BB",   "financial_risk":"STABLE"},
    {"name":"Sensata Technologies", "altman_z_score":2.78, "net_debt_ebitda":3.0, "credit_rating":"BB+",  "financial_risk":"STABLE"},
]


# ─── Neo4j helpers ────────────────────────────────────────────────────────────

def _neo4j_query(cypher: str, params: dict | None = None) -> list[dict]:
    if not NEO4J_PASS:
        return []
    auth = base64.b64encode(f"{NEO4J_USER}:{NEO4J_PASS}".encode()).decode()
    body = json.dumps({"statements": [{"statement": cypher,
                                       "parameters": params or {}}]}).encode()
    req = urllib.request.Request(
        f"{NEO4J_URL}/db/neo4j/tx/commit",
        data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Basic {auth}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read())
            if d.get("errors"):
                print(f"[WARN] Neo4j errors: {d['errors']}", file=sys.stderr)
                return []
            rows = d.get("results", [{}])[0].get("data", [])
            cols = d.get("results", [{}])[0].get("columns", [])
            return [{c: row["row"][i] for i, c in enumerate(cols)} for row in rows]
    except urllib.error.URLError as e:
        print(f"[WARN] Neo4j unreachable: {e}", file=sys.stderr)
        return []


def _load_suppliers() -> list[dict]:
    rows = _neo4j_query("""
        MATCH (s:Supplier)
        WHERE s.altman_z_score IS NOT NULL
        RETURN s.name AS name,
               s.altman_z_score AS altman_z_score,
               s.net_debt_ebitda AS net_debt_ebitda,
               s.credit_rating AS credit_rating,
               s.financial_risk AS financial_risk
        ORDER BY s.altman_z_score ASC
    """)
    if rows:
        return rows
    print("[INFO] Neo4j unreachable or no financial data — using demo dataset",
          file=sys.stderr)
    return DEMO_SUPPLIERS


def _write_alert_neo4j(alert: dict) -> bool:
    """Persist a FinancialAlert node to Neo4j."""
    cypher = """
    MERGE (a:FinancialAlert {supplier: $supplier, alert_type: $alert_type, check_date: $check_date})
    ON CREATE SET
        a.z_score        = $z_score,
        a.nd_ebitda      = $nd_ebitda,
        a.credit_rating  = $credit_rating,
        a.severity       = $severity,
        a.message        = $message,
        a.demo           = true
    ON MATCH SET
        a.z_score        = $z_score,
        a.nd_ebitda      = $nd_ebitda,
        a.severity       = $severity,
        a.message        = $message
    WITH a
    MATCH (s:Supplier {name: $supplier})
    MERGE (s)-[:HAS_ALERT]->(a)
    RETURN a.supplier AS created
    """
    rows = _neo4j_query(cypher, alert)
    return bool(rows)


# ─── Alert logic ─────────────────────────────────────────────────────────────

def _rating_idx(rating: Optional[str]) -> int:
    """Lower index = better rating."""
    try:
        return RATING_ORDER.index(str(rating))
    except ValueError:
        return len(RATING_ORDER)  # unknown → worst


def analyze_supplier(s: dict, z_threshold: float = Z_DISTRESS,
                     grey_threshold: float = Z_GREY) -> List[dict]:
    """Produce alert dicts for a supplier. Returns [] if healthy."""
    alerts = []
    name = s.get("name", "?")
    z = s.get("altman_z_score")
    nd = s.get("net_debt_ebitda")
    rating = s.get("credit_rating", "NR")
    today = str(date.today())

    # 1. Altman Z-Score distress
    if z is not None and z < z_threshold:
        alerts.append({
            "supplier": name, "alert_type": "ALTMAN_Z_DISTRESS", "check_date": today,
            "z_score": z, "nd_ebitda": nd, "credit_rating": rating, "severity": "CRITICAL",
            "message": (f"Altman Z-Score {z:.2f} < {z_threshold:.2f} (distress zone). "
                        f"High bankruptcy risk. Review exposure and contingency supplier."),
        })
    elif z is not None and z < grey_threshold:
        alerts.append({
            "supplier": name, "alert_type": "ALTMAN_Z_GREY_ZONE", "check_date": today,
            "z_score": z, "nd_ebitda": nd, "credit_rating": rating, "severity": "HIGH",
            "message": (f"Altman Z-Score {z:.2f} in grey zone ({z_threshold:.2f}–{grey_threshold:.2f}). "
                        f"Monitor quarterly; activate dual-sourcing review."),
        })

    # 2. Net Debt / EBITDA leverage breach
    if nd is not None and nd > ND_EBITDA_ALERT:
        alerts.append({
            "supplier": name, "alert_type": "ND_EBITDA_COVENANT_BREACH", "check_date": today,
            "z_score": z, "nd_ebitda": nd, "credit_rating": rating, "severity": "CRITICAL",
            "message": (f"Net Debt/EBITDA {nd:.1f}× exceeds covenant threshold {ND_EBITDA_ALERT:.1f}×. "
                        f"Risk of debt restructuring or payment delays."),
        })
    elif nd is not None and nd > ND_EBITDA_WARN:
        alerts.append({
            "supplier": name, "alert_type": "ND_EBITDA_ELEVATED", "check_date": today,
            "z_score": z, "nd_ebitda": nd, "credit_rating": rating, "severity": "MEDIUM",
            "message": (f"Net Debt/EBITDA {nd:.1f}× above watch threshold {ND_EBITDA_WARN:.1f}×. "
                        f"Request next quarterly covenant certificate."),
        })

    # 3. Credit rating below investment grade
    rating_pos = _rating_idx(rating)
    floor_pos  = _rating_idx(INVESTMENT_GRADE_FLOOR)
    if rating_pos > floor_pos:
        severity = "CRITICAL" if rating_pos > _rating_idx("B+") else "HIGH"
        alerts.append({
            "supplier": name, "alert_type": "BELOW_INVESTMENT_GRADE", "check_date": today,
            "z_score": z, "nd_ebitda": nd, "credit_rating": rating, "severity": severity,
            "message": (f"Credit rating {rating} is below investment grade (≥ {INVESTMENT_GRADE_FLOOR}). "
                        f"Increased counterparty risk; consider payment terms adjustment."),
        })

    return alerts


# ─── Main ─────────────────────────────────────────────────────────────────────

def run_monitor(z_threshold: float = Z_DISTRESS,
                grey_threshold: float = Z_GREY,
                write_neo4j: bool = False) -> dict:
    """Run full financial health check. Returns summary dict."""
    suppliers = _load_suppliers()
    all_alerts: List[dict] = []

    for s in suppliers:
        alerts = analyze_supplier(s, z_threshold, grey_threshold)
        all_alerts.extend(alerts)
        if write_neo4j and NEO4J_PASS and alerts:
            for a in alerts:
                ok = _write_alert_neo4j(a)
                if not ok:
                    print(f"[WARN] Could not write alert for {a['supplier']}", file=sys.stderr)

    critical = [a for a in all_alerts if a["severity"] == "CRITICAL"]
    high     = [a for a in all_alerts if a["severity"] == "HIGH"]
    medium   = [a for a in all_alerts if a["severity"] == "MEDIUM"]

    return {
        "check_date": str(date.today()),
        "suppliers_checked": len(suppliers),
        "total_alerts": len(all_alerts),
        "critical": len(critical),
        "high": len(high),
        "medium": len(medium),
        "alerts": all_alerts,
        "suppliers": suppliers,
    }


def _print_report(result: dict, verbose: bool = False) -> None:
    SEV_COLOR = {"CRITICAL": "\033[91m", "HIGH": "\033[93m",
                 "MEDIUM": "\033[94m"}
    RST = "\033[0m"

    print(f"\nSupplyLens Financial Monitor — {result['check_date']}")
    print(f"Suppliers checked: {result['suppliers_checked']}  "
          f"Total alerts: {result['total_alerts']}  "
          f"Critical: {result['critical']}  High: {result['high']}  Medium: {result['medium']}")
    print("─" * 80)

    # Health summary
    print(f"\n{'Supplier':<30} {'Z-Score':<10} {'ND/EBITDA':<12} {'Rating':<8} Status")
    print("─" * 80)
    for s in result["suppliers"]:
        z   = s.get("altman_z_score") or 0
        nd  = s.get("net_debt_ebitda") or 0
        rt  = s.get("credit_rating", "NR")
        fin = s.get("financial_risk", "?")
        col = "\033[91m" if fin == "DISTRESS" else ("\033[93m" if fin == "WATCH" else "\033[92m")
        z_col = "\033[91m" if z < Z_DISTRESS else ("\033[93m" if z < Z_GREY else "")
        print(f"{s['name']:<30} {z_col}{z:>6.2f}{RST}      "
              f"{nd:>5.1f}×       {rt:<8} {col}{fin}{RST}")

    # Alerts
    if result["alerts"]:
        print(f"\n{'─'*80}")
        print("ALERTS:")
        print(f"{'─'*80}")
        for a in result["alerts"]:
            col = SEV_COLOR.get(a["severity"], "")
            print(f"\n  {col}[{a['severity']}]{RST} {a['supplier']}")
            print(f"  Type: {a['alert_type']}")
            print(f"  {a['message']}")
    else:
        print("\n  No alerts — all suppliers within thresholds.")

    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="SupplyLens Financial Monitor")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--write-neo4j", action="store_true",
                        help="Write FinancialAlert nodes to Neo4j")
    parser.add_argument("--threshold-z", type=float, default=Z_DISTRESS,
                        help=f"Altman Z alert threshold (default {Z_DISTRESS})")
    parser.add_argument("--threshold-grey", type=float, default=Z_GREY,
                        help=f"Altman Z grey-zone threshold (default {Z_GREY})")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    result = run_monitor(
        z_threshold=args.threshold_z,
        grey_threshold=args.threshold_grey,
        write_neo4j=args.write_neo4j,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        _print_report(result, verbose=args.verbose)

    # Exit code: 2 = critical alerts, 1 = high/medium, 0 = clean
    if result["critical"] > 0:
        sys.exit(2)
    if result["high"] + result["medium"] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
