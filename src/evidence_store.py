"""SupplyLens Evidence Store — UC4

Stores and retrieves EDRM-style evidence claims attached to Neo4j supply chain nodes.
Every fact in the graph can have one or more evidence records:
  source_doc      — document name / URL / report title
  source_excerpt  — quoted text passage supporting the claim
  claim           — the extracted fact
  claim_type      — CONTRACT | SANCTIONS | SUPPLY_CHAIN | FINANCIAL | REGULATORY |
                    OPERATIONS | ENVIRONMENTAL | MARKET | RISK | MITIGATION
  confidence      — HIGH | MED | LOW
  reviewed        — bool (human-confirmed)
  reviewer        — who confirmed it
  ingest_date     — ISO date

The EvidenceClaim node is linked to a Supplier/RawMaterial/Product/Event via:
  (claim:EvidenceClaim)-[:EVIDENCE_FOR]->(node)

Usage:
    python3 src/evidence_store.py get "Norilsk Nickel"
    python3 src/evidence_store.py store --node "CATL" --claim "..." --source "..." --type CONTRACT
    python3 src/evidence_store.py review --id <claim-id>
    python3 src/evidence_store.py stats
    python3 src/evidence_store.py export --json
"""

import argparse
import base64
import json
import os
import sys
import uuid
from datetime import date
from typing import Dict, List, Optional

NEO4J_URL  = os.getenv("NEO4J_URL",  "http://localhost:7474")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "")

VALID_TYPES = {
    "CONTRACT", "SANCTIONS", "SUPPLY_CHAIN", "FINANCIAL",
    "REGULATORY", "OPERATIONS", "ENVIRONMENTAL", "MARKET",
    "RISK", "MITIGATION", "LOGISTICS",
}
VALID_CONF = {"HIGH", "MED", "LOW"}


# ── Neo4j helpers ─────────────────────────────────────────────────────────────

def _query(cypher: str, params: dict = None) -> List[dict]:
    """Run a Cypher query. Returns [] if NEO4J_PASS not set (demo mode)."""
    if not NEO4J_PASS:
        return []
    import urllib.request
    auth = base64.b64encode(f"{NEO4J_USER}:{NEO4J_PASS}".encode()).decode()
    body = json.dumps({"statements": [{"statement": cypher, "parameters": params or {}}]})
    req = urllib.request.Request(
        f"{NEO4J_URL}/db/neo4j/tx/commit",
        data=body.encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Basic {auth}"},
        method="POST",
    )
    import urllib.error
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read())
        if d.get("errors"):
            raise RuntimeError(d["errors"][0]["message"])
        rows = d["results"][0]["data"]
        cols = d["results"][0]["columns"]
        return [{cols[i]: row["row"][i] for i in range(len(cols))} for row in rows]
    except urllib.error.URLError as exc:
        raise ConnectionError(f"Neo4j unreachable: {exc}") from exc


# ── Evidence schema setup ─────────────────────────────────────────────────────

def ensure_schema() -> None:
    """Create constraint + index for EvidenceClaim nodes."""
    _query("CREATE CONSTRAINT evidence_id IF NOT EXISTS FOR (e:EvidenceClaim) REQUIRE e.id IS UNIQUE")
    _query("CREATE INDEX evidence_node_name IF NOT EXISTS FOR (e:EvidenceClaim) ON (e.node_name)")


# ── Core CRUD ─────────────────────────────────────────────────────────────────

