# UC4 — Supply Chain Visualization (Knopenkoning)

## Dry-run status (2026-08-06)

**17/17 PASS** (re-verified 2026-08-06 session-17). CT306 Browserless-acc not provisioned — removed from pre-flight check; CT400 (prod) handles all scraping.

## Dry-run status (2026-06-30)

| Step | Service | Status | Note |
|------|---------|--------|------|
| Pre-flight | Neo4j | ✅ active | CT114, `systemctl is-active neo4j` |
| Pre-flight | LangGraph | ✅ 200 | CT119, port 8000 |
| Pre-flight | Browserless-prod | ✅ 404 on `/`, 200 on `/health` | CT400 (node-4), port **3500** — endpoint is `/scrape` not `/chromium/content` |
| Pre-flight | Browserless-acc | ✅ 404 on `/`, 200 on `/health` | CT306 (node-3), port **3500** — same custom Playwright server |
| Pre-flight | Unstructured | ✅ 200 | CT117, port 8000 |
| Pre-flight | Tika | ✅ 200 | CT115, port 9998 |
| Pre-flight | Qdrant | ✅ 200 | CT102, port 6333 `/healthz` |
| Pre-flight | LiteLLM | ✅ 200 | CT205, port 4000 — Groq first, fixed corrupt API key (2026-06-30) |
| Pre-flight | Superset | ✅ 200 | CT206, port 8088 `/health` — needs restart if SQLAlchemy PendingRollback |
| Pre-flight | Metabase | ✅ 200 | CT202, port 3000 |
| Step 1 | Neo4j seed | ✅ PASS | Button supply chain seeded (BTN-001 → AMS Buttons BV → Shenzhen/Plastic/Metal) |
| Step 2 | Neo4j traversal | ✅ PASS | 4 paths returned at correct depths |
| Step 3 | Browserless scrape | ✅ PASS | example.com scraped, 559 chars, `Example Domain` found — via CT400 `/scrape` endpoint |
| Step 4 | Unstructured extract | ✅ PASS | 6 elements extracted from supplier HTML — **requires multipart/form-data**, not plain text/html |
| Step 5 | LiteLLM inference | ✅ PASS | Groq llama-3.3-70b returned 3 raw materials JSON after fixing corrupt api_key in config |
| Step 6 | Neo4j inferred link | ✅ PASS | Textile Dye (India) stored with `inferred: true`, confidence 0.7 |
| Step 7 | Qdrant embedding | ✅ PASS | `ollama/nomic-embed-text` returns 768-dim vector — NOT `text-embedding-3-small` (not configured) |
| Step 8 | Superset login | ✅ PASS | JWT token issued; admin password: KeePass `superset_ui_password` |

**Fixes applied 2026-06-30:**
- Groq API key on line 230 of `/etc/litellm/config.yaml` had 10 box-drawing chars (`\xe2\x94\x80`) appended → removed, LiteLLM restarted
- Superset had `PendingRollbackError` after connection loss → `systemctl restart superset` resolved
- Browserless endpoint: CLAUDE.md Step 3 used `/chromium/content` (not valid) — correct endpoint is `/scrape`
- Unstructured Step 4: `text/html` Content-Type body returns 422 — must use `multipart/form-data` with `files` field
- Embedding model for Step 7: `text-embedding-3-small` not in LiteLLM config — use `ollama/nomic-embed-text`

**Port correction**: Browserless uses port 3500 on both CT306 and CT400 (Ansible default `browserless_port: 3500`). Custom Playwright-based server (not upstream browserless-chrome). Endpoints: `GET /health`, `POST /scrape`, `POST /pdf`, `POST /screenshot`.

---

## Demo scenario

**Company:** Scania AB — Swedish manufacturer of heavy trucks, buses, and engines.

**Expected output:** Neo4j supply chain graph covering:

