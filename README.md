# SupplyLens — AI Supply Chain Intelligence & Regulatory Enforcement

Given a company name, product SKU, or barcode, SupplyLens automatically maps the
complete supply chain using OSINT, infers hidden Tier 3–5 nodes with AI confidence
scoring, flags violations, and produces EDRM-compliant evidence for EU regulatory
enforcement.

**Industry partner:** Scania AB (ground truth validation)
**Research goal:** Multi-signal OSINT inference + EDRM evidence chain + EU regulatory output
**Status:** All 8 dry-run steps PASS. Phases 1–10 built. NeoDash deployed (CT130).

> Full research concept, methodology, and academic context: see [VISION.md](VISION.md)

---

## Three Research Use Cases

| Use Case | Description | Output |
|----------|-------------|--------|
| **Supply Chain Mapping** | Auto-discover Tier 1–5 suppliers from OSINT | Probabilistic graph with confidence scores |
| **Material Alternative Research** | Find cheaper/greener alternatives to flagged materials | Cost + CO2 improvement proposal |
| **Suppressed Evidence & Regulatory Filing** | Prove a company knew about a better alternative and chose not to use it | EDRM-compliant EU enforcement report |

---

## System Architecture — Three Organs

SupplyLens is structured as three semi-independent organs. Each runs on its own
schedule and communicates through well-defined interfaces. The mouth ingests
continuously. The gut processes whenever raw data arrives. The presentation layer
reads Neo4j on demand — independently of when either of the others last ran.

**Color key:** green = confirmed working · orange = service up, integration incomplete · red = not yet built/deployed

```mermaid
flowchart TD
    classDef green  fill:#1a5c1a,stroke:#0d3a0d,color:#fff
    classDef orange fill:#7a4500,stroke:#5a3000,color:#fff
    classDef red    fill:#7a1a1a,stroke:#5c0000,color:#fff
    classDef store  fill:#1a3a5c,stroke:#0d2640,color:#fff

    EXT(["External world\nwebsites · APIs · PDFs · uploads"])

    subgraph MOUTH ["MOUTH — Ingestion"]
        M1["Browserless CT400  prod scraper"]:::green
        M2["Browserless CT306  acc fallback"]:::green
        M3["n8n CT104  OSINT scheduler"]:::orange
        M4["Kotaemon CT120  manual PDF upload"]:::orange
    end

    MONGO[("MongoDB CT121\nraw store\nHTML · JSON · PDFs")]:::red

    subgraph GUT ["GUT — Processing & Inference"]
        G1["Unstructured CT117  text extraction"]:::green
        G2["Tika CT115  binary docs"]:::green
        G3["LangGraph CT119  orchestration"]:::green
        G4["LiteLLM CT205  Groq inference"]:::green
        G5["Qdrant CT102  vector search"]:::green
        G6["Langfuse CT112  LLM audit trail"]:::orange
        G7["Confidence scorer  multi-signal fusion"]:::red
        G8["EDRM evidence stamp"]:::red
    end

    NEO4J[("Neo4j CT114\nKnowledge Graph\nconfidence · evidence")]:::green

    subgraph PRESENTATION ["PRESENTATION — Output"]
        P1["NeoDash CT130  analytics dashboard"]:::green
        P2["Superset CT206  SQL dashboards"]:::green
        P3["Metabase CT202  alternative dashboards"]:::green
        P4["Kepler.gl  geographic arc map"]:::red
        P5["Neo4j Bloom  graph exploration"]:::red
        P6["EDRM Report → EU authority"]:::red
    end

    EXT --> MOUTH
    MOUTH --> MONGO
    MONGO --> GUT
    GUT --> NEO4J
    NEO4J --> PRESENTATION
```

---

### Organ 1 — The Mouth (Ingestion)

Runs on its own schedule. Does not parse, infer, or score — only collects and stores raw.

| | Item | Format |
|--|------|--------|
| **In** | Company name / SKU / barcode | Plain text |
| **In** | Cron schedule | Time trigger (n8n) |
| **In** | Researcher-provided URLs | Plain text |
| **Out** | Scraped HTML pages | UTF-8 string + `{source_url, timestamp, sha256}` |
| **Out** | Downloaded PDFs / XLS / DOC | Binary + `{filename, sha256, mime_type}` |
| **Out** | Trade flow records | JSON — `{hs_code, reporter, partner, value, year}` |
| **Out** | Bill-of-lading records | JSON — `{shipper, consignee, goods_description, port}` |
| **Out** | Facility records | JSON — `{name, lat, lon, country, certifications[]}` |
| **Out** | News/violation events | JSON — `{actor, location, event_type, date, url}` |
| **Out** | Company ownership records | JSON — `{lei, name, parent_lei, subsidiaries[]}` |
| **Store** | All outputs | MongoDB CT121 — collection `raw_scrapes` |

