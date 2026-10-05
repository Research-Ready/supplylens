#!/usr/bin/env python3
"""UC4 local-stack dry run — tests Docker Compose services on localhost.

Usage:
    python3 scripts/dry_run_local.py
    python3 scripts/dry_run_local.py --json-only   # write JSON, no stdout steps

Steps 3, 4, 8 are skipped (browserless/unstructured/superset not in local stack).
JSON written to test-results/dry_run_local_YYYYMMDD_HHMMSS.json
"""
import argparse, base64, json, os, sys, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
NEO4J_PASS = os.environ.get("NEO4J_PASSWORD", "bmtKQuCO9vOzyBwyVvt2LrFU")
LITELLM_KEY = os.environ.get("LITELLM_KEY", "sk-localstack-5WU8JxXMD2zvhogkbVaY")

steps: list[dict] = []

def record(name: str, status: str, detail: str = ""):
    icon = {"PASS": "✓", "FAIL": "✗", "SKIP": "–"}[status]
    print(f"  {icon} {name}" + (f" — {detail}" if detail else ""))
    steps.append({"name": name, "status": status, "detail": detail})

def http_json(url, body=None, headers=None, timeout=10):
    req = urllib.request.Request(url, data=body, headers=headers or {}, method="POST" if body else "GET")
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())

def neo4j(cypher: str):
    auth = base64.b64encode(f"neo4j:{NEO4J_PASS}".encode()).decode()
    return http_json(
        "http://localhost:7474/db/neo4j/tx/commit",
        json.dumps({"statements": [{"statement": cypher}]}).encode(),
        {"Content-Type": "application/json", "Authorization": f"Basic {auth}"},
    )

# ── Pre-flight ──────────────────────────────────────────────────────────────
print("=== PRE-FLIGHT ===")
for svc, url, expect in [
    ("Neo4j",     "http://localhost:7474/",                   200),
    ("Qdrant",    "http://localhost:6333/healthz",             200),
    ("LiteLLM",   "http://localhost:4000/health/liveliness",  200),
    ("LangGraph", "http://localhost:8000/health",              200),
    ("n8n",       "http://localhost:5678/",                    200),
]:
    try:
        code = urllib.request.urlopen(urllib.request.Request(url), timeout=5).status
    except Exception:
        code = 0
    (record if code == expect else record)(
        f"Pre-flight {svc}", "PASS" if code == expect else "FAIL", f"HTTP {code}"
    )

# ── Step 1 — Neo4j seed ─────────────────────────────────────────────────────
print("\n=== STEP 1: Neo4j seed ===")
try:
    for q in [
        'MERGE (p:Product {sku:"BTN-001",name:"Button 12mm",demo:true})',
        'MERGE (s1:Supplier {name:"AMS Buttons BV",country:"NL",tier:1,demo:true})',
        'MERGE (s2:Supplier {name:"Shenzhen Metal Co",country:"CN",tier:2,demo:true})',
        'MERGE (r1:RawMaterial {name:"Plastic Pellets",origin:"DE",material_type:"Polymer",demo:true})',
        'MERGE (r2:RawMaterial {name:"Metal Pins",origin:"CN",material_type:"Steel",demo:true})',
        'MATCH (p:Product {sku:"BTN-001"}),(s:Supplier {name:"AMS Buttons BV"}) MERGE (p)-[:SUPPLIED_BY]->(s)',
        'MATCH (s1:Supplier {name:"AMS Buttons BV"}),(s2:Supplier {name:"Shenzhen Metal Co"}) MERGE (s1)-[:SOURCED_FROM]->(s2)',
        'MATCH (s1:Supplier {name:"AMS Buttons BV"}),(r:RawMaterial {name:"Plastic Pellets"}) MERGE (s1)-[:SOURCED_FROM]->(r)',
        'MATCH (s2:Supplier {name:"Shenzhen Metal Co"}),(r:RawMaterial {name:"Metal Pins"}) MERGE (s2)-[:SOURCED_FROM]->(r)',
    ]:
        d = neo4j(q)
        if d.get("errors"):
            raise RuntimeError(d["errors"])
    record("Step 1 Neo4j seed", "PASS")
