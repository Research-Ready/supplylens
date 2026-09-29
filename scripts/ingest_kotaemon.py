"""Kotaemon Document Ingestor — UC4 Supply Chain (CT120 :8501)

Bulk-uploads supplier documents into Kotaemon so the RAG layer
has real content to query during LangGraph enrichment runs.

Sources ingested:
  1. data/sample_supplier_text.txt         — demo supplier text
  2. data/sample_companies.csv             — company list
  3. Supplier web pages scraped live via Browserless (CT400)
  4. Any PDFs in data/pdfs/ (if present)

Usage:
    python3 scripts/ingest_kotaemon.py
    python3 scripts/ingest_kotaemon.py --skip-scrape   # only ingest local files
    python3 scripts/ingest_kotaemon.py --dry-run       # list what would be ingested

Kotaemon API (Gradio app on CT120:8501):
    POST /upload   multipart — upload file to session
    POST /api/index — trigger indexing of uploaded file
    The Gradio queue API is used for indexing.
"""
import argparse
import base64
import json
import os
import sys
import time
import uuid
import urllib.request
import urllib.error
import urllib.parse

REPO_ROOT    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KOTAEMON_URL = os.getenv("KOTAEMON_URL",         "http://10.0.1.120:8501")
BROWSERLESS  = os.getenv("BROWSERLESS_PROD_URL", "http://10.0.5.100:3500")
LITELLM      = os.getenv("LITELLM_URL",          "http://localhost:4000")
LITELLM_KEY  = os.getenv("LITELLM_KEY",          "")
NEO4J_URL    = os.getenv("NEO4J_URL",            "http://localhost:7474")
NEO4J_USER   = os.getenv("NEO4J_USER",           "neo4j")
NEO4J_PASS   = os.getenv("NEO4J_PASS",           "")

# Known supplier websites to scrape and ingest
SUPPLIER_SITES = [
    ("Bosch",               "https://www.bosch.com/stories/"),
    ("ZF Friedrichshafen",  "https://www.zf.com/mobile/en/company/company.html"),
    ("SSAB",                "https://www.ssab.com/en/company/about-ssab"),
    ("Michelin",            "https://www.michelin.com/en/group/michelin-at-a-glance/"),
    ("LKAB",                "https://www.lkab.com/en/about-lkab/"),
    ("Infineon Technologies","https://www.infineon.com/cms/en/about-infineon/company/"),
    ("Cummins Inc",         "https://www.cummins.com/company/our-story"),
    ("AMS Buttons BV",      "https://www.amsbuttons.nl"),
    ("Dana Incorporated",   "https://www.dana.com/company/about-dana/"),
    ("Knorr-Bremse AG",     "https://www.knorr-bremse.com/en/company/about-knorr-bremse/"),
    ("Garrett Motion",      "https://www.garrettmotion.com/company/about-us/"),
    ("Haldex AB",           "https://www.haldex.com/en/group/about-haldex/"),
    ("TimkenSteel Corporation","https://www.timkensteel.com/company/who-we-are"),
    ("Schaeffler Group",    "https://www.schaeffler.com/en/group/company/"),
    ("LKAB",                "https://www.lkab.com/en/sustainability/"),
    ("Vale SA",             "https://www.vale.com/en/sustainability"),
    ("Glencore",            "https://www.glencore.com/who-we-are/about-glencore"),
]