```
Scania R-series Truck
  └─► Scania AB (manufacturer, Sweden)
        ├─► ZF Friedrichshafen (gearboxes, Germany) — Tier 1
        │     └─► Saarstahl AG (steel billets, Germany) — Tier 2
        ├─► Bosch (fuel injection, electronics, Germany) — Tier 1
        │     ├─► Infineon Technologies (semiconductors, Germany) — Tier 2
        │     └─► Sensata Technologies (sensors, Netherlands) — Tier 2
        ├─► SSAB (high-strength steel, Sweden) — Tier 1
        │     └─► LKAB (iron ore, Sweden) — Tier 2
        ├─► Michelin (tyres, France) — Tier 1
        ├─► Dana Incorporated (axles, driveshafts, USA) — Tier 1
        └─► Cummins (engines for some variants, USA) — Tier 1
```

- Browserless scrapes: scania.com/suppliers, ZF annual report, Bosch supplier pages
- LLM infers Tier 3 links (Saarstahl iron ore → LKAB, Infineon raw silicon → Asia)
- Superset dashboard: supplier map by country, tier distribution pie chart, risk heatmap
- Risk flags: `SINGLE_SOURCE` (only 1 supplier for gearboxes), `GEOPOLITICAL_RISK` (China dependencies)

**Test input for dry-run:**
```
product: "Scania R-series heavy truck"
company: "Scania AB"
depth: 3  # tiers to traverse
```

---

## Goal

Given a product SKU or company name, the pipeline traverses its full supply chain
backwards: who supplies this, who supplies the supplier, where do raw materials come
from. Browserless scrapes JS-rendered supplier websites. Unstructured and Tika extract
content from PDFs and procurement documents. LLM infers missing links. Everything
gets stored in Neo4j as a directed graph (`SUPPLIED_BY`, `SOURCED_FROM` relationships).
LangGraph orchestrates the multi-step enrichment agent. Superset and Metabase render
SQL dashboards over the data. n8n schedules periodic refreshes. Qdrant enables
semantic search over supplier documents.

## Pipeline architecture

```
Product identifier (SKU, company name, URL)
  │
  ▼
LangGraph (CT119)            ← orchestrates multi-step graph enrichment
  │
  ├─► Neo4j (CT114)          ← query existing supply chain graph
  │     (Cypher: MATCH (p)-[:SUPPLIED_BY*1..5]→(n) RETURN path)
  │
  ├─► Browserless (CT400)    ← scrape JS-rendered supplier websites
  │   OR Browserless (CT306) ← acceptance stack fallback
  │
  ├─► Unstructured (CT117)   ← extract text from supplier HTML/PDFs
  ├─► Tika (CT115)           ← parse procurement docs (XLS, DOC, etc.)
  │
  ├─► Qdrant (CT102)         ← semantic search over supplier documents
  │     (store embeddings, query "who supplies X?")
  │
  ├─► LiteLLM (CT205)        ← LLM infers missing supply chain links
  │     → OpenRouter: analyze supplier relationships from text
  │
  ├─► Kotaemon (CT120)        ← RAG: chat with supplier PDFs/annual reports
  │     (hybrid search over ingested documents, returns cited excerpts)
  │
  └─► Neo4j (CT114)          ← write enriched graph (MERGE nodes + rels)
          │
          ▼
      Superset (CT206)        ← SQL dashboard (neo4j-jdbc connector)
      Metabase (CT202)        ← alternative: drag-and-drop dashboard
      n8n (CT104)             ← schedule: weekly re-scrape + graph update
      PostgreSQL (CT100)      ← structured entity table (knopenkonings DB)
      Langfuse (CT112)        ← trace LLM calls
```

## Services & credentials

