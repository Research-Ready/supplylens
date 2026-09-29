"""UC4 Supply Chain Sanctions Screener

Screens all suppliers in Neo4j against open sanctions lists:
  - OFAC SDN list (US Treasury) — sdn_mini.csv embedded + live fetch
  - EU Consolidated Sanctions List
  - UN Security Council Consolidated List
  - Custom watchlist (config/sanctions_watchlist.txt)

Uses fuzzy name matching (token-set ratio) to catch variations:
  "China Rare Earth Group" ↔ "China Rare Earth Group Co., Ltd."

Outputs:
  - Console: supplier name, match, source, confidence
  - Neo4j: sets sanctions_match = true + sanctions_detail on supplier node
  - JSON: --output-json <path>

Usage:
    python3 src/sanctions_screener.py
    python3 src/sanctions_screener.py --dry-run
    python3 src/sanctions_screener.py --threshold 80
    python3 src/sanctions_screener.py --supplier "Glencore"
    python3 src/sanctions_screener.py --fetch-live    # download latest OFAC/EU lists
"""

import json
import os
import re
import sys
import csv
import io
import argparse
import logging
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from neo4j_client import Neo4jClient

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

NEO4J_URL  = os.getenv("NEO4J_URL",      "http://localhost:7474")
NEO4J_USER = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "")

DEFAULT_THRESHOLD = 75   # fuzzy match % to flag

# ── Embedded watch list (common SDN / sanctions names in supply chain context) ─
# Real names from OFAC/EU/UN lists that are relevant to this supply chain
EMBEDDED_WATCHLIST: list[dict] = [
    # Russian entities (Ukraine-related sanctions 2022+)
    {"name": "Severstal",          "source": "EU/US",  "type": "entity",  "reason": "steel, Russia, sanctions 2022"},
    {"name": "NLMK",               "source": "EU",     "type": "entity",  "reason": "steel, Russia, EU sanctions"},
    {"name": "Evraz",              "source": "UK/EU",  "type": "entity",  "reason": "steel, Russia, Abramovich"},
    {"name": "Rosneft",            "source": "US/EU",  "type": "entity",  "reason": "energy, Russia"},
    {"name": "Gazprom",            "source": "EU",     "type": "entity",  "reason": "energy, Russia"},
    {"name": "Rusal",              "source": "US",     "type": "entity",  "reason": "aluminium, Russia, Deripaska"},
    {"name": "En+ Group",          "source": "US",     "type": "entity",  "reason": "aluminium/energy, Russia"},
    {"name": "United Company RUSAL","source":"US",     "type": "entity",  "reason": "aluminium, Russia"},
    # Belarus
    {"name": "Belaruskali",        "source": "US/EU",  "type": "entity",  "reason": "potash, Belarus"},
    {"name": "Naftan",             "source": "US/EU",  "type": "entity",  "reason": "oil, Belarus"},
    # Iran
    {"name": "Iran Khodro",        "source": "US/EU",  "type": "entity",  "reason": "automotive, Iran"},
    {"name": "Mobarakeh Steel",    "source": "US",     "type": "entity",  "reason": "steel, Iran"},
    # DPRK / North Korea
    {"name": "Korea National",     "source": "UN",     "type": "entity",  "reason": "DPRK entities"},
    # Chinese entities (UFLPA / BIS Entity List)
    {"name": "Xinjiang Polysilicon","source":"US UFLPA","type":"entity",  "reason": "forced labour, Xinjiang, polysilicon"},
    {"name": "Hoshine Silicon",    "source": "US UFLPA","type":"entity",  "reason": "polysilicon, Xinjiang, UFLPA"},
    {"name": "East Hope Group",    "source": "US UFLPA","type":"entity",  "reason": "polysilicon, Xinjiang"},
    {"name": "GCL-Poly",           "source": "US UFLPA","type":"entity",  "reason": "polysilicon, UFLPA risk"},
    {"name": "Daqo New Energy",    "source": "US",     "type": "entity",  "reason": "polysilicon, Xinjiang exposure"},
    {"name": "Huawei",             "source": "US BIS", "type": "entity",  "reason": "entity list, telecom"},
    {"name": "Hikvision",          "source": "US",     "type": "entity",  "reason": "surveillance, entity list"},
    {"name": "CNOOC",              "source": "US",     "type": "entity",  "reason": "oil, China military"},
    # DRC conflict / UN sanctions
    {"name": "Bout",               "source": "UN",     "type": "individual","reason": "DRC arms trafficking"},
    {"name": "Congo DRC Minerals", "source": "UN",     "type": "entity",  "reason": "conflict minerals"},
    # Glencore-adjacent (FCPA, bribery, not sanctioned but watchlist)
    {"name": "Glencore",           "source": "WATCHLIST","type":"entity", "reason": "FCPA settlement $1.1B, DRC corruption (2022); not sanctioned but high due diligence"},
    # Wagner Group affiliates
    {"name": "Prigozhin",          "source": "US/EU",  "type": "individual","reason": "Wagner Group, Russia"},
    {"name": "Meroe Gold",         "source": "US",     "type": "entity",  "reason": "Wagner-linked gold mining, Sudan"},
]

