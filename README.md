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

```mermaid
flowchart LR
    EXT["External world\nwebsites · APIs · PDFs\nmanual uploads"]

    subgraph MOUTH ["MOUTH — Ingestion"]
        direction TB
        M1["Scrapers\nBrowserless CT400/306"]
        M2["Scheduled API pulls\nn8n CT104"]
        M3["Manual uploads\nresearcher drops PDFs"]
    end

    RAW[("Raw store\nMongoDB CT121\nHTML · PDFs · JSON")]

    subgraph GUT ["GUT — Processing & Inference"]
        direction TB
        G1["Extract\nUnstructured CT117\nTika CT115"]
        G2["Embed + index\nQdrant CT102\nnomic-embed-text 768-dim"]
        G3["Infer\nLangGraph CT119\nLiteLLM CT205 → Groq"]
        G4["Score + stamp\nconfidence fusion\nEDRM evidence record"]
    end

    KG[("Knowledge graph\nNeo4j CT114\nnodes · edges\nconfidence · evidence")]

    subgraph PRESENTATION ["PRESENTATION — Output"]
        direction TB
        P1["Map\nKepler.gl geographic arcs"]
        P2["Graph\nNeo4j Bloom · NeoDash CT130"]
        P3["Report\nEDRM PDF → EU authority"]
    end

    EXT --> MOUTH
    MOUTH --> RAW
    RAW --> GUT
    GUT --> KG
    KG --> PRESENTATION
```

---

### Organ 1 — The Mouth (Ingestion)

Runs on its own schedule. Output: raw documents in MongoDB CT121.
The gut is not involved. The mouth does not parse or infer — it only collects.

```mermaid
flowchart TD
    subgraph TRIGGER ["Trigger sources"]
        T1["n8n cron\nMonday 06:00"]
        T2["Researcher request\ncompany name / barcode"]
        T3["Scheduled API poll\ndaily GDELT · weekly Comtrade"]
    end

    subgraph SCRAPE ["Web scraping (Browserless CT400 / CT306)"]
        T1 & T2 --> RESOLVE["Resolve company identity\nGS1 barcode → brand owner\nOpenCorporates → LEI → subsidiaries\nGLEIF → parent company graph"]
        RESOLVE --> URLS["Build URL list\nsupplier disclosure pages\nannual report PDFs\nsustainability report links"]
        URLS --> JS["Scrape JS-rendered pages\nPOST /scrape  port 3500\nwait_for: 1000ms"]
        JS --> FALLBACK{"CT400\nreachable?"}
        FALLBACK -->|Yes| STORE_HTML["Store raw HTML\n+ timestamp + URL"]
        FALLBACK -->|No| CT306["Fallback: CT306\n10.0.3.106:3500"]
        CT306 --> STORE_HTML
    end

    subgraph APIS ["Structured data pulls (n8n CT104)"]
        T3 --> COMTRADE["UN Comtrade API\ntrade flows by HS code + country"]
        T3 --> IMPORTYETI["ImportYeti\nUS bill-of-lading: exact shipments"]
        T3 --> OSH["OpenSupplyHub API\n900k verified facilities + GPS"]
        T3 --> GDELT["GDELT API\nnews events · violation incidents"]
        T3 --> ILO["ILO NORMLEX\nlabor violations by country/sector"]
        COMTRADE & IMPORTYETI & OSH & GDELT & ILO --> STORE_JSON["Store raw JSON\n+ source tag + timestamp"]
    end

    subgraph UPLOAD ["Manual upload (researcher)"]
        T2 --> UPLOAD_PDF["Researcher drops\nPDF · XLS · DOCX\ninto Kotaemon CT120"]
        UPLOAD_PDF --> STORE_DOC["Store binary + metadata\noriginal filename + SHA256"]
    end

    STORE_HTML & STORE_JSON & STORE_DOC --> MONGO[("MongoDB CT121\n10.0.1.121:27017\nraw_scrapes collection")]
    MONGO --> SIGNAL["Signal gut:\nnew documents ready"]
```

---

### Organ 2 — The Gut (Processing & Inference)

Triggered by new documents in MongoDB. Extracts, infers, scores, evidence-stamps.
Output: structured nodes + edges in Neo4j CT114.
Loops until depth limit or no new nodes found.

