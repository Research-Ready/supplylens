"""Supply Chain Graph Analyzer — UC4

Computes graph topology metrics from Neo4j (or demo data):
  - Degree centrality (most connected nodes)
  - Betweenness centrality approximation (critical intermediaries)
  - Single-point-of-failure detection (no ALT_SOURCE + many dependents)
  - HHI (Herfindahl-Hirschman Index) per product — geographic concentration
  - Longest supply chain paths
  - Network density + diameter

Usage:
    python3 src/graph_analyzer.py [--product SKU] [--json] [--top N]
                                  [--metric centrality|bottleneck|hhi|paths]
"""

import json
import os
import sys
import base64
import urllib.request
import argparse
import math
from collections import defaultdict, deque
from typing import Dict, List, Optional, Set, Tuple


NEO4J_URL  = os.getenv("NEO4J_URL",  "http://localhost:7474")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "")


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


# ── Demo graph data ──────────────────────────────────────────────────────────
# Edges: (from_name, to_name, rel_type)
DEMO_NODES = {
    # products
    "SCANIA-R-500":      {"type":"Product", "country":"SE", "tier":0},
    "SCANIA-L-340-BEV":  {"type":"Product", "country":"SE", "tier":0},
    "SCANIA-G-410":      {"type":"Product", "country":"SE", "tier":0},
    "SCANIA-ENG-DC09":   {"type":"Product", "country":"SE", "tier":0},
    "BTN-001":           {"type":"Product", "country":"NL", "tier":0},
    # T1 suppliers
    "ZF Friedrichshafen":   {"type":"Supplier","country":"DE","tier":1,"risk":"MEDIUM","flags":["GEO"]},
    "Bosch":                {"type":"Supplier","country":"DE","tier":1,"risk":"LOW","flags":[]},
    "SSAB":                 {"type":"Supplier","country":"SE","tier":1,"risk":"LOW","flags":[]},
    "Michelin":             {"type":"Supplier","country":"FR","tier":1,"risk":"LOW","flags":[]},
    "Dana Incorporated":    {"type":"Supplier","country":"US","tier":1,"risk":"LOW","flags":[]},
    "Cummins":              {"type":"Supplier","country":"US","tier":1,"risk":"LOW","flags":[]},
    "Knorr-Bremse":         {"type":"Supplier","country":"DE","tier":1,"risk":"LOW","flags":[]},
    "Voith":                {"type":"Supplier","country":"DE","tier":1,"risk":"LOW","flags":[]},
    "CATL":                 {"type":"Supplier","country":"CN","tier":1,"risk":"HIGH","flags":["UFLPA","GEO"]},
    "Nidec":                {"type":"Supplier","country":"JP","tier":1,"risk":"LOW","flags":[]},
    "ABB E-mobility":       {"type":"Supplier","country":"CH","tier":1,"risk":"LOW","flags":[]},
    "AMS Buttons BV":       {"type":"Supplier","country":"NL","tier":1,"risk":"LOW","flags":[]},
    "Continental AG":       {"type":"Supplier","country":"DE","tier":1,"risk":"LOW","flags":[]},
    "Aptiv":                {"type":"Supplier","country":"IE","tier":1,"risk":"HIGH","flags":["GEO"]},
    "Valeo":                {"type":"Supplier","country":"FR","tier":1,"risk":"LOW","flags":[]},
    "Autoliv":              {"type":"Supplier","country":"SE","tier":1,"risk":"LOW","flags":[]},
    # T2 suppliers
    "Saarstahl AG":              {"type":"Supplier","country":"DE","tier":2,"risk":"LOW","flags":[]},
    "Infineon Technologies":     {"type":"Supplier","country":"DE","tier":2,"risk":"MEDIUM","flags":["GEO"]},
    "Sensata Technologies":      {"type":"Supplier","country":"NL","tier":2,"risk":"LOW","flags":[]},
    "LKAB":                      {"type":"Supplier","country":"SE","tier":2,"risk":"LOW","flags":[]},
    "TimkenSteel":               {"type":"Supplier","country":"US","tier":2,"risk":"LOW","flags":[]},
    "Garrett Motion":            {"type":"Supplier","country":"CH","tier":2,"risk":"MEDIUM","flags":[]},
    "BorgWarner":                {"type":"Supplier","country":"US","tier":2,"risk":"LOW","flags":[]},
    "Haldex":                    {"type":"Supplier","country":"SE","tier":2,"risk":"LOW","flags":[]},
    "Schaeffler":                {"type":"Supplier","country":"DE","tier":2,"risk":"LOW","flags":[]},
    "Umicore Battery Materials": {"type":"Supplier","country":"BE","tier":2,"risk":"LOW","flags":[]},
    "Shanshan Advanced Materials":{"type":"Supplier","country":"CN","tier":2,"risk":"HIGH","flags":["UFLPA","GEO"]},
    "Sumitomo Metal Mining":     {"type":"Supplier","country":"JP","tier":2,"risk":"LOW","flags":[]},
    "SK Enpulse":                {"type":"Supplier","country":"KR","tier":2,"risk":"LOW","flags":[]},
    "Proterial Ltd":             {"type":"Supplier","country":"JP","tier":2,"risk":"HIGH","flags":["GEO"]},
    "STMicroelectronics":        {"type":"Supplier","country":"FR","tier":2,"risk":"LOW","flags":[]},
    "TE Connectivity":           {"type":"Supplier","country":"CH","tier":2,"risk":"LOW","flags":[]},
    "Leoni AG":                  {"type":"Supplier","country":"DE","tier":2,"risk":"HIGH","flags":["GEO"]},
    "Toray Industries":          {"type":"Supplier","country":"JP","tier":2,"risk":"LOW","flags":[]},
    "Shenzhen Metal Co":         {"type":"Supplier","country":"CN","tier":2,"risk":"MEDIUM","flags":["GEO"]},
    # T3 suppliers / raw
    "Ovako":                     {"type":"Supplier","country":"SE","tier":3,"risk":"LOW","flags":[]},
    "North Star BlueScope":      {"type":"Supplier","country":"US","tier":3,"risk":"LOW","flags":[]},
    "SQM":                       {"type":"Supplier","country":"CL","tier":3,"risk":"MEDIUM","flags":["ESG"]},
    "Albemarle":                 {"type":"Supplier","country":"US","tier":3,"risk":"LOW","flags":[]},
    "Ganfeng Lithium":           {"type":"Supplier","country":"CN","tier":3,"risk":"HIGH","flags":["GEO","UFLPA"]},
    "Norilsk Nickel":            {"type":"Supplier","country":"RU","tier":3,"risk":"CRITICAL","flags":["SANC","GEO"]},
    "Glencore":                  {"type":"Supplier","country":"CH","tier":3,"risk":"HIGH","flags":["ESG"]},
    "Codelco":                   {"type":"Supplier","country":"CL","tier":3,"risk":"LOW","flags":[]},
    # raw materials
    "Iron Ore (LKAB)":           {"type":"RawMaterial","country":"SE","tier":4},
    "Lithium Brine (Atacama)":   {"type":"RawMaterial","country":"CL","tier":4},
    "Class I Nickel":            {"type":"RawMaterial","country":"RU","tier":4},
    "Natural Graphite":          {"type":"RawMaterial","country":"CN","tier":4},
    "Cobalt Sulfate (DRC)":      {"type":"RawMaterial","country":"CD","tier":4},
    "NdFeB Magnets":             {"type":"RawMaterial","country":"CN","tier":4},
    "Copper Wire":               {"type":"RawMaterial","country":"CL","tier":4},
    "Palladium (catalytic)":     {"type":"RawMaterial","country":"RU","tier":4},
    "Nylon 6,6 (airbag)":        {"type":"RawMaterial","country":"US","tier":4},
    "Plastic Pellets":           {"type":"RawMaterial","country":"DE","tier":4},
}