# Synthetic supplier profiles to ingest as text docs
SYNTHETIC_DOCS = [
    ("Infineon_Technologies_profile.txt", """
Infineon Technologies AG — Semiconductor Supplier Profile (UC4 Supply Chain)

Company: Infineon Technologies AG
Country: Germany (DE)
Founded: 1999 (spin-off from Siemens)
HQ: Neubiberg, Bavaria, Germany
Tier: 2 (supplies to Bosch, Continental)

Supply Chain Relationships:
- SOURCED_FROM: China Rare Earth Group (CN) — rare earth elements for power modules
- SOURCED_FROM: AVX Tantalum (US) — tantalum capacitors for ECU boards
- SOURCED_FROM: Siltronic AG (DE) — silicon wafers (raw silicon)
- SOURCED_FROM: Air Products (US) — specialty gases for fab process

Key Products Supplied to UC4 Chain:
- XMC microcontrollers (to Bosch fuel injection ECU)
- AURIX automotive-grade MCUs (safety-critical systems)
- SiC power modules (EV drivetrains)
- XENSIV sensors (pressure, CO2, radar)

Risk Factors:
- CONFLICT_MINERAL: tantalum capacitors sourced via DRC supply chain
- GEOPOLITICAL_RISK: rare earth supply from China (single-source dependency)
- DODD_FRANK_REPORTABLE: tantalum, tin, tungsten disclosure required
- Fab concentration risk: main fab in Dresden (single geography)

Certifications:
- IATF 16949:2016 (automotive quality)
- ISO 14001:2015 (environmental)
- RBA Code of Conduct
- AEC-Q100 (automotive-grade components)

Annual Revenue: ~€16.3B (2023)
Key Customers: Bosch, Continental, ZF, Valeo, Aptiv
"""),
    ("China_Rare_Earth_Group_profile.txt", """
China Rare Earth Group (中国稀土集团) — Raw Material Supplier Profile

Company: China Rare Earth Group Co., Ltd.
Country: China (CN)
Founded: 2021 (state-owned consolidation)
HQ: Nanchang, Jiangxi Province, China
Tier: 3 (supplies to Infineon, ams-OSRAM)

Supply Chain Relationships:
- Mines: Ganzhou, Jiangxi (heavy rare earths — Dy, Tb, Gd)
- Mines: Inner Mongolia (light rare earths — La, Ce, Nd, Pr)
- Processes: separation, refining, oxide/metal production

Materials Supplied:
- Neodymium (Nd) — NdFeB permanent magnets for motors
- Dysprosium (Dy) — high-temperature magnet additive
- Terbium (Tb) — phosphors, green LED components
- Cerium (Ce) — glass polishing, catalysts
- Lanthanum (La) — battery electrodes, optics

Risk Factors:
- GEOPOLITICAL_RISK: 100% state-owned, subject to Chinese export controls
- SINGLE_SOURCE: no viable Western alternative at scale
- SANCTIONS_RISK: potential target of export control actions
- Supply concentration: >85% of global rare earth processing in China
- 2023: China announced export restrictions on Ga, Ge (gallium, germanium)

Annual Output: ~120,000 tonnes REO equivalent
Key Customers: Infineon, ams-OSRAM, Bosch (indirectly via magnets)
"""),
    ("Scania_Supply_Chain_Overview.txt", """
Scania AB — Supply Chain Overview for R-series Heavy Truck (UC4 Demo)

Product: Scania R-series Heavy Truck (SKU: SCANIA-R-500)
Manufacturer: Scania AB, Södertälje, Sweden
Parent: Volkswagen Truck & Bus GmbH (TRATON Group)
Annual Production: ~90,000 trucks/year

Tier 1 Suppliers (Direct):
- ZF Friedrichshafen (DE): TraXon automated gearbox — contract since 2015
- Bosch (DE): Fuel injection (XPI common rail), ECU, ADAS systems — since 2018
- SSAB (SE): Hardox/Strenx high-strength chassis steel — long-term strategic partner
- Michelin (FR): X Line Energy tyres — since 2020 (fuel efficiency program)
- Dana Incorporated (US): Driveshafts, axles — SINGLE SOURCE risk flagged
- Cummins Inc (US): Euro6 engine variants for non-Scania-engine builds — since 2019
- Continental AG (DE): ADAS sensors, braking systems — since 2021

Key Supply Chain Risks:
1. Dana Incorporated — single source for driveshafts: no qualified backup supplier
2. China Rare Earth dependency: via Infineon → China Rare Earth Group
3. Carbon Black (Michelin → Russia): Cabot sourcing from Russian feedstock
4. Semiconductor shortage exposure: Bosch → Infineon → TSMC/Samsung

Sustainability commitments:
- Scania Science Based Targets: net zero by 2040
- Suppliers must comply with Scania Supplier Code of Conduct
- REACH compliance mandatory for all chemical substances
- Conflict minerals policy: annual OECD Due Diligence reporting

Key Facts:
- 65% of truck cost is in purchased components (outsourced supply chain)
- Average supplier relationship age: 12 years
- Tier 1 supplier count: ~1,500 globally
"""),
    ("Continental_AG_profile.txt", """
Continental AG — Automotive Electronics & ADAS Supplier Profile (UC4)

Company: Continental AG
Country: Germany (DE)
Founded: 1871
HQ: Hanover, Germany
Tier: 1 (direct supplier to Scania R-500, G-410)
Annual Revenue: €41.4B (2023)
Employees: 190,000+

Supply Chain Relationships:
- SOURCED_FROM: STMicroelectronics (CH) — ADAS processors, MCUs, power ICs
- SOURCED_FROM: TE Connectivity (IE) — automotive connectors, sensor housings
- SOURCED_FROM: Infineon Technologies (DE) — radar chips, ECU silicon
- SOURCED_FROM: TSMC (TW) — advanced node wafers for ADAS SoCs

Key Products Supplied to UC4 Chain:
- ADAS sensor fusion modules (camera + radar + lidar)
- Body control modules (BCM) for Scania R-series
- Fleet telematics hardware (VDO brand)
- Electronic brake control (ABS/ESC) systems

Risk Factors:
- SINGLE_SOURCE_PARTIAL: TSMC dependency for 5nm ADAS chips
- FINANCIAL_RISK: Automotive/Tires business separation delayed; Z-score 2.18
- EV_TRANSITION: legacy combustion electronics revenues declining
- Ukraine: component supply disruptions 2022-2023

Financial Health:
- Altman Z-Score: 2.18 (GREY ZONE)
- Net Debt/EBITDA: 2.1× (WATCH)
- Credit Rating: BBB- (Moody's Baa3)
- Note: separation of auto/tire divisions expected to unlock value

Certifications: IATF 16949, ISO 14001, ISO 26262 (functional safety), ASPICE
Contract Value (Scania): €180M/year (ADAS + BCM)
"""),
    ("Aptiv_profile.txt", """
Aptiv PLC — Wiring Harness & High-Voltage Connector Supplier Profile (UC4)

Company: Aptiv PLC
Country: USA (US), major operations in Ukraine
HQ: Dublin, Ireland (legal); Troy, Michigan (operational)
Tier: 1 (direct supplier to Scania R-500, G-410)
Annual Revenue: $17.9B (2023)
Employees: 180,000

Supply Chain Relationships:
- SOURCED_FROM: TE Connectivity (IE) — high-voltage connectors, sealing systems
- SOURCED_FROM: Leoni AG (DE) — cable sub-assemblies (Lviv plant)
- SOURCED_FROM: Molex (US) — micro-connectors, PCB components
- SOURCED_FROM: Copper Cathode (CL/Codelco) — wire core material

Key Products Supplied to UC4 Chain:
- Wiring harness assemblies for Scania R-series cabins
- High-voltage connection systems (800V BEV architecture)
- Signal & power distribution modules
- Smart electrical architecture (zonal controllers)

Risk Factors:
- UKRAINE_CONFLICT_RISK: ~35% of wiring harness production in Lviv & Uzhhorod, Ukraine
- GEOPOLITICAL_RISK: Lviv plant 800km from active front (Feb 2022 disruption)
- FINANCIAL_RISK: Ukraine absorption ~€180M/year; Morocco relocation in progress
- SINGLE_SOURCE: no qualified alternative for some harness configurations

Financial Health:
- Altman Z-Score: 2.41 (GREY ZONE — WATCH)
- Net Debt/EBITDA: 2.9×
- Credit Rating: BBB (stable)
- Ukraine relocation to Morocco/Romania: 60% complete (target: 2026)

Certifications: IATF 16949, ISO 14001, ISO 26262, RoHS
Contract Value (Scania): €95M/year wiring harness
"""),
    ("STMicroelectronics_profile.txt", """
STMicroelectronics — Automotive Semiconductor Supplier Profile (UC4)

Company: STMicroelectronics N.V.
Country: Switzerland (CH), fabs in France + Italy
HQ: Geneva, Switzerland
Tier: 2 (supplies to Continental AG, Valeo, Bosch)
Annual Revenue: €14.3B (2023)

Supply Chain Relationships:
- SOURCED_FROM: Palladium (RU/Norilsk) — wire bonding, catalytic metallisation
- SOURCED_FROM: Polysilicon (CN) — EPI wafer substrate (via SUMCO, Siltronic)
- SOURCED_FROM: Air Products + Linde — specialty fab gases (ultra-pure)
- SOURCED_FROM: Applied Materials — fab equipment for Crolles/Catania

Key Products Supplied to UC4 Chain:
- SPC58x/SPC57x automotive MCUs — safety-critical ECUs (Continental ADAS)
- SiC MOSFET power modules — EV inverters (Nidec via CATL BEV chain)
- MEMS accelerometers & gyroscopes — airbag ECUs (Autoliv)
- Automotive-grade op-amps, voltage regulators

Risk Factors:
- SANCTIONS_RISK: palladium wire bond dependency on Norilsk (OFAC listed)
  → STM: 'actively diversifying' to Heraeus, Umicore palladium sources
- UFLPA_RISK: polysilicon substrate from CN; wafer supply via SUMCO (JP) partially mitigates
- GEOPOLITICAL_RISK: Crolles fab (FR) + Catania fab (IT) — EU subsidized
- Automotive chip shortage 2021: lead times hit 26 weeks; improved to 12-16 weeks 2024

Financial Health:
- Altman Z-Score: 2.91 (approaching SAFE zone)
- Net Debt/EBITDA: 0.1× (near-net-cash)
- Credit Rating: BBB+ (positive outlook)
- SiC revenue: €1.5B (2023), target €5B by 2027

Certifications: IATF 16949, AEC-Q100/Q101, ISO 26262
Contract Value (Continental+Valeo): ~€340M/year (Scania chain)
"""),
    ("Leoni_AG_profile.txt", """
Leoni AG — Cable & Wiring Systems Supplier Profile (UC4)

Company: Leoni AG
Country: Germany (DE), major plant in Stryi/Lviv, Ukraine
HQ: Nuremberg, Germany
Tier: 2 (supplies to Aptiv, Valeo wiring sub-assemblies)
Annual Revenue: €5.4B (2023)

Supply Chain Relationships:
- SOURCED_FROM: Copper Cathode (CL/Codelco) — oxygen-free copper wire
- Volume: ~85,000 tonnes copper wire/year
- SOURCED_FROM: Plastic compounds (BASF DE, LyondellBasell NL) — insulation
- SOURCED_FROM: Aluminium wire (Constellium FR) — weight-saving alternative

Key Products Supplied to UC4 Chain:
- Automotive cable sets (sub-assemblies for Aptiv wiring harness)
- Speciality cables for high-voltage EV architectures (up to 800V)
- Industrial cable harnesses

Risk Factors:
- UKRAINE_CONFLICT_RISK: Stryi (Lviv region) plant — 4,000 employees
  → Feb 2022: partial shutdown; relocated 30% production to Tunisia/Morocco
- FINANCIAL_RISK: DISTRESS ZONE — restructuring completed Dec 2023
  → Rights issue €150M; new revolving credit facility €250M
  → Altman Z-Score: 1.71 (DISTRESS)
- SINGLE_SOURCE: only qualified supplier for certain Aptiv cable specs
- LkSG_RISK: labour conditions in Ukraine plant flagged 2022

Financial Health:
- Altman Z-Score: 1.71 (DISTRESS ZONE — HIGH RISK)
- Net Debt/EBITDA: 5.1× (ELEVATED)
- Credit Rating: B (CCC+ during restructuring)
- Current Ratio: 0.92 (<1 = short-term liquidity risk)
- Post-restructuring: covenants require Z > 1.5 quarterly; Feb 2024 passed

Certifications: IATF 16949, ISO 14001
"""),
    ("Codelco_Copper_profile.txt", """
Codelco — Copper Mining & Refining Profile (UC4)

Company: Corporación Nacional del Cobre de Chile (Codelco)
Country: Chile (CL)
Founded: 1976 (nationalization of copper mines)
HQ: Santiago, Chile
Tier: 3 (supplies Copper Cathode to TE Connectivity, Leoni, Molex)
Annual Revenue: $12B+ (2023)

Mining Operations:
- Escondida Mine (joint: BHP 57.5%, Rio Tinto 30%, JECO Corp 10%, IFC 2.5%)
  → Largest copper mine globally: 1.2M tonnes/year cathode equivalent
- Chuquicamata (100% Codelco): underground conversion 2019 — 330kt/year
- El Teniente (100% Codelco): world's largest underground Cu mine — 450kt/year
- Andina: Andes high-altitude; 240kt/year

Materials Supplied (to UC4 chain):
- Copper Cathode (LME Grade A): 99.99% Cu purity
  → TE Connectivity: ~45kt/year (connector pins)
  → Leoni AG: ~85kt/year (cable wire cores)
  → Molex: ~12kt/year (terminal stamping)

Risk Factors:
- WATER_STRESS: Atacama operations compete with indigenous water rights
- LABOUR_RISK: 7 strikes since 2010 (most recent: El Teniente 2023, 6 days)
- SEISMIC_RISK: Chile M7+ earthquakes; Chuquicamata 2019 (no significant damage)
- SOVEREIGN_RISK: Chilean mining royalty reform 2023 (rate increase 8→11%)

Financial Health:
- Altman Z-Score: 2.34 (GREY ZONE; state guarantee lifts effective rating)
- Net Debt/EBITDA: 3.5× (elevated but backstopped by Chilean state)
- Credit Rating: A- (S&P) — reflects sovereign guarantee
- Copper price sensitivity: -$0.10/lb = -$150M EBITDA

Environmental: ISO 14001; LME Responsible Sourcing; IRMA audited
"""),
    ("AVX_Tantalum_profile.txt", """
AVX Tantalum (Kyocera AVX) — Conflict Mineral Supplier Profile

Company: AVX Corporation (subsidiary of Kyocera)
Country: United States (US)
HQ: Fountain Inn, South Carolina, USA
Tier: 3 (supplies to Infineon Technologies, NXP, STMicroelectronics)

Products:
- Tantalum electrolytic capacitors (TAJ, TPS, TCJ series)
- Used in ECU power filtering, decoupling
- High CV capacitors for automotive-grade applications (AEC-Q200)

Tantalum Supply Chain:
- Sourced from: Global Advanced Metals (Australia) — primary
- Sourced from: Conflict-free DRC certified smelters (RBA/CFSI certified)
- Mineral: Columbite-tantalite (coltan) ore → Ta2O5 → capacitor grade Ta powder
- Key concern: DRC artisanal mining risk in lower tiers

Dodd-Frank Section 1502:
- AVX files annual conflict minerals report with SEC
- CFSI Conflict-Free Smelter Program certified
- 3TG minerals: Tantalum, Tin, Tungsten, Gold — all require disclosure

Risk Factors:
- CONFLICT_MINERAL: tantalum originates from DRC supply chain (even if certified)
- DODD_FRANK_REPORTABLE: mandatory SEC disclosure
- Tier-4 risk: artisanal small-scale mining (ASM) in DRC/Rwanda

Customers: Infineon, NXP, STM, Vishay, Panasonic
Certifications: CFSI Conflict-Free, RBA CoC, ISO 14001
"""),
]