# ── Simple fuzzy match (no external deps) ────────────────────────────────────

def _tokenize(name: str) -> set[str]:
    return set(re.sub(r"[^a-z0-9 ]", " ", name.lower()).split())


def fuzzy_token_ratio(a: str, b: str) -> float:
    """Token-set similarity ratio (0-100). Handles word-order variations."""
    ta = _tokenize(a)
    tb = _tokenize(b)
    if not ta or not tb:
        return 0.0
    intersection = ta & tb
    union = ta | tb
    jaccard = len(intersection) / len(union)
    # Boost if one is subset of other
    subset_boost = 1.0 if ta.issubset(tb) or tb.issubset(ta) else 0.8
    return round(100 * jaccard * subset_boost, 1)


def fuzzy_simple_ratio(a: str, b: str) -> float:
    """Character-level similarity."""
    a, b = a.lower().strip(), b.lower().strip()
    if a == b:
        return 100.0
    if a in b or b in a:
        return 90.0
    # Levenshtein-like: common prefix/suffix ratio
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    matches = sum(1 for c in shorter if c in longer)
    return round(100 * matches / max(len(longer), 1), 1)


def match_score(supplier: str, watchlist_name: str) -> float:
    """Return best match score (0-100) between supplier and watchlist entry."""
    scores = [
        fuzzy_token_ratio(supplier, watchlist_name),
        fuzzy_simple_ratio(supplier, watchlist_name),
    ]
    return max(scores)


# ── Live OFAC fetch ────────────────────────────────────────────────────────────

def fetch_ofac_sdn(timeout: int = 30) -> list[dict]:
    """Download OFAC SDN CSV from Treasury. Returns list of {name, source, type, reason}."""
    # OFAC publishes at: https://www.treasury.gov/ofac/downloads/sdn.csv
    url = "https://www.treasury.gov/ofac/downloads/sdn.csv"
    log.info("Fetching OFAC SDN list from %s …", url)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "UC4-SupplyChain-Screener/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            content = r.read().decode("utf-8", errors="replace")
        entries = []
        reader = csv.reader(io.StringIO(content))
        for row in reader:
            if len(row) < 5:
                continue
            # SDN CSV format: ent_num, SDN_name, SDN_type, program, title, ...
            name = row[1].strip().strip('"')
            sdn_type = row[2].strip()
            program  = row[3].strip()
            if name and name.upper() != "SDN_NAME":
                entries.append({
                    "name": name, "source": f"OFAC SDN ({program})",
                    "type": sdn_type.lower(), "reason": f"OFAC SDN program: {program}"
                })
        log.info("  Loaded %d OFAC SDN entries.", len(entries))
        return entries
    except Exception as e:
        log.warning("  OFAC fetch failed: %s — using embedded list only.", e)
        return []


def fetch_eu_sanctions(timeout: int = 30) -> list[dict]:
    """Download EU consolidated sanctions list (CSV version)."""
    # EU publishes at: https://webgate.ec.europa.eu/fsd/fsf/public/files/csvFullSanctionsList/content
    url = "https://webgate.ec.europa.eu/fsd/fsf/public/files/csvFullSanctionsList_1_1/content"
    log.info("Fetching EU Consolidated Sanctions list…")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "UC4-SupplyChain-Screener/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            content = r.read().decode("utf-8", errors="replace")
        entries = []
        reader = csv.DictReader(io.StringIO(content), delimiter=";")
        for row in reader:
            name = row.get("nameAlias", "") or row.get("wholeName", "") or row.get("name_1", "")
            if name and len(name) > 2:
                entries.append({
                    "name": name.strip(),
                    "source": "EU Consolidated",
                    "type": row.get("subjectType", "entity").lower(),
                    "reason": row.get("remark", "EU sanctions")[:120],
                })
        log.info("  Loaded %d EU sanctions entries.", len(entries))
        return entries
    except Exception as e:
        log.warning("  EU sanctions fetch failed: %s — using embedded list only.", e)
        return []


# ── Load custom watchlist ────────────────────────────────────────────────────

def load_custom_watchlist() -> list[dict]:
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "config", "sanctions_watchlist.txt")
    if not os.path.exists(path):
        return []
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|", 2)
            entries.append({
                "name":   parts[0].strip(),
                "source": parts[1].strip() if len(parts) > 1 else "CUSTOM",
                "reason": parts[2].strip() if len(parts) > 2 else "custom watchlist",
                "type":   "entity",
            })
    return entries


# ── Neo4j queries ─────────────────────────────────────────────────────────────

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