```mermaid
flowchart TD
    IN[("MongoDB CT121\nnew raw documents")] --> LANGGRAPH

    subgraph LANGGRAPH ["LangGraph CT119 — orchestrates the loop"]

        subgraph EXTRACT ["Step 1 — Extract"]
            E1["HTML/PDF → Unstructured CT117\nmultipart/form-data  POST /general/v0/general\nreturns structured text elements"]
            E2["Binary docs → Tika CT115\nXLS · DOC · PPTX  PUT /tika\nreturns plain text"]
        end

        subgraph EMBED ["Step 2 — Embed & Index"]
            EM1["Chunk text\n512-token windows"]
            EM2["Generate embeddings\nLiteLLM CT205 → nomic-embed-text\n768 dimensions"]
            EM3["Upsert into Qdrant CT102\ncollection: supplier_docs\nfor semantic search"]
        end

        subgraph INFER ["Step 3 — Infer Relationships"]
            I1["LiteLLM CT205 → Groq llama-3.3-70b\nprompt: extract supplier relationships\nfrom text as JSON array"]
            I2["Semantic search Qdrant\n'who supplies X?' → retrieve similar docs\ncross-validate inferred entities"]
        end

        subgraph SCORE ["Step 4 — Confidence Score Fusion"]
            S1["Trade signal  ×0.30\nComtrade + bill-of-lading match"]
            S2["Facility signal  ×0.25\nOpenSupplyHub GPS hit"]
            S3["Corporate signal  ×0.20\nOpenCorporates / GLEIF match"]
            S4["Document signal  ×0.15\nfound in annual report / filing"]
            S5["News signal  ×0.10\nGDELT event corroborates"]
            S1 & S2 & S3 & S4 & S5 --> FUSE["Weighted sum\n+ uncertainty band"]
        end

        subgraph EDRM ["Step 5 — EDRM Evidence Stamp"]
            EV1["Create EvidenceClaim node\nURL · SHA256 · timestamp\ninference method version"]
            EV2["Link: EvidenceClaim\n-[:EVIDENCE_FOR]->\nSupplier / RawMaterial node"]
            EV3["Log to Langfuse CT112\nfull LLM trace for audit"]
        end

        subgraph WRITE ["Step 6 — Write to Graph"]
            W1["MERGE Supplier / RawMaterial nodes\nMERGE SUPPLIED_BY / SOURCED_FROM edges\nset confidence · inferred: true"]
            W2["Apply risk flags\nSINGLE_SOURCE\nGEOPOLITICAL_RISK\nCBAM · LkSG · EUDR"]
            W3{New nodes\nfound and\ndepth < limit?}
            W3 -->|Yes — go deeper| EXTRACT
            W3 -->|Done| OUT
        end

    end

    EXTRACT --> EMBED --> INFER --> SCORE --> EDRM --> WRITE
    OUT[("Neo4j CT114\nnodes + edges\nconfidence + evidence")]
```

---

### Organ 3 — The Presentation Layer

Reads Neo4j on demand. Three independent interfaces for three use cases.
Regulatory report path is the end-to-end research output.

```mermaid
flowchart TD
    KG[("Neo4j CT114\nknowledge graph")]

    subgraph MAP ["Interface 1 — Geographic Map (Kepler.gl)"]
        KG --> K1["Export supplier nodes\nwith lat/lon + risk flags"]
        K1 --> K2["Kepler.gl arc layer\nnode = facility  arc = material flow\ncolor = risk  opacity = confidence"]
        K2 --> K3["Click node → evidence panel\nall sources for this supplier"]
    end

    subgraph GRAPH ["Interface 2 — Knowledge Graph (Neo4j Bloom / NeoDash CT130)"]
        KG --> B1["Graph topology view\nshortest path · shared suppliers\nbottleneck detection · community clusters"]
        KG --> B2["NeoDash analytics\nsupplier count by country\ntier distribution · risk heatmap\nlocal: http://localhost:15005"]
    end

    subgraph REPORT ["Interface 3 — Research Report & Regulatory Filing"]
        KG --> R1["Researcher reviews inferred nodes\nconfirm / reject / flag"]
        R1 --> R2["Retrieve EDRM package\nURL · SHA256 · signal weights\nfor each flagged node"]
        R2 --> R3{Violation +\nalternative\nevident?}
        R3 -->|Yes| R4["Draft report\nLiteLLM CT205\nEU CSDD / LkSG / UK Modern Slavery"]
        R3 -->|Monitor| R5["Archive case\nn8n weekly re-check"]
        R4 --> R6["Researcher review\nadd context + annotations"]
        R6 --> R7(["Submit to European Commission\nor national authority"])
        R7 --> R8["Fine issued\ncompany implements improvement\nworld slightly better"]
    end
```

