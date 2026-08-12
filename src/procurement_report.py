#!/usr/bin/env python3
"""
procurement_report.py — Generate a self-contained HTML procurement intelligence report
for a product's supply chain. Pulls from Neo4j, runs all analyses inline,
and writes a printable, shareable HTML file.

Usage:
    python3 src/procurement_report.py --product SCANIA-R-500 --out docs/report_scania.html
    python3 src/procurement_report.py --product BTN-001 --out docs/report_buttons.html
    python3 src/procurement_report.py --all --out docs/                # one report per product
    python3 src/procurement_report.py --dry-run                         # demo data only

The generated report includes:
  - Executive summary (KPIs, risk level, total exposure)
  - Supply chain map (tier table)
  - Financial exposure (contract values, lead times)
  - Resilience scorecard (6 dimensions)
  - Sanctions screening results
  - Disruption scenario analysis
  - Certification compliance table
  - Recommendations (prioritised action items)
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime

# ── Config ───────────────────────────────────────────────────────────────────
NEO4J_URL  = os.environ.get("NEO4J_URL",   "http://10.0.1.114:7474")
NEO4J_USER = os.environ.get("NEO4J_USER",  "neo4j")
NEO4J_PASS = os.environ.get("NEO4J_PASS",  "")

KEEPASS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "passwords.kdbx")
KEEPASS_MASTER = "SupplyChainBaby100!"


def _get_pass() -> str:
    global NEO4J_PASS
    if NEO4J_PASS:
        return NEO4J_PASS
    try:
        from pykeepass import PyKeePass
        kp = PyKeePass(KEEPASS_PATH, password=KEEPASS_MASTER)
        e = kp.find_entries(title="Neo4j", first=True)
        if e:
            NEO4J_PASS = e.password
            return NEO4J_PASS
    except Exception:
        pass
    import getpass
    NEO4J_PASS = getpass.getpass("Neo4j password: ")
    return NEO4J_PASS


def neo4j(cypher: str, params: dict = None) -> list[dict]:
    pw = _get_pass()
    auth = base64.b64encode(f"{NEO4J_USER}:{pw}".encode()).decode()
    payload = json.dumps({
        "statements": [{"statement": cypher, "parameters": params or {}}]
    }).encode()
    req = urllib.request.Request(
        f"{NEO4J_URL}/db/neo4j/tx/commit",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Basic {auth}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    if data.get("errors"):
        raise RuntimeError(data["errors"][0]["message"])
    cols = data["results"][0]["columns"]
    return [dict(zip(cols, row["row"])) for row in data["results"][0]["data"]]


def fmt_eur(n):
    if n is None:
        return "N/A"
    if n >= 1e9:
        return f"€{n/1e9:.1f}B"
    if n >= 1e6:
        return f"€{n/1e6:.0f}M"
    if n >= 1e3:
        return f"€{n/1e3:.0f}K"
    return f"€{n:.0f}"


def fmt_num(n):
    if n is None:
        return "—"
    if n >= 1e6:
        return f"{n/1e6:.1f}M"
    if n >= 1e3:
        return f"{n/1e3:.0f}K"
    return str(int(n))


def risk_color(score):
    if score is None:
        return "#718096"
    if score >= 0.7:
        return "#fc8181"
    if score >= 0.4:
        return "#f6ad55"
    return "#68d391"


def risk_label(score):
    if score is None:
        return "UNKNOWN"
    if score >= 0.7:
        return "HIGH"
    if score >= 0.4:
        return "MEDIUM"
    return "LOW"


# ── Data fetching ─────────────────────────────────────────────────────────────

def fetch_product(sku: str) -> dict | None:
    rows = neo4j("MATCH (p:Product {sku:$sku}) RETURN p.name AS name, p.sku AS sku, "
                 "p.category AS category", {"sku": sku})
    return rows[0] if rows else None


def fetch_all_products() -> list[dict]:
    return neo4j("MATCH (p:Product) RETURN p.name AS name, p.sku AS sku, p.category AS category")


def fetch_supply_chain(sku: str, max_depth: int = 5) -> list[dict]:
    return neo4j("""
    MATCH path = (p:Product {sku:$sku})-[:SUPPLIED_BY|SOURCED_FROM*1..5]->(n)
    WITH [node IN nodes(path) | {
        name: coalesce(node.name, node.sku),
        tier: node.tier,
        country: node.country,
        risk_score: node.risk_score,
        risk_flags: node.risk_flags,
        annual_revenue_eur: node.annual_revenue_eur,
        employee_count: node.employee_count,
        type: labels(node)[0],
        sanctions_match: node.sanctions_match
    }] AS chain,
    [rel IN relationships(path) | {
        type: type(rel),
        component: rel.component,
        contract_value_eur: rel.contract_value_eur,
        lead_time_days: rel.lead_time_days,
        single_source: rel.single_source,
        risk_flags: rel.risk_flags
    }] AS rels,
    length(path) AS depth
    RETURN chain, rels, depth
    ORDER BY depth
    """, {"sku": sku})


def fetch_t1_contracts(sku: str) -> list[dict]:
    return neo4j("""
    MATCH (p:Product {sku:$sku})-[r:SUPPLIED_BY]->(s:Supplier)
    RETURN s.name AS supplier, s.country AS country, s.tier AS tier,
           r.component AS component, r.contract_value_eur AS contract_value,
           r.lead_time_days AS lead_time, r.single_source AS single_source,
           r.risk_flags AS risk_flags, r.contract_end AS contract_end,
           s.annual_revenue_eur AS supplier_revenue, s.risk_score AS risk_score,
           s.employee_count AS employees
    ORDER BY r.contract_value_eur DESC NULLS LAST
    """, {"sku": sku})


def fetch_certifications(sku: str) -> list[dict]:
    return neo4j("""
    MATCH (p:Product {sku:$sku})-[:SUPPLIED_BY|SOURCED_FROM*1..3]->(s:Supplier)-[:CERTIFIED_BY]->(c:Certificate)
    RETURN DISTINCT s.name AS supplier, s.tier AS tier, c.name AS cert, c.issuer AS issuer,
           c.valid_until AS valid_until
    ORDER BY s.tier, s.name
    """, {"sku": sku})


def fetch_events(sku: str) -> list[dict]:
    return neo4j("""
    MATCH (p:Product {sku:$sku})-[:SUPPLIED_BY|SOURCED_FROM*1..5]->(s:Supplier)-[:AFFECTED_BY]->(e:Event)
    RETURN DISTINCT e.name AS event, e.date AS date, e.type AS type,
           e.impact AS impact, s.name AS supplier, e.description AS description
    ORDER BY e.date DESC
    """, {"sku": sku})


def fetch_risk_suppliers(sku: str) -> list[dict]:
    return neo4j("""
    MATCH (p:Product {sku:$sku})-[:SUPPLIED_BY|SOURCED_FROM*1..5]->(s:Supplier)
    WHERE s.risk_score IS NOT NULL OR s.risk_flags IS NOT NULL
    RETURN DISTINCT s.name AS name, s.country AS country, s.tier AS tier,
           s.risk_score AS risk_score, s.risk_flags AS risk_flags,
           s.annual_revenue_eur AS revenue, s.sanctions_match AS sanctioned
    ORDER BY s.risk_score DESC NULLS LAST, s.tier
    LIMIT 20
    """, {"sku": sku})


def fetch_alternatives(sku: str) -> list[dict]:
    return neo4j("""
    MATCH (p:Product {sku:$sku})-[:SUPPLIED_BY|SOURCED_FROM*1..3]->(s:Supplier)-[:ALT_SOURCE]->(alt:Supplier)
    RETURN s.name AS primary_supplier, alt.name AS alternative,
           alt.country AS alt_country, alt.annual_revenue_eur AS alt_revenue
    ORDER BY s.name
    """, {"sku": sku})


# ── Resilience scoring (inline — simplified version) ─────────────────────────

def compute_resilience(sku: str) -> dict:
    try:
        t1 = neo4j("""
        MATCH (p:Product {sku:$sku})-[r:SUPPLIED_BY]->(s:Supplier)
        RETURN s.country AS country, r.contract_value_eur AS cv,
               s.risk_flags AS flags, r.lead_time_days AS lead
        """, {"sku": sku})

        t2 = neo4j("""
        MATCH (p:Product {sku:$sku})-[:SUPPLIED_BY]->(s1:Supplier)-[:SOURCED_FROM]->(s2:Supplier)
        RETURN s2.name AS name LIMIT 30
        """, {"sku": sku})

        t3 = neo4j("""
        MATCH (p:Product {sku:$sku})-[:SUPPLIED_BY]->(s1)-[:SOURCED_FROM]->(s2)-[:SOURCED_FROM]->(s3)
        RETURN s3.name AS name LIMIT 20
        """, {"sku": sku})

        # Geo diversity (1 - HHI)
        total_cv = sum(r.get("cv") or 0 for r in t1) or 1
        by_country: dict[str, float] = {}
        for r in t1:
            c = r.get("country") or "ZZ"
            by_country[c] = by_country.get(c, 0) + (r.get("cv") or 0)
        hhi = sum((v / total_cv) ** 2 for v in by_country.values())
        geo = max(0, 1 - hhi)

        # Single source
        ss_count = sum(1 for r in t1 if "SINGLE_SOURCE" in (r.get("flags") or []))
        single_source = 1 - (ss_count / max(len(t1), 1))

        # Risk exposure (fraction of value from low-risk countries)
        risky_countries = {"CN", "RU", "IR", "BY", "KP"}
        risky_cv = sum(r.get("cv") or 0 for r in t1 if r.get("country") in risky_countries)
        risk_exp = 1 - (risky_cv / total_cv)

        # Tier coverage
        tier_pts = {0: 0, 1: 0.25, 2: 0.6, 3: 1.0}
        t1_present = 1 if t1 else 0
        t2_present = 1 if t2 else 0
        t3_present = 1 if t3 else 0
        tier_cov = (tier_pts.get(t1_present, 0) + tier_pts.get(t2_present, 0) + tier_pts.get(t3_present, 0)) / 3

        # Lead time
        leads = [r.get("lead") for r in t1 if r.get("lead")]
        avg_lead = sum(leads) / len(leads) if leads else 60
        lead_score = max(0, 1 - avg_lead / 180)

        # Composite
        weights = {"geo": 0.20, "single_source": 0.25, "risk_exp": 0.25,
                   "tier_cov": 0.15, "lead": 0.10, "cert": 0.05}
        cert_score = 0.5  # default (can't easily compute inline)
        composite = (
            geo * weights["geo"] +
            single_source * weights["single_source"] +
            risk_exp * weights["risk_exp"] +
            tier_cov * weights["tier_cov"] +
            lead_score * weights["lead"] +
            cert_score * weights["cert"]
        )

        return {
            "score": composite,
            "dimensions": {
                "Geo Diversity": geo,
                "Single Source": single_source,
                "Risk Exposure": risk_exp,
                "Tier Coverage": tier_cov,
                "Lead Time": lead_score,
                "Certification": cert_score,
            },
            "avg_lead_days": avg_lead,
            "t1_count": len(t1),
            "t2_count": len(t2),
            "t3_count": len(t3),
            "single_source_count": ss_count,
            "countries": list(by_country.keys()),
        }
    except Exception as exc:
        return {"score": None, "error": str(exc)}


# ── HTML report generator ─────────────────────────────────────────────────────

HTML_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; color: #1a202c; background: #f7fafc; }
@media print { body { background: white; } .no-print { display: none; } }

.page { max-width: 1100px; margin: 0 auto; padding: 24px; }
.cover { background: linear-gradient(135deg, #1a365d 0%, #2d3748 100%); color: white; padding: 48px 40px; border-radius: 8px; margin-bottom: 24px; }
.cover h1 { font-size: 28px; font-weight: 700; margin-bottom: 8px; }
.cover .subtitle { font-size: 16px; opacity: 0.8; margin-bottom: 24px; }
.cover .meta { font-size: 12px; opacity: 0.6; }
.cover .meta span { margin-right: 24px; }

.section { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; margin-bottom: 20px; }
.section h2 { font-size: 15px; font-weight: 700; color: #2d3748; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #e2e8f0; display: flex; align-items: center; gap: 8px; }
.section h2 .num { background: #3182ce; color: white; width: 22px; height: 22px; border-radius: 4px; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; }

.kpi-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 16px; }
.kpi { background: #f7fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; text-align: center; }
.kpi-v { font-size: 22px; font-weight: 700; }
.kpi-l { font-size: 11px; color: #718096; margin-top: 4px; }
.kpi-v.red { color: #e53e3e; }
.kpi-v.orange { color: #dd6b20; }
.kpi-v.green { color: #38a169; }
.kpi-v.blue { color: #3182ce; }

table { width: 100%; border-collapse: collapse; font-size: 12px; }
th { background: #edf2f7; padding: 8px 10px; text-align: left; font-weight: 600; color: #4a5568; border-bottom: 2px solid #e2e8f0; }
td { padding: 7px 10px; border-bottom: 1px solid #f0f4f8; vertical-align: top; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: #f7fafc; }

.badge { display: inline-block; padding: 2px 7px; border-radius: 4px; font-size: 10px; font-weight: 700; }
.badge-red { background: #fed7d7; color: #c53030; }
.badge-orange { background: #feebc8; color: #c05621; }
.badge-green { background: #c6f6d5; color: #276749; }
.badge-blue { background: #bee3f8; color: #2b6cb0; }
.badge-gray { background: #edf2f7; color: #4a5568; }

.flag-chip { display: inline-block; background: #fff5f5; color: #c53030; border: 1px solid #fed7d7; border-radius: 3px; padding: 1px 5px; font-size: 10px; margin: 1px; font-weight: 600; }

.resilience-bar { height: 12px; border-radius: 6px; background: #edf2f7; margin-top: 3px; }
.resilience-fill { height: 100%; border-radius: 6px; }

.tier-tree { font-family: monospace; font-size: 12px; line-height: 1.8; background: #f7fafc; padding: 12px; border-radius: 6px; border: 1px solid #e2e8f0; }

.reco { padding: 8px 12px; border-radius: 6px; margin-bottom: 6px; display: flex; align-items: flex-start; gap: 10px; font-size: 12px; }
.reco.critical { background: #fff5f5; border-left: 4px solid #e53e3e; }
.reco.high { background: #fffaf0; border-left: 4px solid #dd6b20; }
.reco.medium { background: #f0fff4; border-left: 4px solid #38a169; }
.reco-icon { font-size: 16px; flex-shrink: 0; }

.radar-svg { display: block; margin: 0 auto; }

.chart-bar { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.chart-bar-label { width: 120px; font-size: 11px; color: #4a5568; text-align: right; flex-shrink: 0; }
.chart-bar-track { flex: 1; height: 16px; background: #edf2f7; border-radius: 4px; overflow: hidden; }
.chart-bar-fill { height: 100%; border-radius: 4px; display: flex; align-items: center; padding-left: 4px; font-size: 10px; color: white; font-weight: 600; }
.chart-bar-val { width: 40px; font-size: 11px; color: #4a5568; }

footer { text-align: center; color: #a0aec0; font-size: 11px; margin-top: 24px; padding-top: 16px; border-top: 1px solid #e2e8f0; }
"""


