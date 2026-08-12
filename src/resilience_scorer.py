"""UC4 Supply Chain Resilience Scorer

For each product, computes 6 resilience dimensions:
  1. geo_diversity    — Herfindahl-Hirschman Index of contract value by country (inverted)
  2. single_source    — fraction of supply chain NOT flagged SINGLE_SOURCE
  3. risk_exposure    — 1 - (fraction of contract value with HIGH/CRITICAL suppliers)
  4. tier_coverage    — all tiers 1-3 have ≥2 qualified alternatives
  5. lead_time_score  — 1 - (avg lead time / 180 days)
  6. certification    — fraction of T1 suppliers with at least 1 quality cert

Overall resilience_score = weighted average (0-1, 1 = fully resilient)

Usage:
    python3 src/resilience_scorer.py
    python3 src/resilience_scorer.py --product SCANIA-R-500
    python3 src/resilience_scorer.py --dry-run
    python3 src/resilience_scorer.py --compare   # compare all products
"""

import json
import os
import sys
import argparse
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from neo4j_client import Neo4jClient

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

NEO4J_URL  = os.getenv("NEO4J_URL",      "http://10.0.1.114:7474")
NEO4J_USER = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "")

WEIGHTS = {
    "geo_diversity":  0.20,
    "single_source":  0.25,   # highest weight — single source = immediate halt
    "risk_exposure":  0.25,
    "tier_coverage":  0.15,
    "lead_time":      0.10,
    "certification":  0.05,
}

HIGH_RISK_THRESHOLD = 0.6    # risk_score >= this = HIGH/CRITICAL


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


# ── Data queries ──────────────────────────────────────────────────────────────

def get_product_skus(db: Neo4jClient) -> list[str]:
    rows = db.query("MATCH (p:Product) RETURN p.sku AS sku ORDER BY p.sku", {})
    return [r["sku"] for r in rows if r.get("sku")]


def get_supply_chain(db: Neo4jClient, sku: str) -> dict:
    """Fetch full supply chain data for a product SKU."""
    # All suppliers + relationship data
    suppliers_q = db.query("""
        MATCH (p:Product {sku: $sku})-[:SUPPLIED_BY|SOURCED_FROM*1..6]->(s:Supplier)
        WITH DISTINCT s,
             min(length((p)-[:SUPPLIED_BY|SOURCED_FROM*]->(s))) AS depth
        RETURN s.name AS name, s.country AS country, s.tier AS tier,
               s.risk_score AS risk_score, s.risk_flags AS risk_flags,
               depth AS depth
        ORDER BY depth
    """, {"sku": sku})

    # Tier-1 relationships with contract data
    t1_rels_q = db.query("""
        MATCH (p:Product {sku: $sku})-[r:SUPPLIED_BY]->(s:Supplier)
        RETURN s.name AS name, s.country AS country, s.tier AS tier,
               r.contract_value_eur AS contract_value,
               r.lead_time_days AS lead_time,
               r.single_source AS single_source,
               r.risk_flags AS rel_flags,
               s.risk_score AS risk_score, s.risk_flags AS sup_flags
    """, {"sku": sku})

    # All supply relationships with financial data
    all_rels_q = db.query("""
        MATCH (p:Product {sku: $sku})-[:SUPPLIED_BY|SOURCED_FROM*1..5]->(a)-[r:SOURCED_FROM|SUPPLIED_BY]->(b:Supplier)
        RETURN b.name AS supplier, b.country AS country, b.tier AS tier,
               b.risk_score AS risk_score,
               r.contract_value_eur AS contract_value,
               r.lead_time_days AS lead_time,
               r.single_source AS single_source,
               r.risk_flags AS rel_flags
    """, {"sku": sku})

    # Certifications for T1 suppliers
    certs_q = db.query("""
        MATCH (p:Product {sku: $sku})-[:SUPPLIED_BY]->(s:Supplier)-[:CERTIFIED_BY]->(c:Certificate)
        RETURN DISTINCT s.name AS supplier, c.name AS cert
    """, {"sku": sku})

    return {
        "sku": sku,
        "suppliers": suppliers_q,
        "t1_rels": t1_rels_q,
        "all_rels": all_rels_q + t1_rels_q,
        "certs": certs_q,
    }