def store_evidence(
    node_name:    str,
    claim:        str,
    source_doc:   str,
    claim_type:   str   = "SUPPLY_CHAIN",
    confidence:   str   = "MED",
    source_excerpt: str = "",
    source_url:   str   = "",
    ingest_date:  str   = "",
    reviewed:     bool  = False,
    reviewer:     str   = "",
    demo:         bool  = True,
) -> str:
    """Store one evidence claim linked to a named node.

    Returns the claim UUID. Works in demo mode (no Neo4j) — returns UUID only.
    """
    if claim_type not in VALID_TYPES:
        raise ValueError(f"claim_type must be one of {VALID_TYPES}")
    if confidence not in VALID_CONF:
        raise ValueError(f"confidence must be HIGH | MED | LOW")

    claim_id = str(uuid.uuid4())
    today = ingest_date or date.today().isoformat()

    cypher = """
    MERGE (n {name: $node_name})
    CREATE (e:EvidenceClaim {
        id:             $id,
        node_name:      $node_name,
        claim:          $claim,
        source_doc:     $source_doc,
        source_excerpt: $source_excerpt,
        source_url:     $source_url,
        claim_type:     $claim_type,
        confidence:     $confidence,
        ingest_date:    $ingest_date,
        reviewed:       $reviewed,
        reviewer:       $reviewer,
        demo:           $demo
    })
    CREATE (e)-[:EVIDENCE_FOR]->(n)
    RETURN e.id AS id
    """
    try:
        _query(cypher, {
            "node_name": node_name, "id": claim_id,
            "claim": claim, "source_doc": source_doc,
            "source_excerpt": source_excerpt, "source_url": source_url,
            "claim_type": claim_type, "confidence": confidence,
            "ingest_date": today, "reviewed": reviewed,
            "reviewer": reviewer, "demo": demo,
        })
    except ConnectionError:
        pass  # Demo mode — return ID only

    return claim_id


def get_evidence(node_name: str) -> List[dict]:
    """Retrieve all evidence claims for a named node."""
    try:
        return _query(
            """
            MATCH (e:EvidenceClaim)-[:EVIDENCE_FOR]->(n {name: $name})
            RETURN e.id AS id, e.claim AS claim, e.source_doc AS source_doc,
                   e.source_excerpt AS source_excerpt, e.source_url AS source_url,
                   e.claim_type AS claim_type, e.confidence AS confidence,
                   e.ingest_date AS ingest_date, e.reviewed AS reviewed,
                   e.reviewer AS reviewer
            ORDER BY e.confidence DESC, e.ingest_date DESC
            """,
            {"name": node_name},
        )
    except ConnectionError:
        return []


def mark_reviewed(claim_id: str, reviewer: str = "human") -> bool:
    """Mark an evidence claim as human-reviewed."""
    try:
        rows = _query(
            "MATCH (e:EvidenceClaim {id: $id}) SET e.reviewed = true, e.reviewer = $reviewer RETURN e.id AS id",
            {"id": claim_id, "reviewer": reviewer},
        )
        return bool(rows)
    except ConnectionError:
        return False


def delete_evidence(claim_id: str) -> bool:
    """Remove an evidence claim."""
    try:
        _query("MATCH (e:EvidenceClaim {id: $id}) DETACH DELETE e", {"id": claim_id})
        return True
    except ConnectionError:
        return False


def get_pipeline_status() -> List[dict]:
    """Return per-supplier evidence completeness: claim count, reviewed count, types covered."""
    try:
        return _query(
            """
            MATCH (s:Supplier)
            OPTIONAL MATCH (e:EvidenceClaim)-[:EVIDENCE_FOR]->(s)
            RETURN s.name AS supplier, s.country AS country, s.tier AS tier,
                   count(e) AS total_claims,
                   sum(CASE WHEN e.reviewed THEN 1 ELSE 0 END) AS reviewed,
                   collect(DISTINCT e.claim_type) AS types_covered
            ORDER BY s.tier ASC, total_claims DESC
            """
        )
    except ConnectionError:
        return []