def bar_color(score):
    if score >= 0.7:
        return "#68d391"
    if score >= 0.4:
        return "#f6ad55"
    return "#fc8181"


def render_resilience_radar_svg(dims: dict) -> str:
    """Render a simple 6-axis radar chart as inline SVG."""
    labels = list(dims.keys())
    scores = [dims[l] for l in labels]
    n = len(labels)
    cx, cy, r = 120, 120, 90

    import math
    def pt(i, val, max_r=r):
        angle = 2 * math.pi * i / n - math.pi / 2
        x = cx + max_r * val * math.cos(angle)
        y = cy + max_r * val * math.sin(angle)
        return x, y

    # Background rings
    rings = ""
    for v in [0.25, 0.5, 0.75, 1.0]:
        pts = " ".join(f"{pt(i, v)[0]:.1f},{pt(i, v)[1]:.1f}" for i in range(n))
        rings += f'<polygon points="{pts}" fill="none" stroke="#e2e8f0" stroke-width="0.8"/>'

    # Axes
    axes = ""
    for i, label in enumerate(labels):
        x, y = pt(i, 1.0)
        axes += f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="#e2e8f0" stroke-width="1"/>'
        lx, ly = pt(i, 1.22)
        anchor = "middle"
        if lx < cx - 10:
            anchor = "end"
        elif lx > cx + 10:
            anchor = "start"
        axes += f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" font-size="9" fill="#4a5568">{label}</text>'

    # Score polygon
    score_pts = " ".join(f"{pt(i, scores[i])[0]:.1f},{pt(i, scores[i])[1]:.1f}" for i in range(n))
    poly = f'<polygon points="{score_pts}" fill="#3182ce" fill-opacity="0.25" stroke="#3182ce" stroke-width="2"/>'

    # Score dots
    dots = ""
    for i, s in enumerate(scores):
        x, y = pt(i, s)
        dots += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#3182ce"/>'

    return f'<svg width="240" height="240" viewBox="0 0 240 240" class="radar-svg">{rings}{axes}{poly}{dots}</svg>'