def get_product_info(db: Neo4jClient, sku: str) -> dict:
    rows = db.query("MATCH (p:Product {sku:$sku}) RETURN p.name AS name, p.category AS cat", {"sku": sku})
    return rows[0] if rows else {"name": sku, "cat": ""}


# ── Dimension calculators ─────────────────────────────────────────────────────

def dim_geo_diversity(chain: dict) -> tuple[float, dict]:
    """1 - HHI of contract value by country. 1 = perfect diversity, 0 = monopoly."""
    country_val: dict[str, float] = {}
    for rel in chain["all_rels"]:
        cc = rel.get("country") or "??"
        cv = rel.get("contract_value") or 0
        country_val[cc] = country_val.get(cc, 0) + cv

    # If no contract values, fall back to supplier count
    if not any(country_val.values()):
        country_cnt: dict[str, int] = {}
        for s in chain["suppliers"]:
            cc = s.get("country") or "??"
            country_cnt[cc] = country_cnt.get(cc, 0) + 1
        total = sum(country_cnt.values()) or 1
        country_val = {cc: cnt/total for cc, cnt in country_cnt.items()}
    else:
        total = sum(country_val.values()) or 1
        country_val = {cc: v/total for cc, v in country_val.items()}

    hhi = sum(v**2 for v in country_val.values())
    score = max(0.0, 1.0 - hhi)
    detail = {
        "hhi": round(hhi, 3),
        "countries": sorted(country_val.items(), key=lambda x: -x[1]),
        "dominant_country": max(country_val, key=lambda k: country_val[k]) if country_val else "?",
    }
    return round(score, 3), detail


def dim_single_source(chain: dict) -> tuple[float, dict]:
    """Fraction of relationships NOT single-source (weighted by tier proximity)."""
    t1 = chain["t1_rels"]
    if not t1:
        return 0.5, {"t1_count": 0, "single_source_count": 0}

    ss = [r for r in t1 if r.get("single_source") or
          "SINGLE_SOURCE" in (r.get("rel_flags") or []) or
          "SINGLE_SOURCE" in (r.get("sup_flags") or [])]
    ss_ratio = len(ss) / len(t1)
    score = 1.0 - ss_ratio
    return round(score, 3), {
        "t1_count": len(t1),
        "single_source_count": len(ss),
        "single_source_suppliers": [r.get("name") for r in ss],
    }


def dim_risk_exposure(chain: dict) -> tuple[float, dict]:
    """1 - fraction of contract value with HIGH/CRITICAL suppliers."""
    rels = chain["all_rels"]
    if not rels:
        # Fall back to supplier count
        all_sups = chain["suppliers"]
        if not all_sups:
            return 0.5, {}
        high_risk = [s for s in all_sups if (s.get("risk_score") or 0) >= HIGH_RISK_THRESHOLD]
        ratio = len(high_risk) / len(all_sups)
        return round(1.0 - ratio, 3), {
            "method": "count",
            "high_risk_suppliers": [s.get("name") for s in high_risk],
        }

    total_cv  = sum(r.get("contract_value") or 0 for r in rels)
    hr_cv     = sum(r.get("contract_value") or 0 for r in rels
                    if (r.get("risk_score") or 0) >= HIGH_RISK_THRESHOLD)

    if total_cv == 0:
        # Count method
        all_sups = chain["suppliers"]
        high_risk = [s for s in all_sups if (s.get("risk_score") or 0) >= HIGH_RISK_THRESHOLD]
        ratio = len(high_risk) / max(len(all_sups), 1)
        return round(1.0 - ratio * 0.8, 3), {"method": "count", "high_risk_count": len(high_risk)}

    hr_ratio = hr_cv / total_cv
    score = max(0.0, 1.0 - hr_ratio)
    return round(score, 3), {
        "method": "contract_value",
        "total_contract_eur": total_cv,
        "high_risk_contract_eur": hr_cv,
        "high_risk_fraction": round(hr_ratio, 3),
    }