| Service | Container | IP:Port | Role in UC4 | Auth method | Credential location |
|---------|-----------|---------|-------------|-------------|---------------------|
| Neo4j | CT114 | 10.0.1.114:7474 (HTTP) :7687 (Bolt) | Supply chain graph storage + traversal | Password | vault: `neo4j_password` |
| LangGraph | CT119 | 10.0.1.119:8000 | Agent workflow orchestration | None | No auth |
| Browserless (prod) | CT400 | 10.0.5.100:3500 | JS page scraping | None | No auth (internal) |
| Browserless (acc) | CT306 | 10.0.3.106:3500 | Fallback scraper | None | No auth (internal) |
| Unstructured | CT117 | 10.0.1.117:8000 | HTML/PDF text extraction | None | No auth |
| Tika | CT115 | 10.0.1.115:9998 | Binary doc parsing (XLS, DOC) | None | No auth |
| Qdrant | CT102 | 10.0.1.102:6333 | Supplier doc vector search | API key | vault: `qdrant_api_key` |
| LiteLLM | CT205 | 10.0.2.205:4000 | LLM: infer supply chain links | Bearer token | `ssh root@10.0.2.205 "grep master_key /etc/litellm/config.yaml"` |
| PostgreSQL | CT100 | 10.0.1.100:5432 | Structured entity table | Password | vault: `postgres_password`; DB: `knopenkonings` |
| Superset | CT206 | 10.0.2.206:8088 | SQL dashboards | Email+Password | KeePass → Services → Superset; admin: `admin@research-ready.nl` |
| Metabase | CT202 | 10.0.2.202:3000 | Alternative dashboards | Email+Password | KeePass → Services → Metabase |
| n8n | CT104 | 10.0.1.104:5678 | Scheduled refresh pipeline | API key | `ssh root@10.0.1.104 "cat /root/.credentials/n8n.txt"` |
| Langfuse | CT112 | 10.0.1.112:3000 | LLM tracing | Public+Secret key | vault: `langfuse_public_key` + `langfuse_api_key` |
| MongoDB | CT121 | 10.0.1.121:27017 | Document store (raw scraped data) | Password | vault: `mongodb_root_password` |
| Kotaemon | CT120 | 10.0.1.120:8501 | RAG over supplier docs (PDFs, annual reports) | Password | vault: `kotaemon_password`; admin: `admin@research-ready.nl` |

## Credentials lookup

```bash
# Neo4j password (MOST IMPORTANT — used in every Cypher query):
NEO4J_PW=$(grep neo4j_password ansible/inventory/group_vars/vault.yml | awk '{print $2}' | tr -d '"')
echo "Neo4j password: $NEO4J_PW"
# User: neo4j
# HTTP API: http://10.0.1.114:7474
# Bolt: bolt://10.0.1.114:7687
# Basic auth: base64(neo4j:PASSWORD)

# PostgreSQL for knopenkonings DB:
PG_PW=$(grep "^postgres_password" ansible/inventory/group_vars/vault.yml | awk '{print $2}' | tr -d '"')
echo "postgres: host=10.0.1.100 user=postgres password=$PG_PW"
# knopenkonings DB created by Ansible role — check: ssh root@10.0.1.100 "psql -U postgres -l | grep knop"

# Qdrant API key:
QDRANT_KEY=$(grep qdrant_api_key ansible/inventory/group_vars/vault.yml | awk '{print $2}' | tr -d '"')

# LiteLLM key:
LITELLM_KEY=$(ssh root@10.0.2.205 "grep master_key /etc/litellm/config.yaml | awk '{print \$2}'")

# Superset login (use API):
SUPERSET_PW=$(grep superset_secret_key ansible/inventory/group_vars/vault.yml | awk '{print $2}' | tr -d '"')
# Note: superset_secret_key is the app SECRET_KEY, not the admin password
# Admin password is in KeePass → Services → Superset
```

## Neo4j supply chain schema

```cypher
// Node types
(p:Product {name, sku, category})
(s:Supplier {name, country, website, tier})  -- tier 1/2/3
(r:RawMaterial {name, origin, material_type})
(c:Company {name, country, industry})
(cert:Certificate {name, issuer, valid_until})  -- ISO 9001, REACH, etc.

// Relationships
(p)-[:SUPPLIED_BY {since, contract_value}]->(s)
(s)-[:SOURCED_FROM {volume_kg_year}]->(r)
(s)-[:CERTIFIED_BY]->(cert)
(s)-[:OWNED_BY]->(c)  -- parent company
(c)-[:SUBSIDIARY_OF]->(c)  -- corporate structure
```

## Pre-flight checklist

