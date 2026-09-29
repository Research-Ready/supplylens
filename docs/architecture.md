# UC4 Architecture — Supply Chain Visualization

## Overview

UC4 is a multi-agent supply chain enrichment pipeline. Starting from a product identifier
or company name, LangGraph orchestrates a loop that scrapes supplier websites, extracts
structured data from documents, infers missing relationships via LLM, stores everything
in Neo4j, and makes it queryable via Superset/Metabase dashboards.

The pipeline is designed to discover Tier 1 → Tier 2 → Tier 3 supplier relationships
automatically, including AI-inferred links marked with `inferred: true` and a confidence
score for analyst review.

---

## Component Roles

### LangGraph (CT119 — localhost:8000)

Orchestrates the enrichment loop. Each iteration:
1. Query Neo4j for known nodes missing outbound edges
2. Dispatch scrape tasks to Browserless
3. Send scraped HTML to Unstructured for text extraction
4. Embed extracted text into Qdrant for semantic retrieval
5. Call LiteLLM to infer new supplier/material relationships
6. MERGE new nodes and edges into Neo4j
7. Repeat until depth limit reached or no new nodes discovered

### Neo4j (CT114 — localhost:7474 HTTP / :7687 Bolt)

Central knowledge store. Graph schema:
- `Product` → `SUPPLIED_BY` → `Supplier`
- `Supplier` → `SOURCED_FROM` → `Supplier | RawMaterial`
- `Supplier` → `CERTIFIED_BY` → `Certificate`
- `Supplier` → `OWNED_BY` → `Company`
- `Company` → `SUBSIDIARY_OF` → `Company`

Traversal query pattern:
```cypher
MATCH path = (p:Product {sku: $sku})-[:SUPPLIED_BY|SOURCED_FROM*1..3]->(n)
RETURN [node in nodes(path) | coalesce(node.name, node.sku)] AS chain,
       length(path) AS depth
ORDER BY depth
```

### Browserless (CT400 prod / CT306 acc — port 3500)

Custom Playwright-based JS scraping server. Key endpoint: `POST /scrape`.
Request body: `{"url": "...", "wait_for": 1000}`.
Response: `{"html": "...", "status_code": 200}`.

CT400 (node-4, 10.0.5.100) is primary. CT306 (node-3, 10.0.3.106) is fallback.
CT400 has no SSH keys — access via `pct exec 400 --` on node-4 (root@10.0.0.18).

### Unstructured (CT117 — 10.0.1.117:8000)

Converts HTML/PDFs to structured text elements. Endpoint: `POST /general/v0/general`.
Requires `multipart/form-data` with a `files` field — plain text/html body returns HTTP 422.

### Tika (CT115 — 10.0.1.115:9998)

Apache Tika for binary document parsing (XLS, DOC, PPTX, PDF). Used for procurement
documents and supplier capability statements. Endpoint: `PUT /tika`.

### Qdrant (CT102 — localhost:6333)

Vector store for supplier document embeddings. Collection: `supplier_docs`.
Embedding model: `ollama/nomic-embed-text` via LiteLLM (768 dimensions).
Semantic queries: "who supplies raw materials to button manufacturers?" etc.

### LiteLLM (CT205 — localhost:4000)

Unified LLM proxy. Model routing for UC4:
- `researcher-llm` → Groq `llama-3.3-70b-versatile` (primary, free tier)
- `ollama/nomic-embed-text` → local Ollama on fedora GPU node (768-dim embeddings)

Common issue: Groq API key corruption (box-drawing chars appended). Fix:
```bash
ssh root@10.0.2.205 "sed -i 's/\xe2\x94\x80//g' /etc/litellm/config.yaml && systemctl restart litellm"
```

### Superset (CT206 — 10.0.2.206:8088)

Apache Superset for SQL-based dashboards. Connects to Neo4j via JDBC connector,
and to PostgreSQL `knopenkonings` DB for structured entity tables.

### n8n (CT104 — localhost:5678)

Weekly Cron trigger (Monday 06:00) runs the full enrichment loop for known companies.
Also handles notifications (Slack/email) with new node counts after each run.

---

## Data Flow Sequence

```
1. Input: {"product": "Scania R-series", "company": "Scania AB", "depth": 3}
   │
2. LangGraph queries Neo4j for existing graph (returns empty or partial)
   │
3. LangGraph dispatches Browserless scrapes:
   - scania.com/suppliers → HTML
   - ZF annual report URL → HTML
   │
4. HTML → Unstructured → [{text: "ZF supplies gearboxes..."}, ...]
   │
5. Text chunks → LiteLLM embeddings (nomic-embed-text) → Qdrant UPSERT
   │
6. Text → LiteLLM (researcher-llm) → JSON array of inferred relationships:
   [{"name": "ZF Friedrichshafen", "country": "DE", "tier": 1, "supplies": "gearboxes"},
    {"name": "Saarstahl AG", "country": "DE", "tier": 2, "supplies": "steel billets"}]
   │
7. Neo4j MERGE: new Supplier nodes + SUPPLIED_BY / SOURCED_FROM edges
   - Inferred edges carry: {inferred: true, confidence: 0.8, source: "LLM"}
   │
8. Repeat for Tier 2 suppliers discovered in step 6
   │
9. Superset/Metabase dashboards auto-refresh via materialized views
```

---

## Risk Flag Logic

Two risk flags are written to Neo4j Supplier nodes by the LangGraph agent:

- `SINGLE_SOURCE`: supplier has no alternative (only 1 inbound `SUPPLIED_BY` edge)
- `GEOPOLITICAL_RISK`: `country IN ["CN", "RU", "IR", "BY"]`

These power the Superset risk heatmap chart.

---

## Network Requirements

All containers are on internal Proxmox subnets. VPN required from workstation.
Cross-node routing (CT400 on node-4 ↔ CT114 on node-1) requires `ip_forward=1`
on Proxmox nodes. If cross-VM calls return 000: check `sysctl net.ipv4.ip_forward`
on the relevant node.
