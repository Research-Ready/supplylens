"""Alternative Sourcing Engine — UC4 Supply Chain

Finds alternative suppliers for HIGH/CRITICAL risk nodes using:
  - ALT_SOURCE relationships in Neo4j
  - Geographic diversification scoring
  - Switching cost estimates
  - Dual-sourcing recommendations

Usage:
    python3 src/alternative_sourcing.py [--product SKU] [--supplier NAME]
                                        [--min-risk HIGH] [--json] [--write-neo4j]
"""

import json
import os
import sys
import base64
import urllib.request
import argparse
from typing import Dict, List, Optional, Tuple
from datetime import datetime


# ── Config ──────────────────────────────────────────────────────────────────
NEO4J_URL  = os.getenv("NEO4J_URL",  "http://10.0.1.114:7474")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "")

# Switching cost as % of annual contract value (rough estimate)
SWITCHING_COST_PCT = {
    "LOW":    0.08,   # commodity, easy to switch
    "MEDIUM": 0.15,   # some qualification required
    "HIGH":   0.30,   # significant qualification + tooling
    "CRITICAL": 0.50, # custom parts, long qualification cycle
}

# Country risk tiers (for diversification scoring)
COUNTRY_RISK = {
    # 0 = best, 3 = highest
    "SE": 0, "DE": 0, "NO": 0, "FI": 0, "CH": 0, "NL": 0, "BE": 0, "FR": 0,
    "DK": 0, "AT": 0, "GB": 0, "US": 0, "CA": 0, "AU": 0, "NZ": 0, "JP": 0, "KR": 0,
    "IE": 0, "CZ": 0, "PL": 0, "HU": 0,
    "BR": 1, "MX": 1, "ZA": 1, "IN": 1, "TR": 1, "TW": 1, "CL": 1,
    "CN": 2, "MY": 2, "TH": 2, "ID": 2, "VN": 2, "MA": 2,
    "RU": 3, "BY": 3, "IR": 3, "KP": 3, "MM": 3, "SD": 3,
}

RISK_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


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


def _write_recommendation(supplier: str, alt: str, score: float, action: str) -> None:
    q = """
    MATCH (s:Supplier {name: $supplier}), (a:Supplier {name: $alt})
    MERGE (s)-[r:ALT_SOURCE {evaluated_by: 'alternative_sourcing.py'}]->(a)
    SET r.switch_score = $score,
        r.action = $action,
        r.evaluated_at = $ts
    """
    _neo4j_query(q, {"supplier": supplier, "alt": alt,
                     "score": round(score, 3), "action": action,
                     "ts": datetime.utcnow().isoformat()})