---

## Infrastructure Map

Services grouped by organ. All on internal Proxmox subnets — VPN required from workstation.

```mermaid
graph TB
    subgraph WS ["Researcher Workstation"]
        BROWSER[Browser]
        TUNNELS["SSH Tunnels\n-L 15005 NeoDash\n-L 17474 Neo4j HTTP\n-L 17687 Neo4j Bolt"]
        BROWSER --- TUNNELS
    end

    subgraph MOUTH_INFRA ["MOUTH — Ingestion services"]
        CT104["n8n  CT104\n10.0.1.104:5678\ncron scheduler\nOSINT API pulls"]
        CT400["Browserless  CT400\n10.0.5.100:3500\nJS scraper  prod\nPOST /scrape"]
        CT306["Browserless  CT306\n10.0.3.106:3500\nJS scraper  acc fallback"]
        CT121["MongoDB  CT121\n10.0.1.121:27017\nraw_scrapes store"]
        CT120["Kotaemon  CT120\n10.0.1.120:8501\nmanual PDF upload + RAG"]
    end

    subgraph GUT_INFRA ["GUT — Processing services"]
        CT119["LangGraph  CT119\n10.0.1.119:8000\norchestrates the loop"]
        CT117["Unstructured  CT117\n10.0.1.117:8000\nHTML/PDF text extraction\nmultipart/form-data"]
        CT115["Tika  CT115\n10.0.1.115:9998\nbinary doc parser\nXLS · DOC · PPTX"]
        CT205["LiteLLM  CT205\n10.0.2.205:4000\nLLM proxy + embeddings\nGroq llama-3.3-70b"]
        CT102["Qdrant  CT102\n10.0.1.102:6333\nvector store\n768-dim embeddings"]
        CT112["Langfuse  CT112\n10.0.1.112:3000\nLLM trace + EDRM audit"]
    end

    subgraph STORE ["Knowledge Store"]
        CT114["Neo4j  CT114\n10.0.1.114:7474 / :7687\nKnowledge Graph\nSUPPLIED_BY · SOURCED_FROM\nEvidenceClaim nodes"]
        CT100["PostgreSQL  CT100\n10.0.1.100:5432\nknopenkonings DB\nstructured entity table"]
    end

    subgraph PRES_INFRA ["PRESENTATION — Output services"]
        CT130["NeoDash  CT130\n10.0.1.130:5005\nanalytics dashboard\ntunnel → localhost:15005"]
        CT206["Superset  CT206\n10.0.2.206:8088\nSQL dashboards"]
        CT202["Metabase  CT202\n10.0.2.202:3000\nalternative dashboards"]
    end

    subgraph EXT ["External"]
        GROQ["Groq API\nllama-3.3-70b"]
        COMTRADE["UN Comtrade"]
        IMPORTYETI["ImportYeti"]
        OSH["OpenSupplyHub"]
        GDELT["GDELT API"]
        GLEIF["GLEIF / OpenCorporates"]
    end

    TUNNELS --> CT130
    TUNNELS --> CT114

    CT104 --> CT400
    CT104 --> COMTRADE & IMPORTYETI & OSH & GDELT & GLEIF
    CT104 --> CT119
    CT400 --> CT121
    CT306 --> CT121

    CT119 --> CT117 & CT115 & CT102 & CT205 & CT112
    CT119 --> CT114
    CT121 --> CT119

    CT205 --> GROQ
    CT120 --> CT205 & CT114

    CT114 --> CT130 & CT206 & CT202 & CT100
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