# (from, to) — SUPPLIED_BY/SOURCED_FROM edges (direction: product → supplier → raw)
DEMO_EDGES = [
    # R-500 T1
    ("SCANIA-R-500","ZF Friedrichshafen"),("SCANIA-R-500","Bosch"),("SCANIA-R-500","SSAB"),
    ("SCANIA-R-500","Michelin"),("SCANIA-R-500","Dana Incorporated"),("SCANIA-R-500","Cummins"),
    ("SCANIA-R-500","Knorr-Bremse"),("SCANIA-R-500","Voith"),
    ("SCANIA-R-500","Continental AG"),("SCANIA-R-500","Aptiv"),
    ("SCANIA-R-500","Valeo"),("SCANIA-R-500","Autoliv"),
    # G-410 T1 (same as R-500)
    ("SCANIA-G-410","ZF Friedrichshafen"),("SCANIA-G-410","Bosch"),("SCANIA-G-410","SSAB"),
    ("SCANIA-G-410","Dana Incorporated"),("SCANIA-G-410","Knorr-Bremse"),
    ("SCANIA-G-410","Continental AG"),("SCANIA-G-410","Aptiv"),("SCANIA-G-410","Autoliv"),
    # BEV T1
    ("SCANIA-L-340-BEV","CATL"),("SCANIA-L-340-BEV","Nidec"),
    ("SCANIA-L-340-BEV","ABB E-mobility"),("SCANIA-L-340-BEV","Bosch"),
    ("SCANIA-L-340-BEV","Knorr-Bremse"),("SCANIA-L-340-BEV","Continental AG"),
    # DC09 T1
    ("SCANIA-ENG-DC09","Bosch"),("SCANIA-ENG-DC09","Garrett Motion"),
    ("SCANIA-ENG-DC09","Knorr-Bremse"),
    # BTN
    ("BTN-001","AMS Buttons BV"),
    # T2 links
    ("ZF Friedrichshafen","Saarstahl AG"),("ZF Friedrichshafen","Schaeffler"),
    ("Bosch","Infineon Technologies"),("Bosch","Sensata Technologies"),
    ("Bosch","STMicroelectronics"),
    ("SSAB","LKAB"),
    ("Dana Incorporated","TimkenSteel"),
    ("Cummins","Garrett Motion"),("Cummins","BorgWarner"),
    ("Knorr-Bremse","Haldex"),
    ("CATL","Umicore Battery Materials"),("CATL","Shanshan Advanced Materials"),
    ("CATL","Sumitomo Metal Mining"),("CATL","SK Enpulse"),
    ("Nidec","Proterial Ltd"),
    ("Continental AG","Infineon Technologies"),("Continental AG","STMicroelectronics"),
    ("Continental AG","TE Connectivity"),
    ("Aptiv","Leoni AG"),("Aptiv","TE Connectivity"),
    ("Autoliv","Toray Industries"),
    ("AMS Buttons BV","Shenzhen Metal Co"),
    # T3 links
    ("Saarstahl AG","Ovako"),("Saarstahl AG","North Star BlueScope"),
    ("LKAB","Iron Ore (LKAB)"),
    ("SK Enpulse","SQM"),("SK Enpulse","Albemarle"),("SK Enpulse","Ganfeng Lithium"),
    ("Sumitomo Metal Mining","Norilsk Nickel"),
    ("Umicore Battery Materials","Glencore"),
    ("SQM","Lithium Brine (Atacama)"),("Albemarle","Lithium Brine (Atacama)"),
    ("Norilsk Nickel","Class I Nickel"),
    ("Norilsk Nickel","Palladium (catalytic)"),
    ("Shanshan Advanced Materials","Natural Graphite"),
    ("Glencore","Cobalt Sulfate (DRC)"),
    ("Proterial Ltd","NdFeB Magnets"),
    ("Codelco","Copper Wire"),("Leoni AG","Copper Wire"),("Leoni AG","Codelco"),
    ("Toray Industries","Nylon 6,6 (airbag)"),
    ("AMS Buttons BV","Plastic Pellets"),
    ("Shenzhen Metal Co","Palladium (catalytic)"),  # shared palladium dependency
]