# ── Demo data — fallback when Neo4j offline ──────────────────────────────────
DEMO_HIGH_RISK = [
    {
        "name": "Norilsk Nickel", "country": "RU", "tier": 3, "risk": "CRITICAL",
        "flags": ["SANC", "GEO", "CBAM"], "contract_value": 95_000_000,
        "products": ["SCANIA-L-340-BEV"],
        "alternatives": [
            {"name": "Vale (nickel division)",    "country": "BR", "tier": 3, "risk": "MEDIUM",  "cert_match": 0.7},
            {"name": "BHP Nickel West",            "country": "AU", "tier": 3, "risk": "LOW",     "cert_match": 0.8},
            {"name": "Wyloo Metals",               "country": "AU", "tier": 3, "risk": "LOW",     "cert_match": 0.6},
        ],
    },
    {
        "name": "Shanshan Advanced Materials", "country": "CN", "tier": 2, "risk": "HIGH",
        "flags": ["UFLPA", "GEO"], "contract_value": 62_000_000,
        "products": ["SCANIA-L-340-BEV"],
        "alternatives": [
            {"name": "Umicore Battery Materials",  "country": "BE", "tier": 2, "risk": "LOW",    "cert_match": 0.9},
            {"name": "BASF Battery Materials",      "country": "DE", "tier": 2, "risk": "LOW",    "cert_match": 0.95},
            {"name": "Sumitomo Metal Mining",       "country": "JP", "tier": 2, "risk": "LOW",    "cert_match": 0.85},
        ],
    },
    {
        "name": "Ganfeng Lithium", "country": "CN", "tier": 3, "risk": "HIGH",
        "flags": ["GEO", "UFLPA"], "contract_value": 38_000_000,
        "products": ["SCANIA-L-340-BEV"],
        "alternatives": [
            {"name": "Albemarle",                   "country": "US", "tier": 3, "risk": "LOW",    "cert_match": 0.9},
            {"name": "SQM",                         "country": "CL", "tier": 3, "risk": "MEDIUM", "cert_match": 0.8},
            {"name": "Livent (lithium)",             "country": "US", "tier": 3, "risk": "LOW",    "cert_match": 0.75},
        ],
    },
    {
        "name": "CATL", "country": "CN", "tier": 1, "risk": "HIGH",
        "flags": ["UFLPA", "GEO", "CBAM"], "contract_value": 820_000_000,
        "products": ["SCANIA-L-340-BEV"],
        "alternatives": [
            {"name": "Samsung SDI",                 "country": "KR", "tier": 1, "risk": "LOW",    "cert_match": 0.85},
            {"name": "LG Energy Solution",          "country": "KR", "tier": 1, "risk": "LOW",    "cert_match": 0.9},
            {"name": "Northvolt",                   "country": "SE", "tier": 1, "risk": "LOW",    "cert_match": 0.75},
        ],
    },
    {
        "name": "Proterial Ltd", "country": "JP", "tier": 2, "risk": "HIGH",
        "flags": ["GEO"], "contract_value": 28_000_000,
        "products": ["SCANIA-L-340-BEV"],
        "alternatives": [
            {"name": "Vacuumschmelze",              "country": "DE", "tier": 2, "risk": "LOW",    "cert_match": 0.85},
            {"name": "Arnold Magnetic Technologies","country": "US", "tier": 2, "risk": "LOW",    "cert_match": 0.7},
        ],
    },
    {
        "name": "Glencore (cobalt)", "country": "CH", "tier": 3, "risk": "HIGH",
        "flags": ["ESG", "GEO"], "contract_value": 42_000_000,
        "products": ["SCANIA-L-340-BEV"],
        "alternatives": [
            {"name": "Freeport Cobalt",             "country": "FI", "tier": 3, "risk": "LOW",    "cert_match": 0.8},
            {"name": "Umicore (cobalt refining)",   "country": "BE", "tier": 3, "risk": "LOW",    "cert_match": 0.9},
        ],
    },
]


def score_alternative(
    current: dict,
    alt: dict,
    carbon_price: float = 65.0,
) -> float:
    """Score alternative supplier (0–1, higher = better switch candidate).

    Weights:
      40%  Risk reduction (from current to alt)
      25%  Geographic diversification (different country, lower risk tier)
      20%  Certification / product match
      15%  Penalty for switching cost (lower contract_value = lower penalty)
    """
    risk_diff = RISK_RANK[current["risk"]] - RISK_RANK.get(alt["risk"], 0)
    risk_score = max(0, min(1, risk_diff / 3.0))

    # Geo: different country + lower COUNTRY_RISK tier
    same_country = alt["country"] == current["country"]
    geo_diff = COUNTRY_RISK.get(current["country"], 1) - COUNTRY_RISK.get(alt["country"], 0)
    geo_score = 0.0 if same_country else min(1.0, 0.3 + geo_diff * 0.25)

    cert_score = float(alt.get("cert_match", 0.7))

    # Switching cost penalty (normalize against a €100M reference)
    cost_pct = SWITCHING_COST_PCT.get(current["risk"], 0.15)
    switch_eur = current.get("contract_value", 10_000_000) * cost_pct
    cost_score = max(0.0, 1.0 - switch_eur / 50_000_000)  # 50M = max reference

    total = (risk_score * 0.40 + geo_score * 0.25 + cert_score * 0.20 + cost_score * 0.15)
    return round(total, 4)