def render_dim_bars(dims: dict) -> str:
    out = ""
    for label, score in dims.items():
        pct = int(score * 100)
        color = bar_color(score)
        out += f"""
        <div class="chart-bar">
          <div class="chart-bar-label">{label}</div>
          <div class="chart-bar-track">
            <div class="chart-bar-fill" style="width:{pct}%;background:{color}">{pct}%</div>
          </div>
          <div class="chart-bar-val">{pct}%</div>
        </div>"""
    return out


def build_recommendations(contracts: list, resilience: dict, events: list, alternatives: list) -> list[tuple]:
    """Return list of (level, text) recommendation tuples."""
    recos = []

    # Single-source suppliers
    ss_suppliers = [c for c in contracts if c.get("single_source")]
    for c in ss_suppliers:
        alts = [a for a in alternatives if a.get("primary_supplier") == c.get("supplier")]
        if alts:
            recos.append(("high", f"Single-source risk: {c['supplier']} (contract {fmt_eur(c.get('contract_value'))}). "
                                  f"Alternative suppliers identified: {', '.join(a['alternative'] for a in alts)}. Initiate qualification."))
        else:
            recos.append(("critical", f"Single-source risk: {c['supplier']} (contract {fmt_eur(c.get('contract_value'))}). "
                                      f"No qualified alternative. Urgently identify and qualify backup supplier."))

    # High lead times
    long_lead = [c for c in contracts if (c.get("lead_time") or 0) > 90]
    for c in long_lead:
        recos.append(("high", f"Long lead time: {c['supplier']} — {c.get('lead_time')}d. "
                              f"Consider strategic inventory buffer or nearshore alternative."))

    # Geopolitical exposure
    geo_risk = [c for c in contracts if c.get("country") in ("CN", "RU", "IR", "BY")]
    for c in geo_risk:
        recos.append(("critical", f"Geopolitical exposure: {c['supplier']} ({c.get('country')}) — "
                                  f"{fmt_eur(c.get('contract_value'))} contract. Country: high geopolitical risk."))

    # Low resilience dimensions
    if resilience.get("dimensions"):
        for dim, score in resilience["dimensions"].items():
            if score < 0.35:
                recos.append(("critical", f"Resilience dimension '{dim}' critically low ({int(score*100)}%). Immediate action required."))
            elif score < 0.5:
                recos.append(("high", f"Resilience dimension '{dim}' below threshold ({int(score*100)}%). Improvement plan needed."))

    # Disruption events
    for e in events:
        if e.get("impact") == "HIGH":
            recos.append(("high", f"Historical disruption: {e['event']} ({e.get('date')}) affected {e.get('supplier')}. "
                                  f"Review business continuity plan."))

    # Deduplicate + sort by severity
    order = {"critical": 0, "high": 1, "medium": 2}
    recos = sorted(recos, key=lambda x: order.get(x[0], 9))
    return recos[:12]  # cap at 12