# ALT_SOURCE edges (alternative suppliers)
DEMO_ALT_EDGES = [
    ("Knorr-Bremse","Autoliv"),   # overlapping safety components
    ("Shanshan Advanced Materials","Umicore Battery Materials"),
    ("Norilsk Nickel","Codelco"),
    ("CATL","Nidec"),             # partial battery module overlap
]


def load_from_neo4j() -> Tuple[dict, list, list]:
    """Load nodes and edges from Neo4j. Returns (nodes_dict, edges, alt_edges)."""
    # Nodes
    node_rows = _neo4j_query("""
        MATCH (n) WHERE n:Supplier OR n:Product OR n:RawMaterial
        RETURN id(n) AS nid, n.name AS name, labels(n)[0] AS type,
               n.country AS country, n.tier AS tier, n.risk AS risk, n.flags AS flags
    """)
    if not node_rows:
        return DEMO_NODES, DEMO_EDGES, DEMO_ALT_EDGES

    nodes = {}
    for r in node_rows:
        nodes[r["name"]] = {
            "type": r["type"], "country": r["country"] or "XX",
            "tier": int(r["tier"] or 0), "risk": r["risk"] or "LOW",
            "flags": r["flags"] or [],
        }

    # Edges (SUPPLIED_BY + SOURCED_FROM)
    edge_rows = _neo4j_query("""
        MATCH (a)-[r:SUPPLIED_BY|SOURCED_FROM]->(b)
        RETURN a.name AS src, b.name AS dst, type(r) AS rel
    """)
    edges = [(r["src"], r["dst"]) for r in edge_rows if r["src"] and r["dst"]]

    # Alt edges
    alt_rows = _neo4j_query("""
        MATCH (a)-[r:ALT_SOURCE]->(b)
        RETURN a.name AS src, b.name AS dst
    """)
    alt_edges = [(r["src"], r["dst"]) for r in alt_rows if r["src"] and r["dst"]]

    return nodes, edges, alt_edges