```mermaid
flowchart TD
    classDef green  fill:#1a5c1a,stroke:#0d3a0d,color:#fff
    classDef orange fill:#7a4500,stroke:#5a3000,color:#fff
    classDef red    fill:#7a1a1a,stroke:#5c0000,color:#fff

    T1["n8n cron  CT104\nMonday 06:00"]:::orange
    T2["Researcher request\ncompany name / barcode / URL"]:::green
    T3["Scheduled API poll\ndaily GDELT · weekly Comtrade"]:::red

    T1 & T2 --> RESOLVE["Resolve company identity\nGS1 → brand owner\nOpenCorporates → LEI\nGLEIF → parent graph"]:::red

    RESOLVE --> URLS["Build URL list\nsupplier pages · annual reports\nsustainability filings"]:::green

    URLS --> SCRAPE["Scrape JS-rendered pages\nBrowserless CT400  POST /scrape\nwait_for: 1000ms"]:::green

    SCRAPE --> FALLBACK{CT400 up?}
    FALLBACK -->|Yes| HTML["Raw HTML\n+ timestamp + URL"]:::green
    FALLBACK -->|No| FB["Fallback: Browserless CT306\n10.0.3.106:3500"]:::green
    FB --> HTML

    T3 --> APIS["Pull structured data\nUN Comtrade · ImportYeti\nOpenSupplyHub · GDELT · ILO"]:::red

    T2 --> MANUAL["Researcher uploads\nPDF · XLS · DOCX\nvia Kotaemon CT120"]:::orange

    HTML & APIS & MANUAL --> MONGO[("MongoDB CT121\n10.0.1.121:27017\nraw_scrapes")]:::red
```

---

### Organ 2 — The Gut (Processing & Inference)

Triggered by new documents in MongoDB. Loops until depth limit or no new nodes found.

| | Item | Format |
|--|------|--------|
| **In** | Raw HTML | UTF-8 string — multipart POST to Unstructured CT117 |
| **In** | Binary documents (PDF/XLS/DOC) | Binary — PUT to Tika CT115 |
| **In** | Structured JSON (trade/facility/news) | JSON — parsed directly by LangGraph |
| **Out** | Text elements | JSON array — `[{text, type, metadata}]` from Unstructured |
| **Out** | 768-dim embeddings | `float[]` — nomic-embed-text via LiteLLM, upserted to Qdrant |
| **Out** | Inferred relationships | JSON array — `[{name, country, tier, supplies, confidence}]` |
| **Out** | Supplier / RawMaterial nodes | Neo4j MERGE — `{name, country, tier, confidence, inferred, signals[]}` |
| **Out** | SUPPLIED\_BY / SOURCED\_FROM edges | Neo4j MERGE — `{confidence, inferred: true, source}` |
| **Out** | EvidenceClaim nodes | Neo4j MERGE — `{source_url, sha256, timestamp, method_version}` |
| **Store** | Nodes + edges + evidence | Neo4j CT114 + Qdrant CT102 (embeddings) |