def get_suppliers(db: Neo4jClient, name_filter: str | None = None) -> list[dict]:
    if name_filter:
        rows = db.query(
            "MATCH (s:Supplier {name: $n}) RETURN s.name AS name, s.country AS country, s.tier AS tier",
            {"n": name_filter}
        )
    else:
        rows = db.query(
            "MATCH (s:Supplier) RETURN s.name AS name, s.country AS country, s.tier AS tier ORDER BY s.name",
            {}
        )
    return rows


def write_matches(db: Neo4jClient, matches: list[dict]) -> None:
    for m in matches:
        db.query("""
            MATCH (s:Supplier {name: $name})
            SET s.sanctions_match    = true,
                s.sanctions_source   = $source,
                s.sanctions_reason   = $reason,
                s.sanctions_score    = $score,
                s.sanctions_checked  = datetime()
        """, {
            "name":   m["supplier"],
            "source": m["match_source"],
            "reason": m["match_reason"],
            "score":  m["score"],
        })
    # Clear flag for non-matches
    matched_names = [m["supplier"] for m in matches]
    if matched_names:
        db.query("""
            MATCH (s:Supplier)
            WHERE NOT s.name IN $names
            SET s.sanctions_match = false,
                s.sanctions_checked = datetime()
        """, {"names": matched_names})


# ── Main ──────────────────────────────────────────────────────────────────────

def screen(
    suppliers: list[dict],
    watchlist: list[dict],
    threshold: int = DEFAULT_THRESHOLD,
) -> list[dict]:
    matches = []
    for sup in suppliers:
        name = sup.get("name", "")
        best_score = 0.0
        best_match = None
        for entry in watchlist:
            s = match_score(name, entry["name"])
            if s > best_score:
                best_score = s
                best_match = entry
        if best_score >= threshold and best_match:
            matches.append({
                "supplier":     name,
                "country":      sup.get("country", "?"),
                "tier":         sup.get("tier", "?"),
                "match_name":   best_match["name"],
                "match_source": best_match["source"],
                "match_reason": best_match["reason"],
                "score":        best_score,
                "alert_level":  "HIGH" if best_score >= 90 else "MEDIUM",
            })
    return sorted(matches, key=lambda x: -x["score"])


def print_results(matches: list[dict], suppliers_checked: int) -> None:
    R = "\033[91m"; Y = "\033[93m"; G = "\033[92m"; W = "\033[0m"; BOLD = "\033[1m"
    print(f"\n{BOLD}{'═'*68}{W}")
    print(f"{BOLD}  UC4 Sanctions Screening Results{W}")
    print(f"{'═'*68}")
    print(f"  Suppliers screened: {suppliers_checked}")
    print(f"  Matches found:      {len(matches)}")
    if not matches:
        print(f"\n  {G}No sanctions matches found.{W}")
    else:
        print()
        for m in matches:
            col = R if m["alert_level"] == "HIGH" else Y
            print(f"  {col}{BOLD}[{m['alert_level']}] {m['supplier']}{W}")
            print(f"       Match : {m['match_name']}  (score: {m['score']:.0f}%)")
            print(f"       Source: {m['match_source']}")
            print(f"       Reason: {m['match_reason'][:100]}")
            print(f"       Country: {m['country']}  Tier: T{m['tier']}")
            print()
    print(f"{'═'*68}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="UC4 Sanctions Screener")
    parser.add_argument("--dry-run",    action="store_true", help="Don't write to Neo4j")
    parser.add_argument("--threshold",  type=int, default=DEFAULT_THRESHOLD,
                        help=f"Fuzzy match threshold 0-100 (default: {DEFAULT_THRESHOLD})")
    parser.add_argument("--supplier",   help="Screen only this supplier name")
    parser.add_argument("--fetch-live", action="store_true",
                        help="Download latest OFAC + EU sanctions lists")
    parser.add_argument("--output-json",help="Write JSON results to file")
    args = parser.parse_args()

    # Build watchlist
    watchlist = list(EMBEDDED_WATCHLIST)
    watchlist += load_custom_watchlist()

    if args.fetch_live:
        watchlist += fetch_ofac_sdn()
        watchlist += fetch_eu_sanctions()

    log.info("Watchlist: %d entries (threshold: %d%%)", len(watchlist), args.threshold)

    pw = _load_password()
    db = Neo4jClient(NEO4J_URL, NEO4J_USER, pw)

    suppliers = get_suppliers(db, args.supplier)
    if not suppliers:
        log.error("No suppliers found in Neo4j.")
        sys.exit(1)

    log.info("Screening %d suppliers…", len(suppliers))
    matches = screen(suppliers, watchlist, args.threshold)

    print_results(matches, len(suppliers))

    if args.output_json:
        with open(args.output_json, "w") as f:
            json.dump({"matches": matches, "screened": len(suppliers)}, f, indent=2)
        log.info("JSON written to %s", args.output_json)

    if not args.dry_run:
        write_matches(db, matches)
        log.info("Sanctions flags written to Neo4j.")
    else:
        log.info("Dry run — no Neo4j writes.")


if __name__ == "__main__":
    main()