# ── Graph algorithms (stdlib only, no networkx) ──────────────────────────────

def build_graph(nodes: dict, edges: list) -> Tuple[Dict, Dict]:
    """Build forward (out) and backward (in) adjacency dicts."""
    out_adj: Dict[str, List[str]] = {n: [] for n in nodes}
    in_adj:  Dict[str, List[str]] = {n: [] for n in nodes}
    for src, dst in edges:
        if src in nodes and dst in nodes:
            out_adj.setdefault(src, []).append(dst)
            in_adj.setdefault(dst, []).append(src)
    return out_adj, in_adj


def degree_centrality(nodes: dict, out_adj: dict, in_adj: dict) -> List[dict]:
    """Degree centrality = (in_deg + out_deg) / (2 * (N-1))."""
    N = len(nodes)
    results = []
    for name in nodes:
        out_d = len(out_adj.get(name, []))
        in_d  = len(in_adj.get(name, []))
        total = out_d + in_d
        score = total / max(1, 2 * (N - 1))
        results.append({
            "name": name, "type": nodes[name].get("type","?"),
            "country": nodes[name].get("country","XX"),
            "tier": nodes[name].get("tier", 0),
            "risk": nodes[name].get("risk","LOW"),
            "in_degree": in_d, "out_degree": out_d,
            "total_degree": total, "centrality": round(score, 5),
        })
    results.sort(key=lambda r: r["total_degree"], reverse=True)
    return results


def bfs_reachable(start: str, out_adj: dict) -> Set[str]:
    """BFS forward reachability from start node."""
    visited = {start}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for nb in out_adj.get(node, []):
            if nb not in visited:
                visited.add(nb)
                queue.append(nb)
    return visited


