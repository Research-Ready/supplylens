#!/usr/bin/env bash
# UC4 Supply Chain — 8-step dry run
# Run from repo root: bash usecases/uc4-supply-chain/scripts/dry_run.sh
# Requires VPN active and Proxmox quorum

set -euo pipefail
UC4_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PASS=0
FAIL=0
ERRORS=()

log()  { echo "[$(date '+%H:%M:%S')] $*"; }
ok()   { log "PASS: $1"; PASS=$((PASS+1)); }
fail() { log "FAIL: $1"; FAIL=$((FAIL+1)); ERRORS+=("$1"); }

# ---------------------------------------------------------------------------
# Credentials from UC4 passwords.kdbx (master: SupplyChainBaby100!)
# ---------------------------------------------------------------------------
NEO4J_PW=$(python3 -c "
from pykeepass import PyKeePass
kp = PyKeePass('$UC4_DIR/passwords.kdbx', password='SupplyChainBaby100!')
e = kp.find_entries(title='Neo4j', first=True)
print(e.password if e else 'NOT_FOUND')
")

LITELLM_KEY=$(python3 -c "
from pykeepass import PyKeePass
kp = PyKeePass('$UC4_DIR/passwords.kdbx', password='SupplyChainBaby100!')
e = kp.find_entries(title='LiteLLM', first=True)
print(e.password if e else 'NOT_FOUND')
")

QDRANT_KEY=$(python3 -c "
from pykeepass import PyKeePass
kp = PyKeePass('$UC4_DIR/passwords.kdbx', password='SupplyChainBaby100!')
e = kp.find_entries(title='Qdrant', first=True)
print(e.password if e else 'NOT_FOUND')
")

SUPERSET_PW=$(python3 -c "
from pykeepass import PyKeePass
kp = PyKeePass('$UC4_DIR/passwords.kdbx', password='SupplyChainBaby100!')
e = kp.find_entries(title='Superset', first=True)
print(e.password if e else 'NOT_FOUND')
")

log "Credentials loaded from passwords.kdbx"

# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------
log "=== PRE-FLIGHT CHECK ==="

BASTION="root@10.0.0.16"

check_http() {
    local name="$1" url="$2" expected="$3"
    code=$(ssh -o StrictHostKeyChecking=accept-new "$BASTION" \
        "curl -s -o /dev/null -w '%{http_code}' --connect-timeout 5 '$url'" 2>/dev/null || echo "000")
    if [[ "$code" == "$expected" ]]; then
        ok "Pre-flight $name ($code)"
    else
        fail "Pre-flight $name — expected $expected got $code ($url)"
    fi
}

check_http "Neo4j"                  "http://10.0.1.114:7474/"           "200"
check_http "LangGraph"              "http://10.0.1.119:8000/health"     "200"
check_http "Browserless-prod"       "http://10.0.5.100:3500/health"     "200"
# CT306 (Browserless-acc) not provisioned — pipeline uses CT400 (prod) for all scraping
check_http "Unstructured"           "http://10.0.1.117:8000/health"     "200"
check_http "Tika"                   "http://10.0.1.115:9998/tika"       "200"
check_http "Qdrant"                 "http://10.0.1.102:6333/healthz"    "200"
check_http "LiteLLM"                "http://10.0.2.205:4000/health/liveliness" "200"
check_http "Superset"               "http://10.0.2.206:8088/health"     "200"
check_http "Metabase"               "http://10.0.2.202:3000/api/health" "200"

# ---------------------------------------------------------------------------
# Step 1 — Neo4j: seed supply chain graph
# ---------------------------------------------------------------------------
log "=== STEP 1: Neo4j seed ==="

SEED_RESULT=$(ssh -o StrictHostKeyChecking=accept-new -o ProxyJump=root@10.0.0.16 root@10.0.1.114 "python3 -c \"
import urllib.request, json, base64
auth = base64.b64encode(b'neo4j:$NEO4J_PW').decode()
base = 'http://localhost:7474/db/neo4j/tx/commit'
headers = {'Content-Type': 'application/json', 'Authorization': 'Basic ' + auth}
queries = [
    'MERGE (p:Product {sku: \\\"BTN-001\\\", name: \\\"Button 12mm\\\", category: \\\"Fasteners\\\"})',
    'MERGE (s1:Supplier {name: \\\"AMS Buttons BV\\\", country: \\\"Netherlands\\\", tier: 1})',
    'MERGE (s2:Supplier {name: \\\"Shenzhen Metal Co\\\", country: \\\"China\\\", tier: 2})',
    'MERGE (r1:RawMaterial {name: \\\"Plastic Pellets\\\", origin: \\\"Germany\\\", material_type: \\\"Polymer\\\"})',
    'MERGE (r2:RawMaterial {name: \\\"Metal Pins\\\", origin: \\\"China\\\", material_type: \\\"Steel\\\"})',
    'MATCH (p:Product {sku: \\\"BTN-001\\\"}), (s:Supplier {name: \\\"AMS Buttons BV\\\"}) MERGE (p)-[:SUPPLIED_BY]->(s)',
    'MATCH (s1:Supplier {name: \\\"AMS Buttons BV\\\"}), (s2:Supplier {name: \\\"Shenzhen Metal Co\\\"}) MERGE (s1)-[:SOURCED_FROM]->(s2)',
    'MATCH (s1:Supplier {name: \\\"AMS Buttons BV\\\"}), (r1:RawMaterial {name: \\\"Plastic Pellets\\\"}) MERGE (s1)-[:SOURCED_FROM]->(r1)',
    'MATCH (s2:Supplier {name: \\\"Shenzhen Metal Co\\\"}), (r2:RawMaterial {name: \\\"Metal Pins\\\"}) MERGE (s2)-[:SOURCED_FROM]->(r2)',
]
errs = 0
for q in queries:
    req = urllib.request.Request(base,
        data=json.dumps({'statements': [{'statement': q}]}).encode(),
        headers=headers, method='POST')
    r = urllib.request.urlopen(req)
    d = json.loads(r.read())
    if d.get('errors'): errs += 1
print('SEED_OK' if errs == 0 else 'SEED_FAIL')
\"" 2>/dev/null || echo "SSH_FAIL")

if [[ "$SEED_RESULT" == *"SEED_OK"* ]]; then ok "Step 1 Neo4j seed"; else fail "Step 1 Neo4j seed — $SEED_RESULT"; fi

# ---------------------------------------------------------------------------
# Step 2 — Neo4j: backward traversal
# ---------------------------------------------------------------------------
log "=== STEP 2: Neo4j traversal ==="

TRAVERSE_RESULT=$(ssh -o StrictHostKeyChecking=accept-new -o ProxyJump=root@10.0.0.16 root@10.0.1.114 "python3 << 'PYEOF'
import urllib.request, json, base64
auth = base64.b64encode('neo4j:$NEO4J_PW'.encode()).decode()
query = 'MATCH path = (p:Product {sku: \"BTN-001\"})-[:SUPPLIED_BY|SOURCED_FROM*1..5]->(n) RETURN [node in nodes(path) | coalesce(node.name, node.sku)] AS chain, length(path) AS depth ORDER BY depth'
req = urllib.request.Request(
    'http://localhost:7474/db/neo4j/tx/commit',
    data=json.dumps({'statements': [{'statement': query}]}).encode(),
    headers={'Content-Type': 'application/json', 'Authorization': 'Basic ' + auth},
    method='POST'
)
r = urllib.request.urlopen(req)
d = json.loads(r.read())
rows = d['results'][0]['data']
print(f'PATHS:{len(rows)}')
PYEOF" 2>/dev/null || echo "SSH_FAIL")

PATH_COUNT=$(echo "$TRAVERSE_RESULT" | grep -o 'PATHS:[0-9]*' | cut -d: -f2 || echo "0")
if [[ "${PATH_COUNT:-0}" -ge 4 ]]; then
    ok "Step 2 Neo4j traversal ($PATH_COUNT paths)"
else
    fail "Step 2 Neo4j traversal — expected >=4 paths, got ${PATH_COUNT:-0}"
fi

# ---------------------------------------------------------------------------
# Step 3 — Browserless scrape via pct exec on node-4
# NOTE: CT400 has no SSH keys. Use pct exec 400 on root@10.0.0.18.
# NOTE: Endpoint is /scrape (NOT /chromium/content). Port is 3500.
# ---------------------------------------------------------------------------
log "=== STEP 3: Browserless scrape ==="

SCRAPE_RESULT="SSH_FAIL"
for _attempt in 1 2 3; do
    _try=$(ssh -i ~/.ssh/proxmox_node3 -o StrictHostKeyChecking=accept-new root@10.0.0.18 \
        "pct exec 400 -- python3 -c \"
import urllib.request, json
req = urllib.request.Request(
    'http://localhost:3500/scrape',
    data=json.dumps({'url': 'https://example.com'}).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST'
)
try:
    r = urllib.request.urlopen(req, timeout=35)
    d = json.loads(r.read())
    html = d.get('html', '')
    print('SCRAPE_OK' if 'Example Domain' in html else 'CONTENT_FAIL')
    print(f'CHARS:{len(html)}')
except Exception as e:
    print(f'RETRY:{e}')
\"" 2>/dev/null || true)
    if [[ "$_try" == *"SCRAPE_OK"* ]]; then
        SCRAPE_RESULT="$_try"
        break
    fi
    log "Step 3 attempt $_attempt failed, retrying..."
done

if [[ "$SCRAPE_RESULT" == *"SCRAPE_OK"* ]]; then
    CHARS=$(echo "$SCRAPE_RESULT" | grep -o 'CHARS:[0-9]*' | cut -d: -f2 || echo "0")
    ok "Step 3 Browserless scrape ($CHARS chars)"
else
    fail "Step 3 Browserless scrape — $SCRAPE_RESULT"
fi

# ---------------------------------------------------------------------------
# Step 4 — Unstructured extracts supplier HTML
# NOTE: Must use multipart/form-data with 'files' field. Plain text/html body = 422.
# ---------------------------------------------------------------------------
log "=== STEP 4: Unstructured extract ==="

UNSTRUCTURED_RESULT=$(ssh -o StrictHostKeyChecking=accept-new -o ProxyJump=root@10.0.0.16 root@10.0.1.117 "python3 << 'PYEOF'
import urllib.request, json
supplier_html = b'''<html><body>
<h1>AMS Buttons BV - Supplier Profile</h1>
<p>Founded 1987. ISO 9001:2015 certified.</p>
<p>Specialization: plastic and metal buttons, fasteners.</p>
<p>Key materials: ABS plastic from BASF (Germany), steel pins from China.</p>
<p>Annual capacity: 50 million units. Key customers: H&M, Zara, C&A.</p>
<p>Tier 1 supplier for Dutch textile industry.</p>
</body></html>'''
boundary = b'----WebKitFormBoundary7MA4YWxkTrZu0gW'
body = (
    b'--' + boundary + b'\r\n'
    b'Content-Disposition: form-data; name=\"files\"; filename=\"supplier.html\"\r\n'
    b'Content-Type: text/html\r\n'
    b'\r\n' + supplier_html +
    b'\r\n--' + boundary + b'--\r\n'
)
req = urllib.request.Request(
    'http://localhost:8000/general/v0/general',
    data=body,
    headers={
        'Content-Type': 'multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW',
        'Accept': 'application/json'
    },
    method='POST'
)
r = urllib.request.urlopen(req, timeout=30)
elements = json.loads(r.read())
texts = [el['text'] for el in elements if el.get('text')]
print(f'ELEMENTS:{len(texts)}')
PYEOF" 2>/dev/null || echo "SSH_FAIL")

ELEM_COUNT=$(echo "$UNSTRUCTURED_RESULT" | grep -o 'ELEMENTS:[0-9]*' | cut -d: -f2 || echo "0")
if [[ "${ELEM_COUNT:-0}" -ge 3 ]]; then
    ok "Step 4 Unstructured extract ($ELEM_COUNT elements)"
else
    fail "Step 4 Unstructured extract — expected >=3 elements, got ${ELEM_COUNT:-0}"
fi

# ---------------------------------------------------------------------------
# Step 5 — LiteLLM: infer missing supply chain links
# ---------------------------------------------------------------------------
log "=== STEP 5: LiteLLM inference ==="

LLM_RESULT=$(ssh -o StrictHostKeyChecking=accept-new "$BASTION" "python3 -c \"
import urllib.request, json
req = urllib.request.Request(
    'http://10.0.2.205:4000/v1/chat/completions',
    data=json.dumps({'model':'researcher-llm','messages':[{'role':'user','content':'Supplier: AMS Buttons BV (Netherlands). Makes plastic buttons using ABS plastic from BASF Germany and metal pins from Shenzhen. What 3 other raw materials are likely in their supply chain? JSON array only with keys: name, origin, material_type'}],'max_tokens':300}).encode(),
    headers={'Authorization':'Bearer $LITELLM_KEY','Content-Type':'application/json'},
    method='POST'
)
try:
    r = urllib.request.urlopen(req, timeout=120)
    print(r.read().decode())
except Exception as e:
    print(json.dumps({'error':str(e)}))
\"" 2>/dev/null || echo '{"error":"ssh_fail"}')

if echo "$LLM_RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'choices' in d" 2>/dev/null; then
    ok "Step 5 LiteLLM inference"
else
    fail "Step 5 LiteLLM inference — $(echo "$LLM_RESULT" | head -c 200)"
fi

# ---------------------------------------------------------------------------
# Step 6 — Neo4j: store inferred links
# ---------------------------------------------------------------------------
log "=== STEP 6: Neo4j store inferred link ==="

INFER_RESULT=$(ssh -o StrictHostKeyChecking=accept-new -o ProxyJump=root@10.0.0.16 root@10.0.1.114 "python3 -c \"
import urllib.request, json, base64
auth = base64.b64encode(b'neo4j:$NEO4J_PW').decode()
base = 'http://localhost:7474/db/neo4j/tx/commit'
headers = {'Content-Type': 'application/json', 'Authorization': 'Basic ' + auth}
q = 'MERGE (r:RawMaterial {name: \\\"Textile Dye\\\", origin: \\\"India\\\", material_type: \\\"Chemical\\\", inferred: true}) WITH r MATCH (s:Supplier {name: \\\"AMS Buttons BV\\\"}) MERGE (s)-[:SOURCED_FROM {confidence: 0.7, source: \\\"LLM inference\\\"}]->(r)'
req = urllib.request.Request(base,
    data=json.dumps({'statements': [{'statement': q}]}).encode(),
    headers=headers, method='POST')
r = urllib.request.urlopen(req)
d = json.loads(r.read())
print('INFER_OK' if not d.get('errors') else 'INFER_FAIL')
\"" 2>/dev/null || echo "SSH_FAIL")

if [[ "$INFER_RESULT" == *"INFER_OK"* ]]; then ok "Step 6 Neo4j inferred link stored"; else fail "Step 6 Neo4j inferred link — $INFER_RESULT"; fi

# ---------------------------------------------------------------------------
# Step 7 — Qdrant embedding via LiteLLM (nomic-embed-text, 768 dims)
# NOTE: text-embedding-3-small is NOT configured — use ollama/nomic-embed-text
# ---------------------------------------------------------------------------
log "=== STEP 7: Qdrant embedding ==="

EMB_RESULT=$(ssh -o StrictHostKeyChecking=accept-new -o ProxyJump=root@10.0.0.16 root@10.0.1.100 "python3 << 'PYEOF'
import urllib.request, json
LITELLM_KEY = '$LITELLM_KEY'
emb_req = urllib.request.Request(
    'http://10.0.2.205:4000/v1/embeddings',
    data=json.dumps({'model': 'ollama/nomic-embed-text', 'input': 'who supplies raw materials to button manufacturers?'}).encode(),
    headers={'Authorization': 'Bearer ' + LITELLM_KEY, 'Content-Type': 'application/json'},
    method='POST'
)
r = urllib.request.urlopen(emb_req, timeout=30)
d = json.loads(r.read())
embedding = d['data'][0]['embedding']
print(f'DIMS:{len(embedding)}')
PYEOF" 2>/dev/null || echo "SSH_FAIL")

DIMS=$(echo "$EMB_RESULT" | grep -o 'DIMS:[0-9]*' | cut -d: -f2 || echo "0")
if [[ "${DIMS:-0}" -ge 768 ]]; then
    ok "Step 7 embedding via nomic-embed-text ($DIMS dims)"
else
    fail "Step 7 embedding — expected 768 dims, got ${DIMS:-0}"
fi

# ---------------------------------------------------------------------------
# Step 8 — Superset dashboard login (JWT)
# ---------------------------------------------------------------------------
log "=== STEP 8: Superset dashboard login ==="

SUPERSET_TOKEN=$(ssh -o StrictHostKeyChecking=accept-new "$BASTION" "python3 -c \"
import urllib.request, json
req = urllib.request.Request(
    'http://10.0.2.206:8088/api/v1/security/login',
    data=json.dumps({'username':'admin','password':'$SUPERSET_PW','provider':'db'}).encode(),
    headers={'Content-Type':'application/json'},
    method='POST'
)
try:
    r = urllib.request.urlopen(req, timeout=10)
    d = json.loads(r.read())
    print(d.get('access_token','FAIL'))
except Exception as e:
    print('FAIL')
\"" 2>/dev/null || echo "FAIL")

if [[ "$SUPERSET_TOKEN" != "FAIL" && ${#SUPERSET_TOKEN} -gt 10 ]]; then
    ok "Step 8 Superset login (token ${SUPERSET_TOKEN:0:15}...)"
else
    fail "Step 8 Superset login failed (try: ssh -J root@10.0.0.15 root@10.0.2.206 systemctl restart superset)"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "============================================"
echo "UC4 DRY RUN COMPLETE: $PASS passed, $FAIL failed"
echo "============================================"
if [[ ${#ERRORS[@]} -gt 0 ]]; then
    echo "FAILURES:"
    for e in "${ERRORS[@]}"; do echo "  - $e"; done
    exit 1
fi
echo "All steps passed."