def build_tier_tree_html(sku: str) -> str:
    """Build a simple text-based tier tree from Neo4j."""
    try:
        # T1
        t1 = neo4j("""
        MATCH (p:Product {sku:$sku})-[:SUPPLIED_BY]->(s:Supplier)
        RETURN s.name AS name, s.country AS c, s.risk_flags AS flags
        ORDER BY s.name
        """, {"sku": sku})

        lines = []
        for i, s in enumerate(t1):
            branch = "└─" if i == len(t1) - 1 else "├─"
            flag = " ⚠" if s.get("flags") else ""
            lines.append(f"{branch}▶ {s['name']} ({s.get('c','?')}){flag}")

            # T2 for this T1
            t2 = neo4j("""
            MATCH (s1:Supplier {name:$name})-[:SOURCED_FROM]->(s2)
            RETURN coalesce(s2.name, s2.sku) AS name, s2.country AS c, labels(s2)[0] AS type
            ORDER BY s2.name LIMIT 5
            """, {"name": s["name"]})

            indent = "   " if i == len(t1) - 1 else "│  "
            for j, s2 in enumerate(t2):
                b2 = "└─" if j == len(t2) - 1 else "├─"
                icon = "◆" if s2.get("type") == "RawMaterial" else "▶"
                lines.append(f"{indent}{b2}{icon} {s2['name']} ({s2.get('c','?')})")

        return "\n".join(lines) if lines else "(no supply chain data)"
    except Exception as exc:
        return f"(error: {exc})"