def get_stats() -> dict:
    """Return aggregate evidence statistics."""
    try:
        rows = _query(
            """
            MATCH (e:EvidenceClaim)
            RETURN count(e) AS total,
                   sum(CASE WHEN e.reviewed THEN 1 ELSE 0 END) AS reviewed,
                   sum(CASE WHEN e.confidence = 'HIGH' THEN 1 ELSE 0 END) AS high_conf,
                   count(DISTINCT e.node_name) AS nodes_covered
            """
        )
        return rows[0] if rows else {"total": 0, "reviewed": 0, "high_conf": 0, "nodes_covered": 0}
    except ConnectionError:
        return {"total": 0, "reviewed": 0, "high_conf": 0, "nodes_covered": 0}


def export_all(demo_only: bool = False) -> List[dict]:
    """Export all evidence claims as a list of dicts (for JSON output)."""
    try:
        cypher = """
        MATCH (e:EvidenceClaim)-[:EVIDENCE_FOR]->(n)
        WHERE NOT $demo_only OR e.demo = true
        RETURN e.id AS id, e.node_name AS node_name, e.claim AS claim,
               e.source_doc AS source_doc, e.source_url AS source_url,
               e.source_excerpt AS source_excerpt, e.claim_type AS claim_type,
               e.confidence AS confidence, e.ingest_date AS ingest_date,
               e.reviewed AS reviewed, e.reviewer AS reviewer
        ORDER BY e.node_name, e.ingest_date
        """
        return _query(cypher, {"demo_only": demo_only})
    except ConnectionError:
        return []


# ── Bulk seed from hardcoded evidence (demo data) ────────────────────────────