def dim_tier_coverage(chain: dict) -> tuple[float, dict]:
    """Score based on number of alternatives per tier (>= 2 per component = good)."""
    by_tier: dict[int, list] = {}
    for s in chain["suppliers"]:
        t = s.get("tier") or 1
        by_tier.setdefault(t, []).append(s.get("name"))

    scores = []
    detail = {}
    for tier in [1, 2, 3]:
        count = len(by_tier.get(tier, []))
        # 1 supplier = 0.25, 2 = 0.6, 3+ = 1.0
        tscore = 0.0 if count == 0 else (0.25 if count == 1 else (0.6 if count == 2 else 1.0))
        scores.append(tscore)
        detail[f"t{tier}_count"] = count
    score = sum(scores) / len(scores) if scores else 0.5
    return round(score, 3), detail


def dim_lead_time(chain: dict) -> tuple[float, dict]:
    """1 - (avg_lead_time / 180). Shorter = more resilient."""
    lead_times = [r.get("lead_time") for r in chain["all_rels"] if r.get("lead_time")]
    if not lead_times:
        return 0.5, {"avg_lead_days": None, "max_lead_days": None}
    avg = sum(lead_times) / len(lead_times)
    mx  = max(lead_times)
    score = max(0.0, 1.0 - avg / 180.0)
    return round(score, 3), {
        "avg_lead_days": round(avg, 1),
        "max_lead_days": mx,
        "long_lead_suppliers": [r.get("supplier") for r in chain["all_rels"]
                                 if (r.get("lead_time") or 0) > 90][:3],
    }


def dim_certification(chain: dict) -> tuple[float, dict]:
    """Fraction of T1 suppliers with at least one quality cert."""
    t1 = chain["t1_rels"]
    if not t1:
        return 0.5, {}
    certified = set(c.get("supplier") for c in chain.get("certs", []))
    t1_names  = set(r.get("name") for r in t1)
    frac = len(certified & t1_names) / len(t1_names) if t1_names else 0.5
    return round(frac, 3), {
        "t1_certified": sorted(certified & t1_names),
        "t1_uncertified": sorted(t1_names - certified),
    }


# ── Main scorer ───────────────────────────────────────────────────────────────

def score_product(db: Neo4jClient, sku: str) -> dict:
    chain   = get_supply_chain(db, sku)
    info    = get_product_info(db, sku)

    geo,   geo_d  = dim_geo_diversity(chain)
    ss,    ss_d   = dim_single_source(chain)
    risk,  risk_d = dim_risk_exposure(chain)
    cov,   cov_d  = dim_tier_coverage(chain)
    lt,    lt_d   = dim_lead_time(chain)
    cert,  cert_d = dim_certification(chain)

    dims = {
        "geo_diversity": geo,
        "single_source": ss,
        "risk_exposure": risk,
        "tier_coverage": cov,
        "lead_time":     lt,
        "certification": cert,
    }
    score = sum(WEIGHTS[k] * dims[k] for k in WEIGHTS)
    level = "RESILIENT" if score >= 0.7 else "MODERATE" if score >= 0.45 else "VULNERABLE"

    # Generate recommendations
    recs = []
    if ss < 0.7:
        for name in ss_d.get("single_source_suppliers", [])[:2]:
            recs.append(f"Qualify alternative for SINGLE_SOURCE supplier: {name}")
    if geo < 0.5:
        dom = geo_d.get("dominant_country", "?")
        recs.append(f"Reduce geographic concentration in {dom} — diversify sourcing")
    if risk < 0.6:
        recs.append("Engage supply chain risk mitigation for HIGH-risk upstream suppliers")
    if lt < 0.5:
        recs.append(f"Reduce lead times — avg {lt_d.get('avg_lead_days','?')}d is above 90d target")
    if cert < 0.7:
        uncert = cert_d.get("t1_uncertified", [])[:2]
        if uncert:
            recs.append(f"Drive certification for uncertified T1 suppliers: {', '.join(uncert)}")

    return {
        "sku": sku,
        "name": info.get("name", sku),
        "supplier_count": len(chain["suppliers"]),
        "resilience_score": round(score, 3),
        "resilience_level": level,
        "dimensions": dims,
        "dimension_details": {
            "geo_diversity": geo_d,
            "single_source": ss_d,
            "risk_exposure": risk_d,
            "tier_coverage": cov_d,
            "lead_time": lt_d,
            "certification": cert_d,
        },
        "recommendations": recs,
    }


