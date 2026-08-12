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
LITELLM      = os.getenv("LITELLM_URL",          "http://10.0.2.205:4000")
LITELLM_KEY  = os.getenv("LITELLM_KEY",          "")

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