except Exception as e:
    record("Step 1 Neo4j seed", "FAIL", str(e)[:120])

# ── Step 2 — Neo4j traversal ────────────────────────────────────────────────
print("\n=== STEP 2: Neo4j traversal ===")
try:
    d = neo4j('MATCH path=(p:Product {sku:"BTN-001"})-[:SUPPLIED_BY|SOURCED_FROM*1..5]->(n) RETURN length(path) AS depth')
    paths = len(d["results"][0]["data"])
    if paths >= 4:
        record("Step 2 Neo4j traversal", "PASS", f"{paths} paths")
    else:
        record("Step 2 Neo4j traversal", "FAIL", f"expected >=4, got {paths}")
except Exception as e:
    record("Step 2 Neo4j traversal", "FAIL", str(e)[:120])

# ── Steps 3, 4 — skipped (not in local stack) ───────────────────────────────
print("\n=== STEPS 3, 4: skipped ===")
record("Step 3 Browserless scrape", "SKIP", "not in local Docker Compose stack")
record("Step 4 Unstructured extract", "SKIP", "not in local Docker Compose stack")

# ── Step 5 — LiteLLM inference ──────────────────────────────────────────────
print("\n=== STEP 5: LiteLLM inference ===")
try:
    d = http_json(
        "http://localhost:4000/v1/chat/completions",
        json.dumps({"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "Reply: INFERENCE_OK"}], "max_tokens": 10}).encode(),
        {"Authorization": f"Bearer {LITELLM_KEY}", "Content-Type": "application/json"},
        timeout=60,
    )
    record("Step 5 LiteLLM inference", "PASS" if "choices" in d else "FAIL")
except Exception as e:
    record("Step 5 LiteLLM inference", "FAIL", str(e)[:120])

# ── Step 6 — Neo4j inferred link ────────────────────────────────────────────
print("\n=== STEP 6: Neo4j inferred link ===")
try:
    d = neo4j('MERGE (r:RawMaterial {name:"Textile Dye",origin:"IN",inferred:true,demo:true}) WITH r MATCH (s:Supplier {name:"AMS Buttons BV"}) MERGE (s)-[:SOURCED_FROM {confidence:0.7,source:"LLM inference"}]->(r)')
    if d.get("errors"):
        raise RuntimeError(d["errors"])
    record("Step 6 Neo4j inferred link", "PASS")
except Exception as e:
    record("Step 6 Neo4j inferred link", "FAIL", str(e)[:120])

# ── Step 7 — Embedding ──────────────────────────────────────────────────────
print("\n=== STEP 7: Qdrant embedding ===")
try:
    d = http_json(
        "http://localhost:4000/v1/embeddings",
        json.dumps({"model": "nomic-embed-text", "input": "supply chain raw materials"}).encode(),
        {"Authorization": f"Bearer {LITELLM_KEY}", "Content-Type": "application/json"},
        timeout=30,
    )
    dims = len(d["data"][0]["embedding"])
    record("Step 7 embedding", "PASS" if dims >= 100 else "FAIL", f"{dims} dims")
except Exception as e:
    record("Step 7 embedding", "FAIL", str(e)[:120])

# ── Step 8 — skipped ────────────────────────────────────────────────────────
print("\n=== STEP 8: skipped ===")
record("Step 8 Superset login", "SKIP", "not in local Docker Compose stack")

# ── JSON output ─────────────────────────────────────────────────────────────
passed = sum(1 for s in steps if s["status"] == "PASS")
failed = sum(1 for s in steps if s["status"] == "FAIL")
ts = datetime.now(timezone.utc)
out = ROOT / "test-results" / f"dry_run_local_{ts.strftime('%Y%m%d_%H%M%S')}.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps({
    "timestamp": ts.isoformat(),
    "stack": "local",
    "passed": passed,
    "failed": failed,
    "status": "PASS" if failed == 0 else "FAIL",
    "steps": steps,
}, indent=2))

print(f"\n{'='*44}")
print(f"LOCAL DRY RUN: {passed} passed, {failed} failed")
print(f"Results: {out}")
print(f"{'='*44}")
sys.exit(0 if failed == 0 else 1)