```bash
# 1. VPN active
bash scripts/vpn-connect.sh status

# 2. Quorum
ssh ProxmoxTest "pvecm status | grep Quorate"

# 3. Neo4j must be running (critical)
ssh root@10.0.1.114 "systemctl is-active neo4j"
# Expected: active

# 4. Cross-VM routing works (Browserless CT400 on prod-vm01)
ssh root@10.0.1.100 "curl -s -o /dev/null -w '%{http_code}' --connect-timeout 3 http://10.0.5.100:3500/"
# Expected: 200 (requires ip_forward + inter-VM routes)
# If 000: ssh ProxmoxTest "sysctl net.ipv4.ip_forward" — must be 1

# 5. Service sweep
for svc in \
  "10.0.1.114:7474/ neo4j" \
  "10.0.1.102:6333/healthz qdrant" \
  "10.0.1.120:8501/ kotaemon" \
  "10.0.5.100:3500/ browserless-prod" \
  "10.0.3.106:3500/ browserless-acc" \
  "10.0.1.117:8000/health unstructured" \
  "10.0.1.115:9998/tika tika" \
  "10.0.1.119:8000/health langgraph" \
  "10.0.2.206:8088/ superset" \
  "10.0.2.202:3000/ metabase"; do
  addr="${svc%% *}"; name="${svc##* }"
  code=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 3 "http://$addr" 2>/dev/null)
  printf "%-20s %s\n" "$name" "${code:-DEAD}"
done
```

## Dry-run test procedure

### Step 1 — Neo4j: seed supply chain graph

```bash
NEO4J_PW=$(grep neo4j_password ansible/inventory/group_vars/vault.yml | awk '{print $2}' | tr -d '"')
NEO4J_AUTH=$(python3 -c "import base64; print(base64.b64encode(f'neo4j:$NEO4J_PW'.encode()).decode())")

ssh root@10.0.1.114 "python3 -c \"
import urllib.request, json, base64

auth = base64.b64encode(b'neo4j:$NEO4J_PW').decode()
base = 'http://localhost:7474/db/neo4j/tx/commit'
headers = {'Content-Type': 'application/json', 'Authorization': 'Basic ' + auth}

# Seed: Button → AMS Buttons BV → Plastic Pellets (Germany) + Metal Pins (China)
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
for q in queries:
    req = urllib.request.Request(base,
        data=json.dumps({'statements': [{'statement': q}]}).encode(),
        headers=headers, method='POST')
    r = urllib.request.urlopen(req)
    d = json.loads(r.read())
    if d.get('errors'):
        print('ERROR:', q, d['errors'])
print('Seed complete')
\""
```

Expected: `Seed complete` (no errors).

### Step 2 — Neo4j: backward traversal query

```bash
NEO4J_PW=$(grep neo4j_password ansible/inventory/group_vars/vault.yml | awk '{print $2}' | tr -d '"')

ssh root@10.0.1.114 "python3 << 'PYEOF'
import urllib.request, json, base64

pw = open('/dev/stdin').read().strip()
auth = base64.b64encode(f'neo4j:{pw}'.encode()).decode()

query = '''
MATCH path = (p:Product {sku: \"BTN-001\"})-[:SUPPLIED_BY|SOURCED_FROM*1..5]->(n)
RETURN [node in nodes(path) | coalesce(node.name, node.sku)] AS chain,
       length(path) AS depth
ORDER BY depth
'''

req = urllib.request.Request(
    'http://localhost:7474/db/neo4j/tx/commit',
    data=json.dumps({'statements': [{'statement': query}]}).encode(),
    headers={'Content-Type': 'application/json', 'Authorization': 'Basic ' + auth},
    method='POST'
)
r = urllib.request.urlopen(req)
d = json.loads(r.read())
rows = d['results'][0]['data']
print(f'Supply chain paths found: {len(rows)}')
for row in rows:
    print(' → '.join(row['row'][0]))
PYEOF
" <<< "$NEO4J_PW"
```