```mermaid
flowchart TD
    classDef green  fill:#1a5c1a,stroke:#0d3a0d,color:#fff
    classDef orange fill:#7a4500,stroke:#5a3000,color:#fff
    classDef red    fill:#7a1a1a,stroke:#5c0000,color:#fff

    IN[("MongoDB CT121\nnew raw documents")]:::red

    ORCH["LangGraph CT119\norchestrates the loop"]:::green

    EXTRACT["Step 1 — Extract text\nHTML/PDF → Unstructured CT117\nbinary → Tika CT115"]:::green

    EMBED["Step 2 — Embed + index\nLiteLLM CT205 → nomic-embed-text\n768-dim → Qdrant CT102"]:::green

    INFER["Step 3 — Infer relationships\nLiteLLM CT205 → Groq llama-3.3-70b\nreturns JSON array of supplier links"]:::green

    SCORE["Step 4 — Score confidence\nTrade ×0.30  Facility ×0.25\nCorporate ×0.20  Docs ×0.15  News ×0.10\nweighted sum + uncertainty band"]:::red

    STAMP["Step 5 — EDRM evidence stamp\nURL · SHA256 · timestamp\ninference method version\nlog to Langfuse CT112"]:::red

    WRITE["Step 6 — MERGE into Neo4j CT114\nSupplier / RawMaterial nodes\nSUPPLIED_BY / SOURCED_FROM edges\nconfidence · inferred: true"]:::green

    FLAGS["Step 7 — Apply risk flags\nSINGLE_SOURCE · GEOPOLITICAL_RISK\nCBAM · LkSG · EUDR"]:::green

    LOOP{New nodes found\nand depth < limit?}
    OUT[("Neo4j CT114\nnodes + edges\nconfidence + evidence")]:::green

    IN --> ORCH --> EXTRACT --> EMBED --> INFER --> SCORE --> STAMP --> WRITE --> FLAGS --> LOOP
    LOOP -->|"Yes — go deeper"| EXTRACT
    LOOP -->|Done| OUT
```

---

### Organ 3 — The Presentation Layer

Reads Neo4j on demand. Three independent interfaces, one per research use case.

| | Item | Format |
|--|------|--------|
| **In** | Supply chain graph | Cypher query results from Neo4j CT114 |
| **In** | Semantic search results | Qdrant similarity query — top-k chunks |
| **Out** | Geographic arc map | Browser UI — Kepler.gl: nodes + arcs + evidence panel |
| **Out** | Graph topology view | Browser UI — NeoDash CT130 / Neo4j Bloom |
| **Out** | SQL analytics dashboard | Browser UI — Superset CT206 / Metabase CT202 |
| **Out** | EDRM regulatory report | PDF — every claim hashed and traceable |
| **Out** | BPMN process export | XML — bpmn.io format for regulatory submission |

```mermaid
flowchart TD
    classDef green  fill:#1a5c1a,stroke:#0d3a0d,color:#fff
    classDef orange fill:#7a4500,stroke:#5a3000,color:#fff
    classDef red    fill:#7a1a1a,stroke:#5c0000,color:#fff

    KG[("Neo4j CT114\nknowledge graph")]:::green

    KG --> MAP_EXP["Export nodes with lat/lon\n+ risk flags + confidence"]:::red
    MAP_EXP --> KEPLER["Kepler.gl  geographic map\nnode = facility · arc = flow\ncolor = risk · opacity = confidence\nclick → evidence panel"]:::red

    KG --> GRAPH_EXP["Graph topology queries\nCypher: shortest path\nshared suppliers · bottlenecks"]:::green
    GRAPH_EXP --> NEODASH["NeoDash CT130\nlocalhost:15005\nsupplier count · tier pie · heatmap"]:::green
    GRAPH_EXP --> BLOOM["Neo4j Bloom\ngraph exploration\ncommunity detection"]:::red

    KG --> REVIEW["Researcher reviews\ninferred nodes\nconfirm / reject / flag"]:::green
    REVIEW --> EDRM_PKG["Retrieve EDRM package\nURL · SHA256 · signal weights\nper flagged node"]:::red
    EDRM_PKG --> JUDGE{Violation +\nalternative\nevident?}
    JUDGE -->|Yes| REPORT["Draft EDRM report\nLiteLLM CT205\nEU CSDD · LkSG · UK Modern Slavery"]:::red
    JUDGE -->|Monitor| ARCHIVE["Archive case\nn8n weekly re-check"]:::orange
    REPORT --> SUBMIT(["Submit to\nEuropean Commission\nor national authority"]):::red
```

---

## Infrastructure Map

Services grouped by organ. All on internal Proxmox subnets — VPN required from workstation.

**Color key:** green = confirmed working · orange = service up, integration incomplete · red = not yet built/deployed