SEED_EVIDENCE = [
    # CATL
    ("CATL", "CATL supplies 230kWh battery pack for Scania L340 BEV at €820M/year contract value.", "Scania Annual Report 2023, p.47", "CONTRACT", "HIGH", "Battery pack contract value €820M/year. 230kWh pack, 800V architecture."),
    ("CATL", "CATL sources cathode material from Shanshan Technology (CN) and Umicore BM (BE).", "CATL Sustainability Report 2023", "SUPPLY_CHAIN", "HIGH", "Cathode active material: Shanshan (China) for NMC, Umicore Belgium for NMC622."),
    ("CATL", "CATL listed as UFLPA risk entity pending review due to Xinjiang-adjacent supply chain.", "US DHS UFLPA Entity List Review 2024", "REGULATORY", "MED", "Xinjiang polysilicon and graphite in battery supply chain flagged."),
    ("CATL", "Single-source status confirmed — no qualified alternative battery supplier at this capacity.", "Scania Procurement Risk Assessment Q3 2024", "RISK", "HIGH", "SINGLE_SOURCE flag: no alternative at 230kWh scale within 18-month qualification window."),
    # Norilsk Nickel
    ("Norilsk Nickel", "Norilsk Nickel produces ~40% of global palladium supply from Polar Division mines.", "USGS Mineral Commodity Summaries 2024", "MARKET", "HIGH", "Global palladium production 2023: 210t. Norilsk Polar Division: 84t (40%)."),
    ("Norilsk Nickel", "OFAC SDN listed entity — all transactions require OFAC license since April 2022.", "US Treasury OFAC SDN List 2022", "SANCTIONS", "HIGH", "Norilsk Nickel added SDN list April 6 2022. OFAC GL-4T general license covers wind-down only."),
    ("Norilsk Nickel", "EU Council Regulation 2022/428 restricts import of ferrous/non-ferrous metals from sanctioned RU entities.", "EU Official Journal L087 2022", "REGULATORY", "HIGH", "Regulation 2022/428 Art. 3g: prohibition on import of iron, steel from Russia."),
    ("Norilsk Nickel", "STMicroelectronics acknowledged palladium exposure, states active diversification to Heraeus.", "STMicro Annual Report 2023, p.82", "SUPPLY_CHAIN", "HIGH", "STMicro: 'actively diversifying palladium sourcing away from Russian-origin material'."),
    # Aptiv
    ("Aptiv", "Aptiv operates wiring harness plant in Lviv, Ukraine employing ~4,000 workers.", "Aptiv 10-K 2022, Note 14", "OPERATIONS", "HIGH", "Boryspil and Lviv plants: 4,000 + 6,200 workers. Lviv 800km from front line."),
    ("Aptiv", "Ukraine plant disruption Feb 2022 — production shifted to Romania/Morocco contingency sites.", "Aptiv Q1 2022 Earnings Call Transcript", "RISK", "HIGH", "CFO: 'We activated Morocco contingency manufacturing within 72 hours of Feb 24 invasion.'"),
    ("Aptiv", "Morocco wiring plant relocation 60% complete as of Q4 2024; full transfer expected 2026.", "Aptiv Q4 2024 Investor Presentation", "MITIGATION", "MED", "Kenitra Morocco facility expansion: 60% of Lviv volume transferred by end 2024."),
    ("Aptiv", "Ukraine conflict cost absorbed: €180M/year (2022–2024); partially offset by force majeure insurance.", "Aptiv 2023 Annual Report, p.61", "FINANCIAL", "HIGH", "Net Ukraine impact 2023: $194M gross, $87M insured, $107M net impact on EBITDA."),
    # Leoni AG
    ("Leoni AG", "Leoni completed financial restructuring Dec 2023 — rights issue €150M, new RCF €250M.", "Leoni AG Press Release 14-Dec-2023", "FINANCIAL", "HIGH", "Rights issue oversubscribed 1.3×. RCF €250M, 3-year tenor, EURIBOR+420bps."),
    ("Leoni AG", "Altman Z-Score 1.71 — distress zone. Net Debt/EBITDA 5.1× exceeds covenant threshold.", "Leoni AG FY2023 Financial Results", "FINANCIAL", "HIGH", "Z-score methodology: Altman (1968) adapted for EU listed industrials."),
    ("Leoni AG", "Leoni Stryi (Lviv region) cable plant: 4,000 employees, produces cable sets for Aptiv.", "Leoni Corporate ESG Report 2022", "OPERATIONS", "HIGH", "Stryi plant: wiring harness sub-assemblies, established 2008, ISO 14001 certified."),
    # STMicroelectronics
    ("STMicroelectronics", "STMicro SPC58x MCUs used in Continental ADAS and Bosch ECU assemblies for Scania.", "Continental AG Supplier Technical Brief 2023", "SUPPLY_CHAIN", "MED", "SPC58 Chorus family: AUTOSAR-compliant, AEC-Q100 Grade 1, used in BCM and ADAS domain controllers."),
    ("STMicroelectronics", "Palladium wire bonding: ~800kg/year consumption; primary source via Heraeus (DE) from Norilsk.", "STMicro 2023 Annual Report, Conflict Minerals Statement", "SUPPLY_CHAIN", "HIGH", "CMR 2023: palladium primary source Heraeus Precious Metals GmbH, who sources from Norilsk."),
    ("STMicroelectronics", "SiC power module revenue €1.5B (2023), growing to €5B target 2027.", "STMicro Capital Markets Day Nov 2023", "MARKET", "HIGH", "SiC addressable market 2027: €7B. STM target market share: ~25%."),
    # Suez Canal
    ("Suez Canal", "Houthi attacks diverted 30% of container traffic to Cape of Good Hope from Nov 2023.", "Drewry World Container Index Weekly Report Jan 2024", "LOGISTICS", "HIGH", "WCI composite: +112% Jan 2024 vs Oct 2023 baseline. Shanghai-Rotterdam +18 days."),
    ("Suez Canal", "Re-routing adds 10–14 days transit time and ~$1,000/TEU additional cost.", "Maersk Customer Advisory 15-Jan-2024", "FINANCIAL", "HIGH", "Fuel surcharge: +$900/TEU Asia-Europe. Transit days: 28 (Suez) vs 42 (Cape)."),
    ("Suez Canal", "CATL battery shipments CN→EU primarily via Suez — supply chain disruption confirmed Q1 2024.", "UC4 Supply Chain Intelligence Analysis 2024", "SUPPLY_CHAIN", "MED", "CATL Ningde → Rotterdam: Red Sea route. Q1 2024 shipments delayed 12–18 days."),
    # SQM
    ("SQM", "SQM Atacama operation produces 180,000 tonnes LCE/year from Salar de Atacama brine.", "SQM Annual Report 2023, Operations Review", "OPERATIONS", "HIGH", "Salar de Atacama: lithium content 1,800 mg/L brine. Evaporation pond area 30km²."),
    ("SQM", "WATER_STRESS: Atacama brine extraction consumes 65% of regional freshwater allocation.", "Chilean Water Authority DGA Report 2022", "ENVIRONMENTAL", "HIGH", "DGA permit volume 1,700 L/s brine. Indigenous Atacameño communities filed legal challenge 2021."),
    ("SQM", "SQM signed lithium supply agreement with CATL 2023 — 100,000 tonnes LCE over 5 years.", "SQM Press Release Jun-2023", "CONTRACT", "HIGH", "5-year offtake agreement. Price linked to LME lithium spot. Delivery: 2024–2028."),
    # Palladium raw material
    ("Palladium", "Global palladium demand 2023: 9.9 million troy oz. Automotive catalysts: 85% of demand.", "Johnson Matthey Platinum Group Metals Review 2024", "MARKET", "HIGH", "Auto catalyst demand: 8.4 moz (85%). Thrifting + BEV transition reducing 3% pa."),
    ("Palladium", "Russian palladium export blocked by OFAC SDN listing — estimated $2B/year trade flow disrupted.", "US Treasury OFAC Impact Assessment Q2 2022", "SANCTIONS", "HIGH", "Norilsk Nickel: 2.6 moz palladium exported pre-sanctions, primarily to EU autocatalyst industry."),
    # ZF Friedrichshafen
    ("ZF Friedrichshafen", "ZF Net Debt/EBITDA 3.8× post-Wabco acquisition — covenant pressure noted in Q3 2024.", "ZF Friedrichshafen Financial Report Q3 2024", "FINANCIAL", "HIGH", "Wabco acquired 2020 for $7B. Integration complete 2023 but leverage remains elevated."),
    ("ZF Friedrichshafen", "ZF TraXon transmission SINGLE_SOURCE for Scania R-series — no qualified alternative.", "Scania Procurement Risk Register 2024", "RISK", "HIGH", "TraXon 12-speed automated gearbox: 4-year qualification; only ZF TraXon passes Scania endurance spec."),
    # SSAB
    ("SSAB", "SSAB HYBRIT green steel pilot production began 2022 at Lulea; commercial scale 2026 target.", "SSAB Press Release Aug-2022", "OPERATIONS", "HIGH", "HYBRIT (Hydrogen Breakthrough Ironmaking Technology): H2-DRI replaces coal blast furnace."),
    ("SSAB", "SSAB Altman Z-Score 3.42 — safe zone; net cash position after divestments.", "SSAB FY2023 Annual Report", "FINANCIAL", "HIGH", "Net cash €180M end 2023. Steel price normalization reduced EBITDA but balance sheet strong."),
]