def recommend_action(current: dict, best_alt: dict, score: float) -> str:
    if score >= 0.75:
        return "SWITCH_NOW"       # immediate sourcing transition
    if score >= 0.55:
        return "DUAL_SOURCE"      # qualify alt as 30–50% volume
    if score >= 0.35:
        return "QUALIFY"          # begin qualification, keep current
    return "MONITOR"              # no viable alt — monitor risk closely


def get_high_risk_suppliers(
    sku: Optional[str] = None,
    min_risk: str = "HIGH",
) -> List[dict]:
    """Fetch high-risk suppliers with their ALT_SOURCE alternatives from Neo4j."""
    min_rank = RISK_RANK.get(min_risk.upper(), 2)

    if sku:
        q = """
        MATCH (p:Product {sku: $sku})-[:SUPPLIED_BY|SOURCED_FROM*1..5]->(s:Supplier)
        WHERE s.risk IN ['HIGH','CRITICAL'] OR any(f IN s.flags WHERE f IN ['SANC','UFLPA'])
        OPTIONAL MATCH (s)-[:ALT_SOURCE]->(alt:Supplier)
        RETURN s.name AS name, s.country AS country, s.tier AS tier,
               s.risk AS risk, s.flags AS flags, s.contract_value AS contract_value,
               collect({name: alt.name, country: alt.country, tier: alt.tier,
                        risk: alt.risk, cert_match: 0.8}) AS alternatives
        """
        rows = _neo4j_query(q, {"sku": sku})
    else:
        q = """
        MATCH (s:Supplier)
        WHERE s.risk IN ['HIGH','CRITICAL'] OR any(f IN s.flags WHERE f IN ['SANC','UFLPA'])
        OPTIONAL MATCH (s)-[:ALT_SOURCE]->(alt:Supplier)
        RETURN s.name AS name, s.country AS country, s.tier AS tier,
               s.risk AS risk, s.flags AS flags, s.contract_value AS contract_value,
               collect({name: alt.name, country: alt.country, tier: alt.tier,
                        risk: alt.risk, cert_match: 0.8}) AS alternatives
        """
        rows = _neo4j_query(q)

    if rows:
        # Filter out null alternatives
        for r in rows:
            r["alternatives"] = [a for a in (r.get("alternatives") or []) if a.get("name")]
            r["products"] = [sku] if sku else []
        return [r for r in rows if RISK_RANK.get(r.get("risk","LOW"), 0) >= min_rank]

    return DEMO_HIGH_RISK  # fallback


def run_assessment(
    sku: Optional[str] = None,
    supplier_filter: Optional[str] = None,
    min_risk: str = "HIGH",
    write_neo4j: bool = False,
) -> List[dict]:
    """Full alternative sourcing assessment."""
    suppliers = get_high_risk_suppliers(sku, min_risk)

    if supplier_filter:
        suppliers = [s for s in suppliers if supplier_filter.lower() in s["name"].lower()]

    results = []
    for s in suppliers:
        alts = s.get("alternatives", [])
        scored_alts = []
        for alt in alts:
            sc = score_alternative(s, alt)
            action = recommend_action(s, alt, sc)
            alt_result = {
                "name":    alt["name"],
                "country": alt.get("country", "?"),
                "tier":    alt.get("tier", s.get("tier")),
                "risk":    alt.get("risk", "UNKNOWN"),
                "score":   sc,
                "action":  action,
            }
            scored_alts.append(alt_result)
            if write_neo4j and alt.get("name"):
                _write_recommendation(s["name"], alt["name"], sc, action)

        scored_alts.sort(key=lambda a: a["score"], reverse=True)

        # Top recommendation
        best = scored_alts[0] if scored_alts else None
        top_action = best["action"] if best else "MONITOR"
        top_score  = best["score"] if best else 0.0

        # Switching cost
        contract_v = float(str(s.get("contract_value", 0)).replace("€","").replace("M","000000").replace("K","000").replace(",","")) if s.get("contract_value") else 0
        switch_cost = contract_v * SWITCHING_COST_PCT.get(s.get("risk","LOW"), 0.15)

        results.append({
            "supplier":        s["name"],
            "country":         s.get("country", "?"),
            "tier":            s.get("tier"),
            "risk":            s.get("risk", "?"),
            "flags":           s.get("flags", []),
            "contract_value":  contract_v,
            "switching_cost":  round(switch_cost),
            "products":        s.get("products", []),
            "top_action":      top_action,
            "top_score":       top_score,
            "best_alt":        best,
            "all_alts":        scored_alts,
        })

    results.sort(key=lambda r: RISK_RANK.get(r["risk"], 0), reverse=True)
    return results