```mermaid
graph TB
    classDef green  fill:#1a5c1a,stroke:#0d3a0d,color:#fff
    classDef orange fill:#7a4500,stroke:#5a3000,color:#fff
    classDef red    fill:#7a1a1a,stroke:#5c0000,color:#fff
    classDef store  fill:#1a3a5c,stroke:#0d2640,color:#fff

    subgraph WS ["Researcher Workstation"]
        BROWSER[Browser]:::green
        TUNNELS["SSH Tunnels\n-L 15005 NeoDash\n-L 17474 Neo4j HTTP\n-L 17687 Neo4j Bolt"]:::green
        BROWSER --- TUNNELS
    end

    subgraph MOUTH_INFRA ["MOUTH — Ingestion services"]
        CT400["Browserless  CT400\n10.0.5.100:3500\nJS scraper  prod\nPOST /scrape"]:::green
        CT306["Browserless  CT306\n10.0.3.106:3500\nJS scraper  acc fallback"]:::green
        CT104["n8n  CT104\n10.0.1.104:5678\ncron scheduler\nOSINT API pulls"]:::orange
        CT120["Kotaemon  CT120\n10.0.1.120:8501\nmanual PDF upload + RAG"]:::orange
        CT121["MongoDB  CT121\n10.0.1.121:27017\nraw_scrapes store"]:::red
    end

    subgraph GUT_INFRA ["GUT — Processing services"]
        CT119["LangGraph  CT119\n10.0.1.119:8000\norchestrates the loop"]:::green
        CT117["Unstructured  CT117\n10.0.1.117:8000\nHTML/PDF text extraction"]:::green
        CT115["Tika  CT115\n10.0.1.115:9998\nbinary doc parser"]:::green
        CT205["LiteLLM  CT205\n10.0.2.205:4000\nGroq llama-3.3-70b"]:::green
        CT102["Qdrant  CT102\n10.0.1.102:6333\nvector store  768-dim"]:::green
        CT112["Langfuse  CT112\n10.0.1.112:3000\nLLM trace + audit"]:::orange
        SCORER["Confidence scorer\nmulti-signal fusion"]:::red
        EDRM_SVC["EDRM evidence stamp\nreport generator"]:::red
    end

    subgraph STORE ["Knowledge Store"]
        CT114["Neo4j  CT114\n10.0.1.114:7474 / :7687\nKnowledge Graph"]:::store
        CT100["PostgreSQL  CT100\n10.0.1.100:5432\nknopenkonings DB"]:::orange
    end

    subgraph PRES_INFRA ["PRESENTATION — Output services"]
        CT130["NeoDash  CT130\n10.0.1.130:5005\nanalytics dashboard"]:::green
        CT206["Superset  CT206\n10.0.2.206:8088\nSQL dashboards"]:::green
        CT202["Metabase  CT202\n10.0.2.202:3000\nalternative dashboards"]:::green
        KEPLER["Kepler.gl\ngeographic arc map"]:::red
        BLOOM["Neo4j Bloom\ngraph exploration"]:::red
    end

    subgraph EXT ["External services"]
        GROQ["Groq API\nllama-3.3-70b"]:::green
        COMTRADE["UN Comtrade API"]:::red
        IMPORTYETI["ImportYeti\nbill-of-lading"]:::red
        OSH["OpenSupplyHub API"]:::red
        GDELT["GDELT API"]:::red
        GLEIF["GLEIF / OpenCorporates"]:::red
    end

    TUNNELS --> CT130
    TUNNELS --> CT114

    CT400 --> CT121
    CT306 --> CT121
    CT104 --> CT400
    CT104 --> COMTRADE & IMPORTYETI & OSH & GDELT & GLEIF
    CT104 --> CT119

    CT121 --> CT119
    CT119 --> CT117 & CT115 & CT102 & CT205 & CT112
    CT119 --> SCORER --> EDRM_SVC
    CT119 --> CT114

    CT205 --> GROQ
    CT120 --> CT205 & CT114

    CT114 --> CT130 & CT206 & CT202 & CT100
    CT114 --> KEPLER & BLOOM
```

---

## Quick Start

```bash
# 1. VPN required
bash scripts/vpn-connect.sh connect

# 2. SSH tunnels (Neo4j + NeoDash)
ssh -f -L 15005:10.0.1.130:5005 -L 17474:localhost:7474 -L 17687:localhost:7687 \
    -N -o ProxyJump=root@10.0.0.16 root@10.0.1.114

# 3. Run all 8 dry-run steps
bash usecases/uc4-supply-chain/scripts/dry_run.sh

# 4. Health check
bash usecases/uc4-supply-chain/scripts/health_check.sh

# 5. Open NeoDash  (requires tunnel above)
#    → http://localhost:15005
#    → bolt://localhost:17687  |  neo4j  |  <password from KeePass>
```

---

## Services