def seed_demo_evidence() -> int:
    """Load SEED_EVIDENCE into Neo4j. Returns count stored."""
    count = 0
    for args in SEED_EVIDENCE:
        node_name, claim, source_doc, claim_type, confidence, excerpt = args
        try:
            store_evidence(
                node_name=node_name, claim=claim, source_doc=source_doc,
                claim_type=claim_type, confidence=confidence,
                source_excerpt=excerpt, demo=True,
            )
            count += 1
        except Exception as exc:
            print(f"  WARN: {node_name} — {exc}", file=sys.stderr)
    return count


# ── CLI ───────────────────────────────────────────────────────────────────────

def _print_claims(claims: List[dict]) -> None:
    if not claims:
        print("  (no evidence found)")
        return
    for c in claims:
        conf_marker = {"HIGH": "✓✓", "MED": "✓ ", "LOW": "? "}.get(c.get("confidence",""), "  ")
        reviewed = " [REVIEWED]" if c.get("reviewed") else ""
        print(f"  {conf_marker} [{c.get('claim_type','?')}]{reviewed}")
        print(f"     {c.get('claim','')}")
        print(f"     Source: {c.get('source_doc','')}")
        if c.get("source_excerpt"):
            print(f"     Excerpt: \"{c['source_excerpt'][:120]}\"")
        print()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="SupplyLens Evidence Store")
    sub = ap.add_subparsers(dest="cmd")

    p_get = sub.add_parser("get", help="Get evidence for a named node")
    p_get.add_argument("name")

    p_store = sub.add_parser("store", help="Store a new evidence claim")
    p_store.add_argument("--node",    required=True)
    p_store.add_argument("--claim",   required=True)
    p_store.add_argument("--source",  required=True, dest="source_doc")
    p_store.add_argument("--type",    default="SUPPLY_CHAIN", dest="claim_type")
    p_store.add_argument("--conf",    default="MED", dest="confidence")
    p_store.add_argument("--excerpt", default="", dest="source_excerpt")
    p_store.add_argument("--url",     default="", dest="source_url")

    p_review = sub.add_parser("review", help="Mark a claim as reviewed")
    p_review.add_argument("--id",       required=True, dest="claim_id")
    p_review.add_argument("--reviewer", default="human")

    p_stats = sub.add_parser("stats", help="Show aggregate stats")
    p_seed  = sub.add_parser("seed",  help="Seed demo evidence into Neo4j")
    p_status = sub.add_parser("pipeline", help="Show per-supplier pipeline status")

    p_export = sub.add_parser("export", help="Export all evidence as JSON")
    p_export.add_argument("--demo-only", action="store_true")

    args = ap.parse_args()

    if args.cmd == "get":
        claims = get_evidence(args.name)
        print(f"\nEvidence for: {args.name} ({len(claims)} claims)\n")
        _print_claims(claims)

    elif args.cmd == "store":
        claim_id = store_evidence(
            node_name=args.node, claim=args.claim, source_doc=args.source_doc,
            claim_type=args.claim_type, confidence=args.confidence,
            source_excerpt=args.source_excerpt, source_url=args.source_url,
        )
        print(f"Stored: {claim_id}")

    elif args.cmd == "review":
        ok = mark_reviewed(args.claim_id, args.reviewer)
        print("Marked reviewed." if ok else "Claim not found.")

    elif args.cmd == "stats":
        s = get_stats()
        print(f"\nEvidence store stats:")
        print(f"  Total claims:   {s.get('total',0)}")
        print(f"  Reviewed:       {s.get('reviewed',0)}")
        print(f"  High confidence:{s.get('high_conf',0)}")
        print(f"  Nodes covered:  {s.get('nodes_covered',0)}")

    elif args.cmd == "seed":
        print("Seeding demo evidence...")
        n = seed_demo_evidence()
        print(f"Seeded {n} claims.")

    elif args.cmd == "pipeline":
        rows = get_pipeline_status()
        print(f"\n{'Supplier':<35} {'T':>2} {'Claims':>6} {'Reviewed':>8} {'Types'}")
        print("-" * 75)
        for r in rows:
            types = ", ".join(r.get("types_covered") or []) or "—"
            print(f"  {r['supplier']:<33} {r.get('tier',0):>2} {r.get('total_claims',0):>6} "
                  f"{r.get('reviewed',0):>8}   {types}")

    elif args.cmd == "export":
        data = export_all(demo_only=args.demo_only)
        print(json.dumps(data, indent=2))

    else:
        ap.print_help()