def approximate_betweenness(nodes: dict, out_adj: dict,
                            in_adj: dict, sample_frac: float = 0.3) -> List[dict]:
    """Approximate betweenness: count how many source→target shortest paths pass through node.

    Samples from product nodes to raw material nodes (most relevant).
    Uses BFS shortest path via predecessors.
    """
    import random
    products = [n for n, d in nodes.items() if d.get("type") == "Product"]
    raw_mat  = [n for n, d in nodes.items() if d.get("type") == "RawMaterial"]

    if not products or not raw_mat:
        return []

    # Track how many paths pass through each node
    pass_count: Dict[str, int] = {n: 0 for n in nodes}
    total_paths = 0

    # BFS shortest path function
    def bfs_shortest_path(src: str, dst: str) -> List[str]:
        prev: Dict[str, Optional[str]] = {src: None}
        queue = deque([src])
        while queue:
            node = queue.popleft()
            if node == dst:
                # reconstruct path
                path = []
                cur = dst
                while cur is not None:
                    path.append(cur)
                    cur = prev.get(cur)
                return list(reversed(path))
            for nb in out_adj.get(node, []):
                if nb not in prev:
                    prev[nb] = node
                    queue.append(nb)
        return []

    random.seed(42)
    pairs = [(p, r) for p in products for r in raw_mat]
    sample_size = max(1, int(len(pairs) * sample_frac))
    sampled = random.sample(pairs, min(sample_size, len(pairs)))

    for src, dst in sampled:
        path = bfs_shortest_path(src, dst)
        if path and len(path) > 2:
            total_paths += 1
            for node in path[1:-1]:  # exclude endpoints
                pass_count[node] = pass_count.get(node, 0) + 1

    results = []
    for name, count in pass_count.items():
        score = count / max(1, total_paths)
        results.append({
            "name": name,
            "type": nodes[name].get("type","?"),
            "country": nodes[name].get("country","XX"),
            "tier": nodes[name].get("tier", 0),
            "risk": nodes[name].get("risk","LOW"),
            "flags": nodes[name].get("flags",[]),
            "path_count": count,
            "betweenness": round(score, 5),
        })
    results.sort(key=lambda r: r["betweenness"], reverse=True)
    return results


def find_bottlenecks(nodes: dict, out_adj: dict, in_adj: dict,
                     alt_edges: list) -> List[dict]:
    """Single points of failure: high in_degree supplier with no ALT_SOURCE.

    A node is a bottleneck if:
      1. Multiple products depend on it (in_degree from Product nodes >= 2)
      2. No ALT_SOURCE relationship exists
      3. Risk is HIGH or CRITICAL
    """
    # Build alt-source set
    alt_set = {src for src, dst in alt_edges}

    # Count products that depend on each node (directly or transitively)
    products = [n for n, d in nodes.items() if d.get("type") == "Product"]

    # For efficiency: for each supplier, count how many products can reach it via BFS backward
    in_adj_bwd = {}  # reverse of out_adj
    for src, targets in out_adj.items():
        for t in targets:
            in_adj_bwd.setdefault(t, []).append(src)

    results = []
    for name, data in nodes.items():
        if data.get("type") not in ("Supplier", "RawMaterial"):
            continue
        # Count products reachable to this node
        product_deps = sum(
            1 for p in products
            if name in bfs_reachable(p, out_adj)
        )
        if product_deps < 1:
            continue
        has_alt = name in alt_set
        risk = data.get("risk", "LOW")
        # Bottleneck score: higher = more critical
        score = (product_deps * 2
                 + (0 if has_alt else 3)
                 + {"LOW":0,"MEDIUM":1,"HIGH":2,"CRITICAL":3}.get(risk,0))
        results.append({
            "name":         name,
            "type":         data.get("type","?"),
            "country":      data.get("country","XX"),
            "tier":         data.get("tier",0),
            "risk":         risk,
            "flags":        data.get("flags",[]),
            "product_deps": product_deps,
            "has_alt":      has_alt,
            "bottleneck_score": score,
            "critical":     product_deps >= 2 and not has_alt and risk in ("HIGH","CRITICAL"),
        })
    results.sort(key=lambda r: r["bottleneck_score"], reverse=True)
    return results