def write_scores(db: Neo4jClient, results: list[dict]) -> None:
    for r in results:
        db.query("""
            MATCH (p:Product {sku: $sku})
            SET p.resilience_score = $score,
                p.resilience_level = $level,
                p.resilience_dims  = $dims
        """, {
            "sku":   r["sku"],
            "score": r["resilience_score"],
            "level": r["resilience_level"],
            "dims":  json.dumps(r["dimensions"]),
        })
    log.info("Wrote resilience scores to %d products.", len(results))


def print_results(results: list[dict]) -> None:
    W  = "\033[0m"; R = "\033[91m"; Y = "\033[93m"; G = "\033[92m"; BOLD = "\033[1m"

    print(f"\n{BOLD}{'═'*70}{W}")
    print(f"{BOLD}  UC4 Supply Chain Resilience Scores{W}")
    print(f"{'═'*70}")
    print(f"  {'Product':<30} {'Score':>6} {'Level':<12} {'GEO':>5} {'SS':>5} "
          f"{'RISK':>5} {'COV':>5} {'LT':>5} {'CERT':>5}")
    print(f"  {'-'*70}")

    for r in sorted(results, key=lambda x: x["resilience_score"]):
        lvl = r["resilience_level"]
        col = R if lvl == "VULNERABLE" else Y if lvl == "MODERATE" else G
        d = r["dimensions"]
        print(f"  {r['name']:<30} {col}{BOLD}{r['resilience_score']:>5.2f}{W} "
              f"{col}{lvl:<12}{W} "
              f"{d['geo_diversity']:>5.2f} {d['single_source']:>5.2f} "
              f"{d['risk_exposure']:>5.2f} {d['tier_coverage']:>5.2f} "
              f"{d['lead_time']:>5.2f} {d['certification']:>5.2f}")

    print(f"\n  {'─'*70}")
    for r in results:
        if r["recommendations"]:
            print(f"\n  {BOLD}{r['name']}{W} — Action items:")
            for rec in r["recommendations"]:
                print(f"    • {rec}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="UC4 Supply Chain Resilience Scorer")
    parser.add_argument("--product", help="Score only this SKU")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to Neo4j")
    parser.add_argument("--compare", action="store_true", help="Compare all products")
    parser.add_argument("--json",    action="store_true", help="Output JSON")
    args = parser.parse_args()

    pw = _load_password()
    db = Neo4jClient(NEO4J_URL, NEO4J_USER, pw)

    skus = [args.product] if args.product else get_product_skus(db)
    if not skus:
        log.error("No products found in Neo4j. Run seed_scania.sh first.")
        sys.exit(1)

    log.info("Scoring %d products…", len(skus))
    results = []
    for sku in skus:
        try:
            r = score_product(db, sku)
            results.append(r)
            log.info("  %s → resilience=%.2f (%s)", sku, r["resilience_score"], r["resilience_level"])
        except Exception as e:
            log.warning("  Failed %s: %s", sku, e)

    if not results:
        log.error("No results. Check Neo4j connectivity.")
        sys.exit(1)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_results(results)

    if not args.dry_run:
        write_scores(db, results)
        log.info("Resilience scores written to Neo4j Product nodes.")


if __name__ == "__main__":
    main()