# ── Neo4j helpers ────────────────────────────────────────────────────────────

def _get_neo4j_pass() -> str:
    global NEO4J_PASS
    if NEO4J_PASS:
        return NEO4J_PASS
    # Try KeePass
    try:
        from pykeepass import PyKeePass
        kp = PyKeePass("passwords.kdbx", password="SupplyChainBaby100!")
        e = kp.find_entries(title="Neo4j", first=True)
        if e:
            NEO4J_PASS = e.password
            return NEO4J_PASS
    except Exception:
        pass
    # Try credentials file on CT114 via env hint
    import getpass
    NEO4J_PASS = getpass.getpass("Neo4j password: ")
    return NEO4J_PASS


def neo4j_query(cypher: str, params: dict = None) -> list[dict]:
    pw = _get_neo4j_pass()
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


def generate_neo4j_fact_sheet(name: str) -> str:
    """Generate a supplier fact sheet dynamically from Neo4j graph data."""
    try:
        profiles = neo4j_query(
            "MATCH (s:Supplier {name:$name}) RETURN s.tier AS tier, s.country AS country, "
            "s.annual_revenue_eur AS rev, s.employee_count AS emp, s.founded_year AS founded, "
            "s.headquarters AS hq, s.risk_flags AS flags, s.website AS website, s.state_owned AS soe",
            {"name": name}
        )
        upstream = neo4j_query(
            "MATCH (s:Supplier {name:$name})-[r:SOURCED_FROM]->(u) "
            "RETURN coalesce(u.name,u.sku) AS uname, u.country AS ucountry, "
            "r.component AS comp, r.contract_value_eur AS val, r.lead_time_days AS lead "
            "LIMIT 15", {"name": name}
        )
        downstream = neo4j_query(
            "MATCH (n)-[:SOURCED_FROM|SUPPLIED_BY]->(s:Supplier {name:$name}) "
            "RETURN coalesce(n.name,n.sku) AS dname, labels(n)[0] AS dtype, "
            "r.component AS comp LIMIT 10" if False else
            "MATCH (n)-[r:SOURCED_FROM|SUPPLIED_BY]->(s:Supplier {name:$name}) "
            "RETURN coalesce(n.name,n.sku) AS dname, labels(n)[0] AS dtype, r.component AS comp LIMIT 10",
            {"name": name}
        )
        certs = neo4j_query(
            "MATCH (s:Supplier {name:$name})-[:CERTIFIED_BY]->(c:Certificate) "
            "RETURN c.name AS cert_name, c.issuer AS issuer, c.valid_until AS valid_until",
            {"name": name}
        )
        events = neo4j_query(
            "MATCH (s:Supplier {name:$name})-[:AFFECTED_BY]->(e:Event) "
            "RETURN e.name AS ename, e.date AS date, e.impact AS impact, "
            "e.description AS desc, e.lesson AS lesson ORDER BY e.date DESC",
            {"name": name}
        )
    except Exception as exc:
        return f"Fact sheet generation failed for {name}: {exc}"

    p = profiles[0] if profiles else {}

    def fmt_eur(n):
        if not n: return "N/A"
        if n >= 1e9: return f"€{n/1e9:.1f}B"
        if n >= 1e6: return f"€{n/1e6:.0f}M"
        return f"€{n:.0f}"

    lines = [
        f"SUPPLIER FACT SHEET — {name}",
        f"Generated: {time.strftime('%Y-%m-%d')} UTC",
        f"Source: UC4 Supply Chain Knowledge Graph",
        "=" * 60, "",
        f"Tier: {p.get('tier','N/A')}",
        f"Country: {p.get('country','N/A')}",
        f"Annual Revenue: {fmt_eur(p.get('rev'))}",
        f"Employees: {p.get('emp',0):,}" if p.get('emp') else "Employees: N/A",
        f"Founded: {p.get('founded','N/A')}",
        f"HQ: {p.get('hq','N/A')}",
        f"State-owned: {'Yes' if p.get('soe') else 'No'}",
        f"Website: {p.get('website','N/A')}", "",
    ]

    if p.get("flags"):
        lines += ["RISK FLAGS:", *[f"  - {f}" for f in p["flags"]], ""]

    if certs:
        lines += ["CERTIFICATIONS:"]
        for c in certs:
            lines.append(f"  - {c['cert_name']} ({c.get('issuer','?')}, valid until {c.get('valid_until','?')})")
        lines.append("")

    if upstream:
        lines += ["UPSTREAM SUPPLY (sources from):"]
        for u in upstream:
            parts = [x for x in [u.get("comp"), fmt_eur(u.get("val")), f"{u.get('lead')}d" if u.get('lead') else None] if x]
            lines.append(f"  - {u['uname']} ({u.get('ucountry','?')})" + (f": {', '.join(parts)}" if parts else ""))
        lines.append("")

    if downstream:
        lines += ["DOWNSTREAM (supplies to):"]
        for d in downstream:
            lines.append(f"  - {d['dname']} [{d.get('dtype','?')}]" + (f": {d['comp']}" if d.get("comp") else ""))
        lines.append("")

    if events:
        lines += ["DISRUPTION EVENTS:"]
        for e in events:
            lines.append(f"  [{e.get('date','?')}] {e['ename']} (Impact: {e.get('impact','?')})")
            if e.get("desc"): lines.append(f"    {e['desc']}")
            if e.get("lesson"): lines.append(f"    Lesson: {e['lesson']}")
        lines.append("")

    lines += ["=" * 60,
              "Auto-generated from UC4 Neo4j graph. Verify against official supplier docs."]
    return "\n".join(lines)