def compute_hhi(nodes: dict, out_adj: dict) -> List[dict]:
    """HHI per product: geographic concentration of its supply chain.

    HHI = sum of (country_share)^2 across countries.
    HHI > 0.25 = highly concentrated.
    """
    products = [(n, d) for n, d in nodes.items() if d.get("type") == "Product"]
    results = []
    for prod, data in products:
        reachable = bfs_reachable(prod, out_adj) - {prod}
        if not reachable:
            continue
        country_counts: Dict[str, int] = {}
        for name in reachable:
            c = nodes[name].get("country","XX")
            country_counts[c] = country_counts.get(c,0) + 1
        total = sum(country_counts.values())
        hhi = sum((count / total) ** 2 for count in country_counts.values())
        dominant = max(country_counts, key=lambda c: country_counts[c])
        results.append({
            "product":    prod,
            "hhi":        round(hhi, 4),
            "hhi_pct":    round(hhi * 100, 1),
            "level":      "HIGH" if hhi > 0.35 else "MEDIUM" if hhi > 0.20 else "LOW",
            "node_count": len(reachable),
            "countries":  len(country_counts),
            "dominant_country": dominant,
            "dominant_pct": round(country_counts[dominant] / total * 100, 1),
            "country_breakdown": sorted(
                [{"country": c, "count": n, "share_pct": round(n/total*100,1)}
                 for c, n in country_counts.items()],
                key=lambda x: x["count"], reverse=True
            ),
        })
    results.sort(key=lambda r: r["hhi"], reverse=True)
    return results


def longest_paths(nodes: dict, out_adj: dict, max_paths: int = 10) -> List[dict]:
    """Find longest paths in the supply chain (product → raw material)."""
    products = [n for n, d in nodes.items() if d.get("type") == "Product"]
    raw_mat  = [n for n, d in nodes.items() if d.get("type") == "RawMaterial"]
    raw_set  = set(raw_mat)

    def dfs_longest(start: str, visited: Set[str]) -> List[List[str]]:
        if start in raw_set:
            return [[start]]
        neighbors = out_adj.get(start, [])
        if not neighbors:
            return [[start]]
        all_paths = []
        for nb in neighbors:
            if nb not in visited:
                sub = dfs_longest(nb, visited | {nb})
                for path in sub:
                    all_paths.append([start] + path)
        if not all_paths:
            return [[start]]
        return all_paths

    found = []
    for prod in products:
        paths = dfs_longest(prod, {prod})
        paths.sort(key=len, reverse=True)
        for path in paths[:3]:  # top 3 longest per product
            found.append({
                "path": path,
                "length": len(path),
                "product": prod,
                "terminus": path[-1] if path else None,
            })

    found.sort(key=lambda r: r["length"], reverse=True)
    return found[:max_paths]


def network_stats(nodes: dict, edges: list, alt_edges: list) -> dict:
    """Overall network statistics."""
    suppliers = [n for n, d in nodes.items() if d.get("type") == "Supplier"]
    products  = [n for n, d in nodes.items() if d.get("type") == "Product"]
    raw       = [n for n, d in nodes.items() if d.get("type") == "RawMaterial"]
    countries = {d.get("country","XX") for d in nodes.values()}
    high_risk = [n for n, d in nodes.items() if d.get("risk") in ("HIGH","CRITICAL")]
    max_possible_edges = len(nodes) * (len(nodes) - 1)
    density = len(edges) / max_possible_edges if max_possible_edges else 0
    return {
        "total_nodes":      len(nodes),
        "suppliers":        len(suppliers),
        "products":         len(products),
        "raw_materials":    len(raw),
        "total_edges":      len(edges),
        "alt_source_edges": len(alt_edges),
        "countries":        len(countries),
        "high_risk_nodes":  len(high_risk),
        "network_density":  round(density, 5),
    }