def print_report(results: List[dict]) -> None:
    W = 110
    print("=" * W)
    print(f"  ALTERNATIVE SOURCING ASSESSMENT — UC4 Supply Chain  |  {datetime.utcnow().strftime('%Y-%m-%d')}")
    print("=" * W)

    switch_now  = [r for r in results if r["top_action"] == "SWITCH_NOW"]
    dual_source = [r for r in results if r["top_action"] == "DUAL_SOURCE"]
    qualify     = [r for r in results if r["top_action"] == "QUALIFY"]
    monitor     = [r for r in results if r["top_action"] == "MONITOR"]

    print(f"  Assessed: {len(results)}  |  SWITCH_NOW: {len(switch_now)}  |  DUAL_SOURCE: {len(dual_source)}  |  QUALIFY: {len(qualify)}  |  MONITOR: {len(monitor)}")
    print("-" * W)

    for r in results:
        flags = " ".join(f"[{f}]" for f in (r["flags"] or []))
        cv = r["contract_value"]
        cv_str = f"€{cv/1e6:.0f}M" if cv >= 1e6 else (f"€{cv/1e3:.0f}K" if cv >= 1000 else f"€{cv:.0f}")
        sw_str = f"€{r['switching_cost']/1e6:.1f}M" if r["switching_cost"] >= 1e6 else f"€{r['switching_cost']/1e3:.0f}K"

        action_colors = {"SWITCH_NOW":"*** ","DUAL_SOURCE":"**  ","QUALIFY":"*   ","MONITOR":"    "}
        prefix = action_colors.get(r["top_action"], "    ")

        print(f"\n{prefix}[{r['risk']:8}] T{r['tier']} {r['supplier']} ({r['country']})  {flags}")
        print(f"         Contract: {cv_str}/yr   Switching cost estimate: {sw_str}   Action: {r['top_action']}")

        if r["best_alt"]:
            b = r["best_alt"]
            print(f"         Best alt: {b['name']} ({b['country']}, {b['risk']})  Score: {b['score']:.2f}")

        for alt in r["all_alts"]:
            bar = "█" * int(alt["score"] * 20)
            print(f"           → {alt['name']:<35} ({alt['country']}, {alt['risk']:<8}) {bar:<20} {alt['score']:.2f}  [{alt['action']}]")

        if not r["all_alts"]:
            print(f"         No alternatives found — single-source dependency! Initiate market scan.")

    print()
    print("=" * W)
    print("  RECOMMENDED ACTIONS:")
    for r in switch_now:
        print(f"   1. SWITCH NOW  — {r['supplier']} ({r['risk']}) → {r['best_alt']['name'] if r['best_alt'] else 'TBD'}")
    for r in dual_source:
        print(f"   2. DUAL SOURCE — {r['supplier']} + {r['best_alt']['name'] if r['best_alt'] else 'TBD'} (30-50% split)")
    print("=" * W)


def main():
    parser = argparse.ArgumentParser(description="Alternative sourcing engine")
    parser.add_argument("--product",   default=None)
    parser.add_argument("--supplier",  default=None)
    parser.add_argument("--min-risk",  default="HIGH", choices=["MEDIUM","HIGH","CRITICAL"])
    parser.add_argument("--json",      action="store_true")
    parser.add_argument("--write-neo4j", action="store_true")
    args = parser.parse_args()

    results = run_assessment(args.product, args.supplier, args.min_risk, args.write_neo4j)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_report(results)

    critical = [r for r in results if r["top_action"] == "SWITCH_NOW"]
    if critical:
        sys.exit(1)  # CI signal: immediate action items exist


if __name__ == "__main__":
    main()