def check_kotaemon() -> bool:
    """Return True if Kotaemon is reachable."""
    try:
        req = urllib.request.Request(f"{KOTAEMON_URL}/", method="HEAD")
        urllib.request.urlopen(req, timeout=8)
        return True
    except Exception as exc:
        print(f"  Kotaemon unreachable at {KOTAEMON_URL}: {exc}")
        return False


def scrape_url(url: str, timeout: int = 35) -> str | None:
    """Scrape a URL via Browserless CT400."""
    try:
        body = json.dumps({"url": url, "wait_for": 2000}).encode()
        req = urllib.request.Request(
            f"{BROWSERLESS}/scrape",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read())
        html = data.get("html", "")
        # Strip tags minimally
        import re
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:8000] if text else None
    except Exception as exc:
        print(f"    Browserless failed ({url[:50]}): {exc}")
        return None


def upload_to_kotaemon(filename: str, content: bytes, content_type: str = "text/plain") -> bool:
    """Upload a file to Kotaemon via Gradio /upload endpoint."""
    boundary = ("----UC4Ingest" + uuid.uuid4().hex[:8]).encode()
    body = (
        b"--" + boundary + b"\r\n"
        b'Content-Disposition: form-data; name="files"; filename="' + filename.encode() + b'"\r\n'
        b"Content-Type: " + content_type.encode() + b"\r\n\r\n"
        + content
        + b"\r\n--" + boundary + b"--\r\n"
    )
    try:
        req = urllib.request.Request(
            f"{KOTAEMON_URL}/upload",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary.decode()}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read())
        # Gradio returns list of file paths
        if isinstance(resp, list) and resp:
            return True
        return False
    except urllib.error.HTTPError as exc:
        # 404 on /upload — try /queue/join with file content inline
        if exc.code == 404:
            return upload_via_queue(filename, content)
        print(f"    Upload HTTP error {exc.code}: {exc}")
        return False
    except Exception as exc:
        print(f"    Upload failed: {exc}")
        return False


