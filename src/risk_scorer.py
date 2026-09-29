"""UC4 Supply Chain Risk Scorer
Traverses the Neo4j graph, calculates a composite risk score (0-1) per Supplier,
and writes risk_score + risk_summary back to each node.

Usage:
    python3 src/risk_scorer.py              # score all suppliers
    python3 src/risk_scorer.py --dry-run    # print scores, don't write to Neo4j
    python3 src/risk_scorer.py --product SCANIA-R-500  # only that product's chain

Risk model (weighted sum, capped at 1.0):
    GEOPOLITICAL_RISK   +0.30   (country in CN/RU/IR/BY/KP)
    SINGLE_SOURCE       +0.25   (no alternative supplier for this component)
    CONFLICT_MINERAL    +0.25   (Tantalum, Tin, Tungsten, Gold — DRC/conflict zones)
    SANCTIONS_RISK      +0.20   (active sanctions on country or entity)
    CLIMATE_RISK        +0.10   (Arctic/high-emission operations)
    ESG_RISK            +0.10   (tailings dam, labour, environmental violations)
    DEFORESTATION_RISK  +0.10   (primary deforestation commodity)
    DODD_FRANK_REPORTABLE +0.05 (SEC Dodd-Frank conflict minerals disclosure)
    tier_penalty        +0.05 * (tier - 1)  (deeper = less visibility)
    inferred_penalty    +0.05   (node was LLM-inferred, not verified)
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

NEO4J_URL  = os.getenv("NEO4J_URL",      "http://localhost:7474")
NEO4J_USER = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "")

# Risk weights
WEIGHTS: dict[str, float] = {
    "GEOPOLITICAL_RISK":     0.30,
    "SINGLE_SOURCE":         0.25,
    "CONFLICT_MINERAL":      0.25,
    "SANCTIONS_RISK":        0.20,
    "CLIMATE_RISK":          0.10,
    "ARCTIC_OPERATIONS":     0.08,
    "ESG_RISK":              0.10,
    "DEFORESTATION_RISK":    0.10,
    "DODD_FRANK_REPORTABLE": 0.05,
    "TAILINGS_RISK":         0.08,
    "CHILD_LABOUR_RISK":     0.15,
}

TIER_PENALTY      = 0.05   # per tier above 1
INFERRED_PENALTY  = 0.05


def load_credentials() -> str:
    """Load Neo4j password from env, KeePass, or prompt."""
    if NEO4J_PASS:
        return NEO4J_PASS
    try:
        from pykeepass import PyKeePass
        repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        kdbx = os.path.join(repo, "passwords.kdbx")
        kp = PyKeePass(kdbx, password="SupplyChainBaby100!")
        entry = kp.find_entries(title="Neo4j", first=True)
        if entry:
            return entry.password
    except Exception as exc:
        log.debug("KeePass lookup failed: %s", exc)
    return input("Neo4j password: ").strip()


def calc_score(supplier: dict) -> tuple[float, list[str]]:
    """Return (score 0-1, list of active risk factors)."""
    active: list[str] = []
    score: float = 0.0

    # Collect flags from supplier node AND its downstream raw materials
    all_flags: list[str] = list(supplier.get("risk_flags") or [])
    for rm_flags in (supplier.get("raw_material_flags") or []):
        for f in (rm_flags or []):
            if f not in all_flags:
                all_flags.append(f)

    for flag in all_flags:
        w = WEIGHTS.get(flag, 0.0)
        if w > 0:
            score += w
            active.append(flag)

    # Tier depth penalty
    tier = supplier.get("tier") or 1
    try:
        tier = int(tier)
    except (TypeError, ValueError):
        tier = 1
    if tier > 1:
        penalty = TIER_PENALTY * (tier - 1)
        score += penalty
        active.append(f"TIER_{tier}_DEPTH (+{penalty:.2f})")

    # Inferred penalty
    if supplier.get("inferred"):
        score += INFERRED_PENALTY
        active.append(f"INFERRED (+{INFERRED_PENALTY})")

    # Propagated risk: if downstream raw material has CONFLICT_MINERAL
    # and parent doesn't, still flag it
    downstream = supplier.get("downstream_flags") or []
    for flag in downstream:
        if flag in ("CONFLICT_MINERAL", "SANCTIONS_RISK") and flag not in active:
            w = WEIGHTS.get(flag, 0) * 0.5  # half-weight for propagated risk
            score += w
            active.append(f"PROPAGATED:{flag}")

    return min(score, 1.0), active


def score_all(db: Neo4jClient, product_sku: str | None = None) -> list[dict]:
    """Fetch all suppliers with their risk flags and compute scores."""
    where = ""
    params: dict = {}
    if product_sku:
        where = """
        WHERE exists {
            MATCH (p:Product {sku: $sku})-[:SUPPLIED_BY|SOURCED_FROM*1..5]->(s)
        }
        """
        params["sku"] = product_sku

    rows = db.run(f"""
        MATCH (s:Supplier)
        {where}
        OPTIONAL MATCH (s)-[:SOURCED_FROM*1..2]->(rm:RawMaterial)
        RETURN s.name        AS name,
               s.country     AS country,
               s.tier        AS tier,
               s.inferred    AS inferred,
               s.risk_flags  AS risk_flags,
               collect(DISTINCT rm.risk_flags) AS raw_material_flags
    """, params)

    # For propagated risk: find what raw materials they source from
    prop_rows = db.run("""
        MATCH (s:Supplier)-[:SOURCED_FROM*1..3]->(n)
        WHERE n.risk_flags IS NOT NULL
        RETURN s.name AS name, collect(DISTINCT n.risk_flags) AS downstream_flags
    """)
    downstream_by_name: dict[str, list[str]] = {}
    for r in prop_rows:
        flags: list[str] = []
        for flag_list in (r.get("downstream_flags") or []):
            for f in (flag_list or []):
                if f not in flags:
                    flags.append(f)
        downstream_by_name[r["name"]] = flags

    results: list[dict] = []
    for row in rows:
        row["downstream_flags"] = downstream_by_name.get(row["name"], [])
        score, active = calc_score(row)
        results.append({
            "name":        row["name"],
            "country":     row["country"],
            "tier":        row["tier"],
            "score":       score,
            "active_flags": active,
            "inferred":    row.get("inferred", False),
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def write_scores(db: Neo4jClient, results: list[dict]) -> int:
    """Write risk_score and risk_summary to each Supplier node."""
    written = 0
    for r in results:
        db.run("""
            MATCH (s:Supplier {name: $name})
            SET s.risk_score   = $score,
                s.risk_summary = $summary
        """, {
            "name":    r["name"],
            "score":   round(r["score"], 4),
            "summary": ", ".join(f for f in r["active_flags"]
                                 if not f.startswith("TIER_") and not f.startswith("INFERRED")),
        })
        written += 1
    return written


def risk_level(score: float) -> str:
    if score >= 0.6: return "HIGH  "
    if score >= 0.3: return "MEDIUM"
    return "LOW   "


def main() -> None:
    parser = argparse.ArgumentParser(description="UC4 Supply Chain Risk Scorer")
    parser.add_argument("--dry-run",  action="store_true", help="Print scores, no Neo4j writes")
    parser.add_argument("--product",  default=None,        help="Filter by product SKU")
    parser.add_argument("--top",      type=int, default=0, help="Show top N only")
    args = parser.parse_args()

    pw = load_credentials()
    db = Neo4jClient(NEO4J_URL, NEO4J_USER, pw)

    log.info("Scoring suppliers%s…", f" for {args.product}" if args.product else "")
    results = score_all(db, args.product)

    if args.top:
        results = results[:args.top]

    print(f"\n{'Supplier':<35} {'Ctry':>4}  {'Tier':>4}  {'Score':>6}  Risk Level  Flags")
    print("─" * 110)
    for r in results:
        flags_short = ", ".join(
            f for f in r["active_flags"]
            if not f.startswith("TIER_") and not f.startswith("INFERRED")
        )[:60]
        inferred_mark = " ~" if r["inferred"] else "  "
        print(
            f"{r['name']:<35}{inferred_mark}"
            f"  {r['country'] or '?':>4}"
            f"  {r['tier'] or '?':>4}"
            f"  {r['score']:>6.3f}"
            f"  {risk_level(r['score'])}"
            f"  {flags_short}"
        )

    high   = sum(1 for r in results if r["score"] >= 0.6)
    medium = sum(1 for r in results if 0.3 <= r["score"] < 0.6)
    low    = sum(1 for r in results if r["score"] < 0.3)
    print(f"\nSummary: {len(results)} suppliers — HIGH:{high}  MEDIUM:{medium}  LOW:{low}")

    if not args.dry_run:
        written = write_scores(db, results)
        log.info("Wrote risk_score to %d supplier nodes in Neo4j.", written)
        print(f"✓ risk_score written to {written} nodes.")
    else:
        print("(dry-run — no Neo4j writes)")


if __name__ == "__main__":
    main()