Expected:
```
Supply chain paths found: 4
Button 12mm → AMS Buttons BV
Button 12mm → AMS Buttons BV → Shenzhen Metal Co
Button 12mm → AMS Buttons BV → Plastic Pellets
Button 12mm → AMS Buttons BV → Shenzhen Metal Co → Metal Pins
```

### Step 3 — Browserless scrapes a supplier site (JS-rendered)

**NOTE**: CT400 does NOT allow direct SSH (publickey denied). Use `pct exec` on node-4.
**NOTE**: Endpoint is `/scrape` (not `/chromium/content` — that was wrong in older docs).
**NOTE**: Port is 3500 on both CT400 and CT306.

```bash
# CT400 is on node-4 (10.0.0.18) — use pct exec
ssh -i ~/.ssh/proxmox_node3 root@10.0.0.18 "pct exec 400 -- python3 -c \"
import urllib.request, json

req = urllib.request.Request(
    'http://localhost:3500/scrape',
    data=json.dumps({
        'url': 'https://example.com',
        'wait_for': 1000
    }).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST'
)
r = urllib.request.urlopen(req, timeout=35)
d = json.loads(r.read())
html = d.get('html', '')
print('Scraped:', len(html), 'chars, status:', d.get('status_code'))
assert 'Example Domain' in html, 'Unexpected content'
print('Browserless JS scraping: OK')
\""
```

Expected: `Scraped: ~559 chars, status: 200` then `Browserless JS scraping: OK`.

### Step 4 — Unstructured extracts supplier document data

**NOTE**: Unstructured requires `multipart/form-data` with a `files` field. Plain `text/html` body returns HTTP 422.

```bash
ssh -o ProxyJump=root@10.0.0.16 root@10.0.1.117 "python3 << 'PYEOF'
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
print(f'Extracted {len(texts)} elements:')
for t in texts:
    print(f'  {t}')
PYEOF"
```

Expected: 6 text elements including supplier name, certifications, materials, capacity.

### Step 5 — LLM infers missing supply chain links

```bash
LITELLM_KEY=$(ssh root@10.0.2.205 "grep master_key /etc/litellm/config.yaml | awk '{print \$2}'")
curl -s http://10.0.2.205:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "researcher-llm",
    "messages": [{
      "role": "user",
      "content": "Supplier: AMS Buttons BV (Netherlands). Makes plastic buttons using ABS plastic from BASF Germany and metal pins from Shenzhen. What 3 other raw materials are likely in their supply chain? For each: name, probable origin country, material type (polymer/metal/chemical). JSON array only."
    }],
    "max_tokens": 300
  }' | python3 -c "
import json, sys
d = json.load(sys.stdin)
response = d['choices'][0]['message']['content']
print('LLM inference:')
print(response)
"
```

Expected: JSON array with 3 raw materials, countries, types.

### Step 6 — Store inferred links back to Neo4j

```bash
# Take the LLM output from Step 5 and MERGE the inferred nodes
NEO4J_PW=$(grep neo4j_password ansible/inventory/group_vars/vault.yml | awk '{print $2}' | tr -d '"')

ssh root@10.0.1.114 "python3 -c \"
import urllib.request, json, base64

auth = base64.b64encode(b'neo4j:$NEO4J_PW').decode()
base = 'http://localhost:7474/db/neo4j/tx/commit'
headers = {'Content-Type': 'application/json', 'Authorization': 'Basic ' + auth}

# Add LLM-inferred material: dye/colorant from India
q = '''
MERGE (r:RawMaterial {name: \\\"Textile Dye\\\", origin: \\\"India\\\", material_type: \\\"Chemical\\\", inferred: true})
MATCH (s:Supplier {name: \\\"AMS Buttons BV\\\"})
MERGE (s)-[:SOURCED_FROM {confidence: 0.7, source: \\\"LLM inference\\\"}]->(r)
'''
req = urllib.request.Request(base,
    data=json.dumps({'statements': [{'statement': q}]}).encode(),
    headers=headers, method='POST')
r = urllib.request.urlopen(req)
d = json.loads(r.read())
print('Inferred link stored:', 'OK' if not d.get('errors') else d['errors'])
\""
```