def generate_report(sku: str, use_demo: bool = False) -> str:
    """Fetch all data and render the HTML report."""
    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    if use_demo:
        product = {"name": "Scania R-series Heavy Truck", "sku": "SCANIA-R-500", "category": "Commercial Vehicles"}
        contracts = [
            {"supplier": "ZF Friedrichshafen", "country": "DE", "tier": 1, "component": "TraXon gearbox",
             "contract_value": 1200000000, "lead_time": 90, "single_source": True,
             "risk_flags": ["SINGLE_SOURCE"], "supplier_revenue": 46600000000, "risk_score": 0.35},
            {"supplier": "Bosch", "country": "DE", "tier": 1, "component": "Fuel injection system",
             "contract_value": 800000000, "lead_time": 60, "single_source": False, "risk_flags": [],
             "supplier_revenue": 91600000000, "risk_score": 0.25},
            {"supplier": "SSAB", "country": "SE", "tier": 1, "component": "Chassis steel",
             "contract_value": 320000000, "lead_time": 30, "single_source": False, "risk_flags": [],
             "supplier_revenue": 9800000000, "risk_score": 0.2},
            {"supplier": "Dana Incorporated", "country": "US", "tier": 1, "component": "Driveshafts/axles",
             "contract_value": 420000000, "lead_time": 75, "single_source": True,
             "risk_flags": ["SINGLE_SOURCE"], "supplier_revenue": 9700000000, "risk_score": 0.6},
            {"supplier": "Cummins Inc", "country": "US", "tier": 1, "component": "Euro6 engine",
             "contract_value": 380000000, "lead_time": 90, "single_source": True,
             "risk_flags": ["SINGLE_SOURCE"], "supplier_revenue": 24100000000, "risk_score": 0.55},
        ]
        resilience = {
            "score": 0.52,
            "dimensions": {"Geo Diversity": 0.6, "Single Source": 0.4, "Risk Exposure": 0.65,
                          "Tier Coverage": 0.8, "Lead Time": 0.5, "Certification": 0.7},
            "avg_lead_days": 69, "t1_count": 7, "t2_count": 11, "t3_count": 8,
            "single_source_count": 3, "countries": ["DE", "SE", "FR", "US"],
        }
        certs = [
            {"supplier": "ZF Friedrichshafen", "tier": 1, "cert": "IATF 16949:2016", "issuer": "Bureau Veritas", "valid_until": "2026-09-30"},
            {"supplier": "SSAB", "tier": 1, "cert": "ISO 14001:2015", "issuer": "TUV", "valid_until": "2027-06-30"},
            {"supplier": "Bosch", "tier": 1, "cert": "LkSG Compliance", "issuer": "Internal", "valid_until": "2027-01-01"},
        ]
        events = [
            {"event": "Garrett Motion Chapter 11 Bankruptcy 2020", "date": "2020-09-20",
             "type": "FINANCIAL", "impact": "HIGH", "supplier": "Garrett Motion",
             "description": "Turbocharger supplier bankruptcy; supply continuity maintained"},
        ]
        alternatives = [
            {"primary_supplier": "Dana Incorporated", "alternative": "Akebono Brake Industry", "alt_country": "JP"},
        ]
        risk_suppliers = [
            {"name": "China Rare Earth Group", "country": "CN", "tier": 3, "risk_score": 0.9,
             "risk_flags": ["GEOPOLITICAL_RISK", "SINGLE_SOURCE", "SANCTIONS_RISK"]},
            {"name": "Dana Incorporated", "country": "US", "tier": 1, "risk_score": 0.6,
             "risk_flags": ["SINGLE_SOURCE"]},
        ]
        tier_tree = "(demo) ZF → Saarstahl → Iron Ore\n     └ Bosch → Infineon → Silicon"
    else:
        product = fetch_product(sku)
        if not product:
            raise ValueError(f"Product not found: {sku}")
        contracts = fetch_t1_contracts(sku)
        resilience = compute_resilience(sku)
        certs = fetch_certifications(sku)
        events = fetch_events(sku)
        alternatives = fetch_alternatives(sku)
        risk_suppliers = fetch_risk_suppliers(sku)
        tier_tree = build_tier_tree_html(sku)

    # KPIs
    total_exposure = sum(c.get("contract_value") or 0 for c in contracts)
    ss_exposure = sum(c.get("contract_value") or 0 for c in contracts if c.get("single_source"))
    high_risk_count = sum(1 for r in risk_suppliers if (r.get("risk_score") or 0) >= 0.7)
    avg_lead = resilience.get("avg_lead_days") or 0
    res_score = resilience.get("score")
    res_pct = int(res_score * 100) if res_score else 0
    res_color = risk_color(1 - (res_score or 0.5))  # invert: high resilience = green

    # Recommendations
    recos = build_recommendations(contracts, resilience, events, alternatives)

    # Render dims
    dims = resilience.get("dimensions", {})
    radar_svg = render_resilience_radar_svg(dims) if dims else ""
    dim_bars = render_dim_bars(dims) if dims else ""

    # Risk level badge
    overall_risk = risk_label(1 - (res_score or 0.5))
    overall_color = risk_color(1 - (res_score or 0.5))

    # Contracts table rows
    contract_rows = ""
    for c in contracts:
        flags = c.get("risk_flags") or []
        flag_html = " ".join(f'<span class="flag-chip">{f.replace("_"," ")}</span>' for f in flags)
        ss_badge = '<span class="badge badge-red">SOLE</span>' if c.get("single_source") else ""
        risk_badge = f'<span class="badge" style="background:{risk_color(c.get("risk_score"))};color:white">{risk_label(c.get("risk_score"))}</span>'
        contract_rows += f"""
        <tr>
          <td><strong>{c.get('supplier','?')}</strong></td>
          <td>{c.get('country','?')}</td>
          <td>T{c.get('tier','?')}</td>
          <td>{c.get('component','—')}</td>
          <td style="font-weight:700">{fmt_eur(c.get('contract_value'))}</td>
          <td>{c.get('lead_time','—')}d</td>
          <td>{ss_badge}</td>
          <td>{risk_badge}</td>
          <td>{flag_html}</td>
        </tr>"""

    # Cert table rows
    def cert_status_badge(d):
        if not d:
            return '<span class="badge badge-gray">?</span>'
        from datetime import date
        try:
            exp = date.fromisoformat(d)
            days = (exp - date.today()).days
            if days < 0:
                return f'<span class="badge badge-red">EXPIRED</span>'
            if days < 180:
                return f'<span class="badge badge-orange">EXPIRING {d}</span>'
            return f'<span class="badge badge-green">VALID {d}</span>'
        except Exception:
            return f'<span class="badge badge-gray">{d}</span>'

    cert_rows = ""
    for c in certs:
        cert_rows += f"""
        <tr>
          <td>{c.get('supplier','?')}</td>
          <td>T{c.get('tier','?')}</td>
          <td>{c.get('cert','?')}</td>
          <td>{c.get('issuer','?')}</td>
          <td>{cert_status_badge(c.get('valid_until'))}</td>
        </tr>"""

    if not cert_rows:
        cert_rows = '<tr><td colspan="5" style="color:#718096;text-align:center">No certification data</td></tr>'

    # Risk table
    risk_rows = ""
    for r in risk_suppliers[:10]:
        flags = r.get("risk_flags") or []
        flag_html = " ".join(f'<span class="flag-chip">{f.replace("_"," ")}</span>' for f in flags[:3])
        sanctioned = '<span class="badge badge-red">MATCH</span>' if r.get("sanctioned") else ""
        risk_rows += f"""
        <tr>
          <td><strong>{r.get('name','?')}</strong></td>
          <td>{r.get('country','?')}</td>
          <td>T{r.get('tier','?')}</td>
          <td style="color:{risk_color(r.get('risk_score'))};font-weight:700">{risk_label(r.get('risk_score'))}</td>
          <td>{flag_html}</td>
          <td>{sanctioned}</td>
        </tr>"""

    if not risk_rows:
        risk_rows = '<tr><td colspan="6" style="color:#718096;text-align:center">No risk data — run risk_scorer.py</td></tr>'

    # Events table
    event_rows = ""
    for e in events:
        impact_color = "#e53e3e" if e.get("impact") == "HIGH" else "#dd6b20" if e.get("impact") == "MEDIUM" else "#718096"
        event_rows += f"""
        <tr>
          <td>{e.get('date','?')}</td>
          <td style="color:{impact_color};font-weight:700">{e.get('impact','?')}</td>
          <td>{e.get('type','?')}</td>
          <td>{e.get('supplier','?')}</td>
          <td>{e.get('event','?')}</td>
        </tr>"""

    if not event_rows:
        event_rows = '<tr><td colspan="5" style="color:#718096;text-align:center">No disruption events recorded</td></tr>'

    # Recommendations
    icon_map = {"critical": "🔴", "high": "🟠", "medium": "🟡"}
    reco_html = ""
    for level, text in recos:
        reco_html += f'<div class="reco {level}"><span class="reco-icon">{icon_map.get(level,"·")}</span><span>{text}</span></div>'
    if not reco_html:
        reco_html = '<div style="color:#718096;font-size:12px">No critical recommendations identified.</div>'

    # Alternatives section
    alt_rows = ""
    for a in alternatives:
        alt_rows += f"""
        <tr>
          <td>{a.get('primary_supplier','?')}</td>
          <td>{a.get('alternative','?')}</td>
          <td>{a.get('alt_country','?')}</td>
          <td>{fmt_eur(a.get('alt_revenue'))}</td>
        </tr>"""
    if not alt_rows:
        alt_rows = '<tr><td colspan="4" style="color:#718096;text-align:center">No alternatives mapped in graph</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Procurement Intelligence Report — {product.get('name','?')}</title>