def upload_via_queue(filename: str, content: bytes) -> bool:
    """Fallback: use Gradio queue API to ingest text content directly."""
    try:
        text = content.decode("utf-8", errors="replace")
        body = json.dumps({
            "data": [text[:6000], filename],
            "fn_index": 1,
            "session_hash": uuid.uuid4().hex[:8],
        }).encode()
        req = urllib.request.Request(
            f"{KOTAEMON_URL}/queue/join",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            json.loads(r.read())
        return True
    except Exception as exc:
        print(f"    Queue ingest failed: {exc}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Kotaemon Document Ingestor")
    parser.add_argument("--skip-scrape", action="store_true", help="Skip live website scraping")
    parser.add_argument("--dry-run",     action="store_true", help="List docs, don't upload")
    parser.add_argument("--supplier",    help="Ingest only this specific supplier name")
    parser.add_argument("--neo4j-only",  action="store_true", help="Only run Neo4j fact-sheet step")
    args = parser.parse_args()

    print(f"UC4 Kotaemon Ingestor — {KOTAEMON_URL}")
    print("=" * 60)

    if not args.dry_run:
        if not check_kotaemon():
            print("\nKotaemon not reachable. Deploy first:")
            print(f"  ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/deploy_kotaemon.yml")
            sys.exit(1)
        print("  Kotaemon: OK")

    uploaded = 0
    failed   = 0

    # 1. Synthetic supplier profiles
    print("\n[1] Synthetic supplier profiles:")
    for filename, content in SYNTHETIC_DOCS:
        size = len(content.encode())
        if args.dry_run:
            print(f"  WOULD UPLOAD: {filename} ({size} bytes)")
            continue
        print(f"  {filename} ({size} bytes) ... ", end="", flush=True)
        ok = upload_to_kotaemon(filename, content.strip().encode())
        if ok:
            print("OK"); uploaded += 1
        else:
            print("FAILED"); failed += 1

    # 2. Local data files
    print("\n[2] Local data files:")
    local_files = [
        (os.path.join(REPO_ROOT, "data", "sample_supplier_text.txt"), "text/plain"),
        (os.path.join(REPO_ROOT, "data", "sample_companies.csv"),     "text/csv"),
    ]
    for fpath, ctype in local_files:
        if not os.path.exists(fpath):
            print(f"  SKIP (not found): {fpath}")
            continue
        fname = os.path.basename(fpath)
        with open(fpath, "rb") as f:
            content = f.read()
        if args.dry_run:
            print(f"  WOULD UPLOAD: {fname} ({len(content)} bytes)")
            continue
        print(f"  {fname} ({len(content)} bytes) ... ", end="", flush=True)
        ok = upload_to_kotaemon(fname, content, ctype)
        if ok: print("OK"); uploaded += 1
        else:  print("FAILED"); failed += 1

    # 3. PDF directory
    pdf_dir = os.path.join(REPO_ROOT, "data", "pdfs")
    if os.path.isdir(pdf_dir):
        print("\n[3] PDF supplier documents:")
        for fname in os.listdir(pdf_dir):
            if not fname.endswith(".pdf"):
                continue
            fpath = os.path.join(pdf_dir, fname)
            with open(fpath, "rb") as f:
                content = f.read()
            if args.dry_run:
                print(f"  WOULD UPLOAD: {fname} ({len(content)} bytes)")
                continue
            print(f"  {fname} ({len(content)} bytes) ... ", end="", flush=True)
            ok = upload_to_kotaemon(fname, content, "application/pdf")
            if ok: print("OK"); uploaded += 1
            else:  print("FAILED"); failed += 1
    else:
        print(f"\n[3] PDF dir not found ({pdf_dir}) — skip. Add PDFs there to ingest.")

    # 4. Live scraping
    if not args.skip_scrape:
        print("\n[4] Live supplier website scraping (via Browserless CT400):")
        for sup_name, url in SUPPLIER_SITES:
            fname = sup_name.replace(" ", "_") + "_web.txt"
            if args.dry_run:
                print(f"  WOULD SCRAPE+UPLOAD: {sup_name} ({url})")
                continue
            print(f"  {sup_name} ({url[:45]}) ... ", end="", flush=True)
            text = scrape_url(url)
            if text:
                content = f"[Scraped: {sup_name}]\nURL: {url}\n\n{text}".encode()
                ok = upload_to_kotaemon(fname, content)
                if ok: print(f"OK ({len(text)} chars)"); uploaded += 1
                else:  print("upload failed"); failed += 1
            else:
                print("scrape failed"); failed += 1
            time.sleep(1)  # be polite

    # 5. Neo4j-derived fact sheets for all graph suppliers
    print("\n[5] Neo4j-derived supplier fact sheets:")
    try:
        cypher = "MATCH (s:Supplier) WHERE s.demo = true"
        if args.supplier:
            cypher += f" AND s.name = '{args.supplier}'"
        cypher += " RETURN s.name AS name ORDER BY s.tier, s.name"
        all_suppliers = neo4j_query(cypher)
        print(f"  Found {len(all_suppliers)} suppliers in graph")
        for row in all_suppliers:
            sname = row["name"]
            fname = sname.lower().replace(" ", "_").replace("/","_") + "_neo4j_factsheet.txt"
            if args.dry_run:
                print(f"  WOULD GENERATE+UPLOAD: {fname}")
                continue
            print(f"  {sname} ... ", end="", flush=True)
            try:
                fact_sheet = generate_neo4j_fact_sheet(sname)
                ok = upload_to_kotaemon(fname, fact_sheet.encode("utf-8"))
                if ok:
                    print(f"OK ({len(fact_sheet)} chars)"); uploaded += 1
                else:
                    print("upload failed"); failed += 1
            except Exception as exc:
                print(f"ERROR: {exc}"); failed += 1
    except Exception as exc:
        print(f"  Neo4j unavailable: {exc} — skipping step 5")

    print(f"\n{'─'*60}")
    if args.dry_run:
        total = len(SYNTHETIC_DOCS) + 2 + len(SUPPLIER_SITES)
        print(f"Dry run complete. Would upload ~{total} documents.")
    else:
        print(f"Done: {uploaded} uploaded, {failed} failed.")
        if uploaded > 0:
            print(f"\nOpen Kotaemon at {KOTAEMON_URL}")
            print("Collections → 'Default' → documents should appear.")
            print("Test query: 'Who supplies raw materials to Infineon Technologies?'")


if __name__ == "__main__":
    main()