Expected: `Inferred link stored: OK`.

### Step 7 — Qdrant semantic search over supplier docs

**NOTE**: Use `ollama/nomic-embed-text` (768 dims) — `text-embedding-3-small` is NOT configured in LiteLLM.
Run from inside the cluster (e.g. CT100) since LiteLLM is on 10.0.2.205 (node-2 internal network).

```bash
ssh -o ProxyJump=root@10.0.0.16 root@10.0.1.100 "python3 << 'PYEOF'
import urllib.request, json, urllib.error

QDRANT_KEY = 'KEY_FROM_VAULT'  # grep qdrant_api_key ansible/inventory/group_vars/vault.yml
LITELLM_KEY = 'sk-0xi1O45reIhzSzwWt90tvdX6'

# Generate embedding via LiteLLM → Ollama nomic-embed-text
emb_req = urllib.request.Request(
    'http://10.0.2.205:4000/v1/embeddings',
    data=json.dumps({'model': 'ollama/nomic-embed-text', 'input': 'who supplies raw materials to button manufacturers?'}).encode(),
    headers={'Authorization': 'Bearer ' + LITELLM_KEY, 'Content-Type': 'application/json'},
    method='POST'
)
r = urllib.request.urlopen(emb_req, timeout=15)
d = json.loads(r.read())
embedding = d['data'][0]['embedding']
print(f'Embedding (nomic-embed-text): {embedding[:3]} ... (dims: {len(embedding)})')
print('Embedding: OK')
PYEOF"
```

Expected: `Embedding (nomic-embed-text): [...] ... (dims: 768)` then `Embedding: OK`.

### Step 8 — Superset dashboard

Manual test:
1. Open `http://10.0.2.206:8088`
2. Log in as `admin@research-ready.nl` (password from KeePass → Services → Superset)
3. Add database connection → Neo4j JDBC or SQLite
4. Create chart: supplier count by country
5. Create dashboard: "Supply Chain Overview"

```bash
# API login for automation:
SUPERSET_TOKEN=$(curl -s -X POST http://10.0.2.206:8088/api/v1/security/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"SUPERSET_PASS_FROM_KEEPASS","provider":"db"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
echo "Superset token: ${SUPERSET_TOKEN:0:20}..."
```

## Full success criteria

- [x] Neo4j traversal returns full supply chain path (4 paths confirmed 2026-06-30)
- [x] Browserless scrapes example.com (559 chars HTML via `/scrape` endpoint, CT400)
- [x] Unstructured extracts 6 elements from supplier HTML (multipart/form-data required)
- [x] LiteLLM infers missing supply chain links (valid JSON, Groq llama-3.3-70b)
- [x] Inferred links stored in Neo4j with `inferred: true` + confidence
- [x] Qdrant accepts embeddings (768-dim from nomic-embed-text via LiteLLM)
- [x] Superset loads at port 8088 (JWT login confirmed 2026-06-30)

## Common failures & fixes

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Neo4j auth 401 | Wrong password in command | Read from CT114: `ssh root@10.0.1.114 "cat /root/.credentials/neo4j.txt"` |
| Browserless 404 on POST | Wrong endpoint | Use `/scrape` not `/chromium/content` — this is a custom Playwright server |
| Browserless SSH denied | CT400 has no SSH keys | Use `pct exec 400 --` on node-4 (root@10.0.0.18 via proxmox_node3 key) |
| Qdrant 403 | API key missing from header | Add `-H "api-key: $QDRANT_KEY"` to all Qdrant requests |
| Unstructured 422 | Wrong Content-Type | Use `multipart/form-data` with `files` field — plain `text/html` body gives 422 |
| Superset 401 on login | Password correct but rejected | `systemctl restart superset` — SQLAlchemy PendingRollbackError after idle |
| Superset 500 on login | PendingRollback on DB connection | Restart clears it: `systemctl restart superset` |
| LiteLLM 400 "No connected db" | Request from non-localhost with master_key | Auth issue when calling from remote — call from localhost on CT205 |
| LiteLLM 429 researcher-llm | Groq key corrupted in config | Check line with `gsk_` for box-drawing chars (`\xe2\x94\x80`) — remove and restart |
| Embedding model not found | `text-embedding-3-small` not in LiteLLM | Use `ollama/nomic-embed-text` (768 dims) — that's what's configured |
| Superset admin wrong password | KeePass `superset_ui_password` | Password: KeePass `superset_ui_password` (NOT `superset_secret_key`) |
| Neo4j OOM | Graph traversal too deep | Limit depth: `[:SUPPLIED_BY|SOURCED_FROM*1..3]` not `*1..5` |
| knopenkonings DB missing | Role not run | `ansible-playbook -i inventory/hosts.yml playbooks/05_platform.yml --tags postgres` |