<style>{HTML_CSS}</style>
</head>
<body>
<div class="page">

<!-- Cover -->
<div class="cover">
  <h1>Procurement Intelligence Report</h1>
  <div class="subtitle">{product.get('name','?')} &bull; {product.get('category','?')}</div>
  <div style="margin-bottom:20px">
    <span class="badge" style="background:{overall_color};color:white;font-size:13px;padding:4px 12px">
      OVERALL RISK: {overall_risk}
    </span>
    <span style="margin-left:12px;font-size:14px">Resilience Score: {res_pct}%</span>
  </div>
  <div class="meta">
    <span>SKU: {product.get('sku','?')}</span>
    <span>Generated: {generated_at}</span>
    <span>Source: UC4 Supply Chain Graph (Neo4j)</span>
  </div>
</div>

<!-- KPIs -->
<div class="section">
  <h2><span class="num">1</span> Executive Summary</h2>
  <div class="kpi-row">
    <div class="kpi"><div class="kpi-v blue">{resilience.get('t1_count','—')}</div><div class="kpi-l">Tier 1 Suppliers</div></div>
    <div class="kpi"><div class="kpi-v blue">{resilience.get('t2_count','—')}</div><div class="kpi-l">Tier 2 Suppliers</div></div>
    <div class="kpi"><div class="kpi-v blue">{resilience.get('t3_count','—')}</div><div class="kpi-l">Tier 3+ Nodes</div></div>
    <div class="kpi"><div class="kpi-v blue">{len(resilience.get('countries',[]))}</div><div class="kpi-l">Countries</div></div>
    <div class="kpi"><div class="kpi-v {'red' if ss_exposure > 5e8 else 'orange'}">{fmt_eur(total_exposure)}</div><div class="kpi-l">Total T1 Exposure</div></div>
    <div class="kpi"><div class="kpi-v red">{fmt_eur(ss_exposure)}</div><div class="kpi-l">Single-Source Exposure</div></div>
    <div class="kpi"><div class="kpi-v {'red' if high_risk_count > 2 else 'orange'}">{high_risk_count}</div><div class="kpi-l">High-Risk Suppliers</div></div>
    <div class="kpi"><div class="kpi-v {'red' if avg_lead > 90 else 'orange' if avg_lead > 60 else 'green'}">{int(avg_lead)}d</div><div class="kpi-l">Avg Lead Time (T1)</div></div>
  </div>
  <div style="background:#f7fafc;border:1px solid #e2e8f0;border-radius:6px;padding:12px;font-size:12px;line-height:1.8">
    <strong>Supply chain summary:</strong> {product.get('name')} relies on {resilience.get('t1_count','N/A')} direct (Tier 1) suppliers
    across {len(resilience.get('countries',[]))} countries, with total annual contract exposure of {fmt_eur(total_exposure)}.
    {f"<strong style='color:#e53e3e'>{resilience.get('single_source_count',0)} single-source dependencies</strong> representing {fmt_eur(ss_exposure)} are the primary risk." if resilience.get('single_source_count') else ""}
    Overall resilience score: <strong>{res_pct}%</strong> ({risk_label(1-(res_score or 0.5))}).
  </div>