def run_full_analysis(product_filter: Optional[str] = None) -> dict:
    nodes, edges, alt_edges = load_from_neo4j()
    if not nodes:
        nodes, edges, alt_edges = DEMO_NODES, DEMO_EDGES, DEMO_ALT_EDGES

    # Filter by product if requested
    if product_filter:
        out_adj_temp, _ = build_graph(nodes, edges)
        reachable = bfs_reachable(product_filter, out_adj_temp)
        nodes = {k: v for k, v in nodes.items() if k in reachable or k == product_filter}
        edges = [(s, d) for s, d in edges if s in nodes and d in nodes]

    out_adj, in_adj = build_graph(nodes, edges)

    return {
        "stats":         network_stats(nodes, edges, alt_edges),
        "centrality":    degree_centrality(nodes, out_adj, in_adj)[:20],
        "betweenness":   approximate_betweenness(nodes, out_adj, in_adj)[:20],
        "bottlenecks":   find_bottlenecks(nodes, out_adj, in_adj, alt_edges)[:20],
        "hhi":           compute_hhi(nodes, out_adj),
        "longest_paths": longest_paths(nodes, out_adj),
    }


def print_report(data: dict, top: int = 10) -> None:
    s = data["stats"]
    print("=" * 90)
    print(f"  SUPPLY CHAIN GRAPH ANALYSIS — UC4")
    print("=" * 90)
    print(f"  Nodes: {s['total_nodes']} ({s['suppliers']} suppliers, {s['products']} products, {s['raw_materials']} raw)")
    print(f"  Edges: {s['total_edges']} | ALT_SOURCE: {s['alt_source_edges']} | Countries: {s['countries']} | Density: {s['network_density']:.5f}")
    print(f"  High-risk nodes: {s['high_risk_nodes']}")
    print()

    print("  TOP DEGREE CENTRALITY (most connected nodes):")
    print(f"  {'Name':<35} {'Type':<12} {'T':>2} {'In':>4} {'Out':>4} {'Total':>6} {'Score'}")
    print("  " + "-" * 78)
    for r in data["centrality"][:top]:
        print(f"  {r['name']:<35} {r['type']:<12} {r['tier']:>2} {r['in_degree']:>4} {r['out_degree']:>4} {r['total_degree']:>6} {r['centrality']:.4f}")

    print()
    print("  TOP BETWEENNESS (critical intermediaries — removing disrupts most paths):")
    print(f"  {'Name':<35} {'Type':<12} {'Paths':>6} {'Score'}")
    print("  " + "-" * 65)
    for r in data["betweenness"][:top]:
        if r["path_count"] == 0:
            continue
        flags = " ".join(f"[{f}]" for f in r.get("flags",[]))
        print(f"  {r['name']:<35} {r['type']:<12} {r['path_count']:>6} {r['betweenness']:.4f}  {flags}")

    print()
    print("  BOTTLENECKS (single points of failure — no alt + multiple product deps):")
    critical = [r for r in data["bottlenecks"] if r["critical"]]
    for r in critical[:top]:
        flags = " ".join(f"[{f}]" for f in r.get("flags",[]))
        print(f"  !! {r['name']:<33} T{r['tier']} {r['country']} {r['risk']:<8} depends:{r['product_deps']} {flags}")

    print()
    print("  HHI — Geographic Concentration per Product:")
    for r in data["hhi"]:
        bar = "█" * int(r["hhi"] * 40)
        print(f"  {r['product']:<25} HHI={r['hhi']:.3f} {bar:<16} {r['level']:<6} dominant: {r['dominant_country']} ({r['dominant_pct']:.0f}%)")

    print()
    print("  LONGEST SUPPLY CHAIN PATHS:")
    for r in data["longest_paths"][:5]:
        print(f"  [{r['length']} hops] {' → '.join(r['path'])}")
    print("=" * 90)


def main():
    parser = argparse.ArgumentParser(description="Supply chain graph analyzer")
    parser.add_argument("--product",  default=None, help="Filter by product SKU")
    parser.add_argument("--json",     action="store_true")
    parser.add_argument("--top",      type=int, default=10)
    parser.add_argument("--metric",   default="all",
                        choices=["all","centrality","betweenness","bottleneck","hhi","paths"])
    args = parser.parse_args()

    data = run_full_analysis(args.product)

    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print_report(data, args.top)


if __name__ == "__main__":
    main()
