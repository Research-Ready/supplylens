#!/usr/bin/env python3
"""
chain_diff.py — Supply chain graph snapshot comparison and change detection.

Captures point-in-time snapshots of the Neo4j supply chain graph, diffs them,
and surfaces: new risk flags, Altman Z threshold crossings, tier changes,
new suppliers, removed relationships, newly-affected events.

Usage:
  python3 src/chain_diff.py --demo             # demo diff (no Neo4j)
  python3 src/chain_diff.py --snapshot         # capture current Neo4j state
  python3 src/chain_diff.py --diff             # diff latest two snapshots
  python3 src/chain_diff.py --alerts           # only CRITICAL/HIGH changes
  python3 src/chain_diff.py --json             # output as JSON
  python3 src/chain_diff.py --demo --json      # demo data as JSON (for dashboard)
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

SNAPSHOT_DIR = Path("snapshots")
NEO4J_URL = "http://10.0.1.114:7474/db/neo4j/tx/commit"

# ── embedded demo snapshots ───────────────────────────────────────────────────

DEMO_SNAPSHOT_A = {
    "timestamp": "2026-07-01T06:00:00Z",
    "label": "2026-07-01 baseline",
    "nodes": {
        "ZF Friedrichshafen": {
            "tier": 1, "country": "Germany",
            "risk_flags": ["SINGLE_SOURCE"], "altman_z": 2.8, "revenue_at_risk": 124.5,
        },
        "Bosch": {
            "tier": 1, "country": "Germany",
            "risk_flags": [], "altman_z": 3.9, "revenue_at_risk": 89.2,
        },
        "SSAB": {
            "tier": 1, "country": "Sweden",
            "risk_flags": ["CARBON_RISK"], "altman_z": 2.1, "revenue_at_risk": 67.3,
        },
        "Infineon Technologies": {
            "tier": 2, "country": "Germany",
            "risk_flags": ["SINGLE_SOURCE"], "altman_z": 3.4, "revenue_at_risk": 45.1,
        },
        "CATL": {
            "tier": 1, "country": "China",
            "risk_flags": ["UFLPA_RISK", "GEOPOLITICAL_RISK"], "altman_z": 3.1, "revenue_at_risk": 820.0,
        },
        "Norilsk Nickel": {
            "tier": 3, "country": "Russia",
            "risk_flags": ["SANCTIONS_OFAC", "GEOPOLITICAL_RISK"], "altman_z": 1.6, "revenue_at_risk": 178.4,
        },
        "Leoni AG": {
            "tier": 2, "country": "Germany",
            "risk_flags": ["GEOPOLITICAL_RISK"], "altman_z": 1.4, "revenue_at_risk": 34.7,
        },
        "SQM": {
            "tier": 3, "country": "Chile",
            "risk_flags": ["WATER_STRESS"], "altman_z": 2.9, "revenue_at_risk": 95.6,
        },
        "TSMC": {
            "tier": 2, "country": "Taiwan",
            "risk_flags": ["GEOPOLITICAL_RISK", "SINGLE_SOURCE"], "altman_z": 4.2, "revenue_at_risk": 340.0,
        },
        "Luminar Technologies": {
            "tier": 1, "country": "USA",
            "risk_flags": ["STARTUP_RISK"], "altman_z": 0.8, "revenue_at_risk": 12.3,
        },
        "Michelin": {
            "tier": 1, "country": "France",
            "risk_flags": [], "altman_z": 3.3, "revenue_at_risk": 44.0,
        },
    },
    "relationships": [
        ["Scania AB", "ZF Friedrichshafen", "SUPPLIED_BY"],
        ["Scania AB", "Bosch", "SUPPLIED_BY"],
        ["Scania AB", "SSAB", "SUPPLIED_BY"],
        ["Scania AB", "CATL", "SUPPLIED_BY"],
        ["Scania AB", "Michelin", "SUPPLIED_BY"],
        ["Bosch", "Infineon Technologies", "SOURCED_FROM"],
        ["CATL", "Norilsk Nickel", "SOURCED_FROM"],
        ["Scania AB", "TSMC", "SOURCED_FROM"],
        ["Scania AB", "Luminar Technologies", "SUPPLIED_BY"],
    ],
    "events": [
        "EVT-SUEZ-CANAL-2024",
        "EVT-TAIWAN-STRAIT-2024",
        "EVT-RED-SEA-HOUTHI-2024",
        "EVT-CATL-UFLPA-2023",
        "EVT-UKRAINE-WIRING-HARNESS-2022",
        "EVT-AUTO-CHIP-SHORTAGE-2021",
    ],
}

DEMO_SNAPSHOT_B = {
    "timestamp": "2026-08-14T06:00:00Z",
    "label": "2026-08-14 current",
    "nodes": {
        "ZF Friedrichshafen": {  # Z dropped into grey zone
            "tier": 1, "country": "Germany",
            "risk_flags": ["SINGLE_SOURCE", "FINANCIAL_STRESS"], "altman_z": 1.95, "revenue_at_risk": 124.5,
        },
        "Bosch": {
            "tier": 1, "country": "Germany",
            "risk_flags": [], "altman_z": 3.7, "revenue_at_risk": 89.2,
        },
        "SSAB": {  # new CBAM flag
            "tier": 1, "country": "Sweden",
            "risk_flags": ["CARBON_RISK", "CBAM_EXPOSURE"], "altman_z": 2.1, "revenue_at_risk": 67.3,
        },
        "Infineon Technologies": {
            "tier": 2, "country": "Germany",
            "risk_flags": ["SINGLE_SOURCE"], "altman_z": 3.4, "revenue_at_risk": 45.1,
        },
        "CATL": {
            "tier": 1, "country": "China",
            "risk_flags": ["UFLPA_RISK", "GEOPOLITICAL_RISK"], "altman_z": 3.1, "revenue_at_risk": 820.0,
        },
        "Norilsk Nickel": {  # Z declined further into distress
            "tier": 3, "country": "Russia",
            "risk_flags": ["SANCTIONS_OFAC", "GEOPOLITICAL_RISK"], "altman_z": 1.3, "revenue_at_risk": 178.4,
        },
        "Leoni AG": {  # approaching distress threshold
            "tier": 2, "country": "Germany",
            "risk_flags": ["GEOPOLITICAL_RISK", "DISTRESS"], "altman_z": 1.1, "revenue_at_risk": 34.7,
        },
        "SQM": {
            "tier": 3, "country": "Chile",
            "risk_flags": ["WATER_STRESS"], "altman_z": 2.9, "revenue_at_risk": 95.6,
        },
        "TSMC": {  # new EXPORT_CTRL flag
            "tier": 2, "country": "Taiwan",
            "risk_flags": ["GEOPOLITICAL_RISK", "SINGLE_SOURCE", "EXPORT_CTRL"], "altman_z": 4.2, "revenue_at_risk": 340.0,
        },
        "Luminar Technologies": {  # deeper distress
            "tier": 1, "country": "USA",
            "risk_flags": ["STARTUP_RISK", "DISTRESS"], "altman_z": 0.6, "revenue_at_risk": 12.3,
        },
        "Michelin": {
            "tier": 1, "country": "France",
            "risk_flags": [], "altman_z": 3.3, "revenue_at_risk": 44.0,
        },
        # NEW suppliers
        "Mobileye Global": {
            "tier": 1, "country": "Israel",
            "risk_flags": ["GEOPOLITICAL_RISK"], "altman_z": 2.7, "revenue_at_risk": 28.0,
        },
        "JSR Corporation": {
            "tier": 3, "country": "Japan",
            "risk_flags": ["SINGLE_SOURCE", "STRATEGIC_MATERIAL"], "altman_z": 3.1, "revenue_at_risk": 220.0,
        },
        "Cryoin Engineering": {
            "tier": 3, "country": "Ukraine",
            "risk_flags": ["GEOPOLITICAL_RISK", "FORCE_MAJEURE"], "altman_z": 0.9, "revenue_at_risk": 85.0,
        },
    },
    "relationships": [
        ["Scania AB", "ZF Friedrichshafen", "SUPPLIED_BY"],
        ["Scania AB", "Bosch", "SUPPLIED_BY"],
        ["Scania AB", "SSAB", "SUPPLIED_BY"],
        ["Scania AB", "CATL", "SUPPLIED_BY"],
        ["Scania AB", "Michelin", "SUPPLIED_BY"],
        ["Bosch", "Infineon Technologies", "SOURCED_FROM"],
        ["CATL", "Norilsk Nickel", "SOURCED_FROM"],
        ["Scania AB", "TSMC", "SOURCED_FROM"],
        ["Scania AB", "Luminar Technologies", "SUPPLIED_BY"],
        ["Scania AB", "Mobileye Global", "SUPPLIED_BY"],     # NEW
        ["TSMC", "JSR Corporation", "SOURCED_FROM"],          # NEW
        ["TSMC", "Cryoin Engineering", "SOURCED_FROM"],       # NEW
    ],
    "events": [
        "EVT-SUEZ-CANAL-2024",
        "EVT-TAIWAN-STRAIT-2024",
        "EVT-RED-SEA-HOUTHI-2024",
        "EVT-CATL-UFLPA-2023",
        "EVT-UKRAINE-WIRING-HARNESS-2022",
        "EVT-AUTO-CHIP-SHORTAGE-2021",
        "EVT-NVIDIA-EXPORT-CTRL-2023",       # NEW
        "EVT-ASML-CHINA-RESTRICTION-2023",   # NEW
        "EVT-NEON-UKRAINE-SHORTAGE-2022",    # NEW
    ],
}


# ── data classes ──────────────────────────────────────────────────────────────

@dataclass
class NodeChange:
    name: str
    change_type: str          # ADDED | REMOVED | MODIFIED
    field: Optional[str] = None
    old_value: object = None
    new_value: object = None
    severity: str = "INFO"    # CRITICAL | HIGH | MEDIUM | INFO

    def to_dict(self):
        return asdict(self)


@dataclass
class DiffResult:
    from_snapshot: str
    to_snapshot: str
    added_nodes: list = field(default_factory=list)
    removed_nodes: list = field(default_factory=list)
    added_relationships: list = field(default_factory=list)
    removed_relationships: list = field(default_factory=list)
    added_events: list = field(default_factory=list)
    removed_events: list = field(default_factory=list)
    changes: list = field(default_factory=list)

    @property
    def critical_count(self):
        return sum(1 for c in self.changes if c.severity == "CRITICAL")

    @property
    def high_count(self):
        return sum(1 for c in self.changes if c.severity == "HIGH")

    def to_dict(self):
        return {
            "from": self.from_snapshot,
            "to": self.to_snapshot,
            "summary": {
                "added_nodes": len(self.added_nodes),
                "removed_nodes": len(self.removed_nodes),
                "added_relationships": len(self.added_relationships),
                "added_events": len(self.added_events),
                "critical": self.critical_count,
                "high": self.high_count,
                "total_changes": len(self.changes),
            },
            "added_nodes": self.added_nodes,
            "removed_nodes": self.removed_nodes,
            "added_relationships": self.added_relationships,
            "removed_relationships": self.removed_relationships,
            "added_events": self.added_events,
            "removed_events": self.removed_events,
            "changes": [c.to_dict() for c in self.changes],
        }


# ── diff logic ────────────────────────────────────────────────────────────────

_FLAG_SEVERITY = {
    "SANCTIONS_OFAC": "CRITICAL",
    "DISTRESS": "CRITICAL",
    "EXPORT_CTRL": "CRITICAL",
    "FORCE_MAJEURE": "CRITICAL",
    "STRATEGIC_MATERIAL": "HIGH",
    "SINGLE_SOURCE": "HIGH",
    "GEOPOLITICAL_RISK": "HIGH",
    "UFLPA_RISK": "HIGH",
    "FINANCIAL_STRESS": "HIGH",
    "CBAM_EXPOSURE": "HIGH",
}


def _flag_sev(flag: str) -> str:
    return _FLAG_SEVERITY.get(flag, "MEDIUM")


def _z_threshold_sev(old_z: float, new_z: float) -> Optional[str]:
    if old_z > 1.81 and new_z <= 1.81:
        return "CRITICAL"   # entered distress zone
    if old_z > 2.99 and new_z <= 2.99:
        return "HIGH"       # entered grey zone
    if abs(old_z - new_z) >= 0.3:
        return "MEDIUM"
    return None


def diff_snapshots(snap_a: dict, snap_b: dict) -> DiffResult:
    result = DiffResult(
        from_snapshot=snap_a.get("label", snap_a.get("timestamp", "?")),
        to_snapshot=snap_b.get("label", snap_b.get("timestamp", "?")),
    )

    nodes_a = snap_a.get("nodes", {})
    nodes_b = snap_b.get("nodes", {})
    rels_a = {tuple(r) for r in snap_a.get("relationships", [])}
    rels_b = {tuple(r) for r in snap_b.get("relationships", [])}
    events_a = set(snap_a.get("events", []))
    events_b = set(snap_b.get("events", []))

    result.added_nodes = [n for n in nodes_b if n not in nodes_a]
    result.removed_nodes = [n for n in nodes_a if n not in nodes_b]
    result.added_relationships = [list(r) for r in rels_b - rels_a]
    result.removed_relationships = [list(r) for r in rels_a - rels_b]
    result.added_events = list(events_b - events_a)
    result.removed_events = list(events_a - events_b)

    for name, data_b in nodes_b.items():
        if name not in nodes_a:
            for flag in data_b.get("risk_flags", []):
                result.changes.append(NodeChange(
                    name=name, change_type="ADDED",
                    field="risk_flag", new_value=flag,
                    severity=_flag_sev(flag),
                ))
            continue

        data_a = nodes_a[name]
        flags_a = set(data_a.get("risk_flags") or [])
        flags_b = set(data_b.get("risk_flags") or [])

        for flag in flags_b - flags_a:
            result.changes.append(NodeChange(
                name=name, change_type="MODIFIED",
                field="risk_flag_added", new_value=flag,
                severity=_flag_sev(flag),
            ))
        for flag in flags_a - flags_b:
            result.changes.append(NodeChange(
                name=name, change_type="MODIFIED",
                field="risk_flag_removed", old_value=flag,
                severity="INFO",
            ))

        z_a = data_a.get("altman_z")
        z_b = data_b.get("altman_z")
        if z_a is not None and z_b is not None and abs(z_a - z_b) > 0.05:
            sev = _z_threshold_sev(z_a, z_b)
            if sev:
                result.changes.append(NodeChange(
                    name=name, change_type="MODIFIED",
                    field="altman_z", old_value=z_a, new_value=z_b,
                    severity=sev,
                ))

        tier_a = data_a.get("tier")
        tier_b = data_b.get("tier")
        if tier_a != tier_b:
            result.changes.append(NodeChange(
                name=name, change_type="MODIFIED",
                field="tier", old_value=tier_a, new_value=tier_b,
                severity="MEDIUM",
            ))

    for name in result.removed_nodes:
        result.changes.append(NodeChange(name=name, change_type="REMOVED", severity="HIGH"))

    sev_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "INFO": 3}
    result.changes.sort(key=lambda c: sev_order.get(c.severity, 4))
    return result


# ── Neo4j fetch ───────────────────────────────────────────────────────────────

def load_snapshot_neo4j(neo4j_pw: str) -> dict:
    import urllib.request
    import base64

    auth = base64.b64encode(f"neo4j:{neo4j_pw}".encode()).decode()
    headers = {"Content-Type": "application/json", "Authorization": "Basic " + auth}

    snap = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "label": f"neo4j-{datetime.now().strftime('%Y%m%d-%H%M')}",
        "nodes": {},
        "relationships": [],
        "events": [],
    }

    queries = {
        "nodes": ("n.name AS name, n.tier AS tier, n.country AS country, "
                  "n.risk_flags AS risk_flags, n.altman_z_score AS altman_z, "
                  "n.revenue_at_risk AS revenue_at_risk",
                  "MATCH (n) WHERE n:Supplier OR n:RawMaterial OR n:Company"),
        "rels": ("a.name AS src, b.name AS dst, type(r) AS rel",
                 "MATCH (a)-[r:SUPPLIED_BY|SOURCED_FROM]->(b)"),
        "events": ("e.event_id AS event_id", "MATCH (e:Event)"),
    }

    for key, (cols_str, match) in queries.items():
        q = f"{match} RETURN {cols_str}"
        req = urllib.request.Request(
            NEO4J_URL,
            data=json.dumps({"statements": [{"statement": q}]}).encode(),
            headers=headers,
            method="POST",
        )
        try:
            r = urllib.request.urlopen(req, timeout=10)
            d = json.loads(r.read())
            cols = d["results"][0]["columns"]
            rows = d["results"][0]["data"]
            for row in rows:
                rec = dict(zip(cols, row["row"]))
                if key == "nodes":
                    name = rec.get("name")
                    if name:
                        snap["nodes"][name] = {
                            "tier": rec.get("tier"),
                            "country": rec.get("country"),
                            "risk_flags": rec.get("risk_flags") or [],
                            "altman_z": rec.get("altman_z"),
                            "revenue_at_risk": rec.get("revenue_at_risk"),
                        }
                elif key == "rels":
                    if rec.get("src") and rec.get("dst"):
                        snap["relationships"].append([rec["src"], rec["dst"], rec["rel"]])
                elif key == "events":
                    if rec.get("event_id"):
                        snap["events"].append(rec["event_id"])
        except Exception as e:
            print(f"  [warn] Neo4j query ({key}): {e}", file=sys.stderr)

    return snap


def save_snapshot(snap: dict) -> Path:
    SNAPSHOT_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = SNAPSHOT_DIR / f"snapshot_{ts}.json"
    path.write_text(json.dumps(snap, indent=2))
    return path


def load_snapshots() -> list:
    if not SNAPSHOT_DIR.exists():
        return []
    paths = sorted(SNAPSHOT_DIR.glob("snapshot_*.json"))
    return [(p, json.loads(p.read_text())) for p in paths]


# ── pretty-print ─────────────────────────────────────────────────────────────

def print_diff(diff: DiffResult, json_out: bool = False, alerts_only: bool = False):
    if json_out:
        print(json.dumps(diff.to_dict(), indent=2))
        return

    R = "\033[91m"; Y = "\033[93m"; G = "\033[92m"
    C = "\033[96m"; B = "\033[1m"; X = "\033[0m"
    SEV_C = {"CRITICAL": R, "HIGH": Y, "MEDIUM": C, "INFO": X}
    SEV_I = {"CRITICAL": "🔴", "HIGH": "🟡", "MEDIUM": "🔵", "INFO": "⚪"}

    print(f"\n{B}Supply Chain Diff{X}")
    print(f"  From : {diff.from_snapshot}")
    print(f"  To   : {diff.to_snapshot}")
    print(f"  {R}{B}{diff.critical_count} CRITICAL{X}  {Y}{diff.high_count} HIGH{X}  "
          f"{len(diff.changes) - diff.critical_count - diff.high_count} other\n")

    if diff.added_nodes:
        print(f"{G}New nodes ({len(diff.added_nodes)}):{X}")
        for n in diff.added_nodes:
            print(f"  + {n}")

    if diff.removed_nodes:
        print(f"{R}Removed nodes:{X}")
        for n in diff.removed_nodes:
            print(f"  - {n}")

    if diff.added_relationships:
        print(f"{G}New relationships ({len(diff.added_relationships)}):{X}")
        for r in diff.added_relationships:
            print(f"  + {r[0]} --[{r[2]}]--> {r[1]}")

    if diff.added_events:
        print(f"{Y}New events:{X}")
        for e in diff.added_events:
            print(f"  ! {e}")

    if diff.changes:
        print(f"\n{B}Node-level changes:{X}")
        for c in diff.changes:
            if alerts_only and c.severity == "INFO":
                continue
            col = SEV_C.get(c.severity, X)
            icon = SEV_I.get(c.severity, " ")
            if c.change_type == "ADDED":
                print(f"  {icon} {col}[{c.severity}]{X} NEW {c.name}: {c.field}={c.new_value}")
            elif c.change_type == "REMOVED":
                print(f"  {icon} {col}[{c.severity}]{X} REMOVED {c.name}")
            elif c.field == "risk_flag_added":
                print(f"  {icon} {col}[{c.severity}]{X} {c.name}: +flag {c.new_value}")
            elif c.field == "risk_flag_removed":
                print(f"  {icon} {col}[{c.severity}]{X} {c.name}: -flag {c.old_value}")
            elif c.field == "altman_z":
                d = "↓" if c.new_value < c.old_value else "↑"
                print(f"  {icon} {col}[{c.severity}]{X} {c.name}: Altman Z {c.old_value:.2f} {d} {c.new_value:.2f}")
            elif c.field == "tier":
                print(f"  {icon} {col}[{c.severity}]{X} {c.name}: tier {c.old_value} → {c.new_value}")
    print()


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Supply chain snapshot diff")
    parser.add_argument("--snapshot", action="store_true", help="Capture Neo4j state now")
    parser.add_argument("--diff", action="store_true", help="Diff latest two snapshots")
    parser.add_argument("--demo", action="store_true", help="Demo mode (no Neo4j)")
    parser.add_argument("--alerts", action="store_true", help="Only CRITICAL/HIGH")
    parser.add_argument("--json", action="store_true", dest="json_out", help="JSON output")
    parser.add_argument("--neo4j-pw", default=os.environ.get("NEO4J_PW", ""))
    args = parser.parse_args()

    if args.demo or (not args.snapshot and not args.diff):
        diff = diff_snapshots(DEMO_SNAPSHOT_A, DEMO_SNAPSHOT_B)
        print_diff(diff, json_out=args.json_out, alerts_only=args.alerts)
        return

    if args.snapshot:
        if not args.neo4j_pw:
            print("Error: --neo4j-pw required (or NEO4J_PW env var)", file=sys.stderr)
            sys.exit(1)
        snap = load_snapshot_neo4j(args.neo4j_pw)
        path = save_snapshot(snap)
        print(f"Saved: {path} ({len(snap['nodes'])} nodes, {len(snap['relationships'])} rels)")
        return

    if args.diff:
        snaps = load_snapshots()
        if len(snaps) < 2:
            print("Need ≥2 snapshots — run --snapshot first", file=sys.stderr)
            sys.exit(1)
        _, a = snaps[-2]
        _, b = snaps[-1]
        diff = diff_snapshots(a, b)
        print_diff(diff, json_out=args.json_out, alerts_only=args.alerts)
        sys.exit(2 if diff.critical_count else 1 if diff.high_count else 0)


if __name__ == "__main__":
    main()