</div>

<!-- Contracts -->
<div class="section">
  <h2><span class="num">2</span> Tier 1 Supplier Contracts</h2>
  <table>
    <thead><tr>
      <th>Supplier</th><th>Country</th><th>Tier</th><th>Component</th>
      <th>Contract Value</th><th>Lead Time</th><th>Sole</th><th>Risk</th><th>Flags</th>
    </tr></thead>
    <tbody>{contract_rows}</tbody>
  </table>
</div>

<!-- Supply chain tree -->
<div class="section">
  <h2><span class="num">3</span> Supply Chain Structure (Tier 1–3)</h2>
  <div class="tier-tree">{tier_tree}</div>
</div>

<!-- Risk suppliers -->
<div class="section">
  <h2><span class="num">4</span> High-Risk Supplier Watchlist</h2>
  <table>
    <thead><tr>
      <th>Supplier</th><th>Country</th><th>Tier</th><th>Risk Level</th><th>Flags</th><th>Sanctions</th>
    </tr></thead>
    <tbody>{risk_rows}</tbody>
  </table>
</div>

<!-- Resilience -->
<div class="section">
  <h2><span class="num">5</span> Resilience Scorecard</h2>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px;align-items:center">
    <div>
      {radar_svg}
      <div style="text-align:center;font-size:13px;margin-top:8px">
        Composite score: <strong style="font-size:20px;color:{res_color}">{res_pct}%</strong>
        <span class="badge" style="background:{res_color};color:white;margin-left:8px">{risk_label(1-(res_score or 0.5))}</span>
      </div>
    </div>
    <div>{dim_bars}</div>
  </div>