| Service | Container | IP:Port | Role |
|---------|-----------|---------|------|
| Neo4j | CT114 | 10.0.1.114:7474 (HTTP) / :7687 (Bolt) | Supply chain knowledge graph |
| LangGraph | CT119 | 10.0.1.119:8000 | Agent orchestration |
| Browserless (prod) | CT400 | 10.0.5.100:3500 | JS scraping — `POST /scrape` |
| Browserless (acc) | CT306 | 10.0.3.106:3500 | Fallback scraper |
| Unstructured | CT117 | 10.0.1.117:8000 | HTML/PDF text extraction |
| Tika | CT115 | 10.0.1.115:9998 | Binary doc parsing (XLS, DOC) |
| Qdrant | CT102 | 10.0.1.102:6333 | Vector search (768-dim) |
| LiteLLM | CT205 | 10.0.2.205:4000 | LLM proxy + embeddings |
| Kotaemon | CT120 | 10.0.1.120:8501 | RAG over supplier docs |
| NeoDash | CT130 | 10.0.1.130:5005 | Analytics dashboard |
| Superset | CT206 | 10.0.2.206:8088 | SQL dashboards |
| Metabase | CT202 | 10.0.2.202:3000 | Alternative dashboards |
| n8n | CT104 | 10.0.1.104:5678 | Scheduled OSINT refresh |
| PostgreSQL | CT100 | 10.0.1.100:5432 | Structured entity table |
| Langfuse | CT112 | 10.0.1.112:3000 | LLM tracing + evidence chain |

---

## Credentials

Stored in `passwords.kdbx` (master: `SupplyChainBaby100!`).

```python
from pykeepass import PyKeePass
kp = PyKeePass('passwords.kdbx', password='SupplyChainBaby100!')
neo4j = kp.find_entries(title='Neo4j', first=True)
print(neo4j.password)
```

Or read directly: `ssh root@10.0.1.114 "cat /root/.credentials/neo4j.txt"`

---

## Neo4j Graph Schema

```cypher
// Node types
(p:Product   {name, sku, category})
(s:Supplier  {name, country, website, tier, risk_flags[]})
(r:RawMaterial {name, origin, material_type})
(c:Company   {name, country, industry})
(cert:Certificate {name, issuer, valid_until})
(ev:EvidenceClaim {source_url, sha256, timestamp, confidence, signals[]})

// Relationships
(p)-[:SUPPLIED_BY  {since, contract_value}]->(s)
(s)-[:SOURCED_FROM {volume_kg_year, confidence, inferred}]->(r|s)
(s)-[:CERTIFIED_BY]->(cert)
(s)-[:OWNED_BY]->(c)
(c)-[:SUBSIDIARY_OF]->(c)
(ev)-[:EVIDENCE_FOR]->(s|r)

// Traversal pattern
MATCH path = (p:Product {sku: $sku})-[:SUPPLIED_BY|SOURCED_FROM*1..3]->(n)
RETURN [node in nodes(path) | coalesce(node.name, node.sku)] AS chain,
       length(path) AS depth
ORDER BY depth
```

---

## Confidence Score Model

Every inferred node carries a weighted confidence score from 5 OSINT signals:

| Signal | Weight | Source |
|--------|--------|--------|
| Trade flow data | 0.30 | UN Comtrade, ImportYeti bill-of-lading |
| Facility location | 0.25 | OpenSupplyHub, satellite imagery |
| Corporate structure | 0.20 | OpenCorporates, GLEIF LEI |
| Document extraction | 0.15 | Annual reports, sustainability filings |
| News & incidents | 0.10 | GDELT, NGO databases, ILO |

---

## Critical Notes

- Browserless endpoint: `POST /scrape` port 3500 — NOT `/chromium/content`
- CT400 has no SSH — use `pct exec 400 --` on node-4 (`root@10.0.0.18` via `~/.ssh/proxmox_node3`)
- Unstructured requires `multipart/form-data` with `files` field — plain `text/html` body = HTTP 422
- Embedding model: `ollama/nomic-embed-text` (768 dims) — NOT `text-embedding-3-small`
- Superset login fails: `systemctl restart superset` fixes PendingRollbackError
- Groq key corruption: check `/etc/litellm/config.yaml` line ~230 for box-drawing chars (`\xe2\x94\x80`)
- Node-1 bastion: `-o ProxyJump=root@10.0.0.16` | Node-2 bastion: `-o ProxyJump=root@10.0.0.15`

See `CLAUDE.md` for full dry-run procedures and failure fix table.
See `VISION.md` for research methodology and academic context.