## n8n scheduled refresh

Weekly supply chain update workflow:
1. Trigger: Cron every Monday 06:00
2. HTTP Request → Browserless: scrape known supplier sites
3. HTTP Request → Unstructured: extract text from scraped HTML
4. HTTP Request → LiteLLM: infer new links from extracted text
5. HTTP Request → Neo4j HTTP API: MERGE new nodes/relationships
6. Notification: Slack/email with count of new nodes added

n8n admin: `chris@research-ready.nl` / KeePass → Services → n8n

## Current status (2026-07-11)

All 8 dry-run steps: **PASS** (confirmed 2026-06-30, infrastructure stable).
Knowledge graph: `graphify-out/graph.json` — 34 nodes, 68 edges, 7 communities.
HTML visualization: `graphify-out/graph.html` — open in browser.

### Next phase: Scania demo

1. **Seed Scania graph** — load `example_outputs/sample_graph.cypher` into Neo4j CT114
2. **LangGraph agent** — Python code on CT119 for `POST /runs` endpoint (scrape → extract → infer → MERGE loop)
3. **Superset dashboards** — supplier count by country, tier pie chart, risk heatmap
4. **n8n workflow** — Monday 06:00 cron, HTTP nodes for each pipeline step
5. **PostgreSQL entity table** — mirror supplier nodes into `knopenkonings.suppliers`

```bash
# Seed Scania graph now:
NEO4J_PW=$(python3 -c "from pykeepass import PyKeePass; kp=PyKeePass('passwords.kdbx',password='SupplyChainBaby100!'); e=kp.find_entries(title='Neo4j',first=True); print(e.password)")
ssh -J root@10.0.0.16 root@10.0.1.114 "cypher-shell -u neo4j -p $NEO4J_PW" < example_outputs/sample_graph.cypher
```

## Recommended Claude skills for this use case

```bash
# Install all skills for UC4 next phase:
/manage-skills install langgraph          # LangGraph agent code (CT119)
/manage-skills install python-pro         # pipeline Python scripts
/manage-skills install grafana-dashboards # Superset/Grafana dashboard JSON
/manage-skills install supply-chain-risk-auditor  # risk flag logic
/manage-skills install n8n-workflow-patterns      # n8n Monday cron workflow
/manage-skills install neo4j              # Cypher query patterns (if available)
/manage-skills install postgresql         # knopenkonings DB schema
```

- **langgraph** — LangGraph agent on CT119: `POST /runs` → scrape/extract/infer/MERGE loop
- **python-pro** — pipeline Python scripts (`src/agent.py`, `src/neo4j_client.py`, etc.)
- **grafana-dashboards** — Superset chart JSON (supplier map, tier pie, risk heatmap)
- **supply-chain-risk-auditor** — risk flag logic: `SINGLE_SOURCE`, `GEOPOLITICAL_RISK`
- **n8n-workflow-patterns** — Monday 06:00 cron, 5-step HTTP workflow
- **postgresql** — `knopenkonings.suppliers` table schema + sync query
- **claude-d3js-skill** — render interactive supply chain graph (D3.js force layout)
- **xlsx** — parse/generate Excel supplier lists
- **pdf** — extract data from supplier capability statements
- **docx** — generate supply chain audit reports