</div>

<!-- Certifications -->
<div class="section">
  <h2><span class="num">6</span> Certification Compliance</h2>
  <table>
    <thead><tr>
      <th>Supplier</th><th>Tier</th><th>Standard</th><th>Issuer</th><th>Status</th>
    </tr></thead>
    <tbody>{cert_rows}</tbody>
  </table>
</div>

<!-- Events -->
<div class="section">
  <h2><span class="num">7</span> Disruption Events</h2>
  <table>
    <thead><tr>
      <th>Date</th><th>Impact</th><th>Type</th><th>Supplier</th><th>Event</th>
    </tr></thead>
    <tbody>{event_rows}</tbody>
  </table>
</div>

<!-- Alternatives -->
<div class="section">
  <h2><span class="num">8</span> Alternative Supplier Mapping</h2>
  <table>
    <thead><tr>
      <th>Primary Supplier</th><th>Alternative</th><th>Country</th><th>Revenue</th>
    </tr></thead>
    <tbody>{alt_rows}</tbody>
  </table>
</div>

<!-- Recommendations -->
<div class="section">
  <h2><span class="num">9</span> Recommended Actions</h2>
  {reco_html}
</div>

<footer>
  Generated by UC4 Supply Chain Intelligence Platform &bull; {generated_at} &bull;
  Data source: Neo4j Supply Chain Graph (CT114) &bull; Confidential — Internal Use Only
</footer>
</div>
</body>
</html>"""


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate procurement intelligence report")
    parser.add_argument("--product", help="Product SKU (e.g. SCANIA-R-500)")
    parser.add_argument("--all", action="store_true", help="Generate report for every product")
    parser.add_argument("--out", default="docs/", help="Output file or directory")
    parser.add_argument("--dry-run", action="store_true", help="Use demo data (no Neo4j needed)")
    args = parser.parse_args()

    if not args.product and not args.all and not args.dry_run:
        parser.error("Specify --product SKU, --all, or --dry-run")

    def write_report(sku, outpath, demo=False):
        print(f"Generating report: {sku} → {outpath}")
        try:
            html = generate_report(sku, use_demo=demo)
            with open(outpath, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"  ✓ Written: {outpath} ({len(html):,} bytes)")
        except Exception as e:
            print(f"  ERROR: {e}")

    if args.dry_run:
        out = args.out if not os.path.isdir(args.out) else os.path.join(args.out, "report_demo.html")
        write_report("SCANIA-R-500", out, demo=True)
        return

    if args.all:
        products = fetch_all_products()
        print(f"Found {len(products)} products")
        for p in products:
            sku = p["sku"]
            fname = f"report_{sku.lower().replace('-','_')}.html"
            out = os.path.join(args.out, fname) if os.path.isdir(args.out) else args.out
            write_report(sku, out)
        return

    out = args.out
    if os.path.isdir(out):
        fname = f"report_{args.product.lower().replace('-','_')}.html"
        out = os.path.join(out, fname)
    write_report(args.product, out)


if __name__ == "__main__":
    main()
