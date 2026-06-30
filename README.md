# UC4 — Supply Chain Visualization (Knopenkoning / Scania)

Given a product SKU or company name, this pipeline traverses the full supply chain
backwards: who supplies this component, who supplies the supplier, where do raw materials
originate. AI agents infer missing links. Everything is stored as a directed graph in
Neo4j. Superset and Metabase provide dashboards for supply chain analysts.

**Primary demo:** Scania AB (heavy trucks) — tier 1/2/3 supplier mapping.
**Secondary demo:** Knopenkoning (buttons) — AMS Buttons BV → Shenzhen Metal Co → raw materials.

---

## Pipeline Flow

```mermaid
flowchart TD
    A["Product identifier\n(SKU / company name / URL)"] --> B

    B["LangGraph CT119\n10.0.1.119:8000\norchestrates enrichment loop"]

    B --> C["Neo4j CT114\n10.0.1.114:7687\nquery existing graph\nCypher SUPPLIED_BY*1..5"]
    B --> D["Browserless CT400\n10.0.5.100:3500\nscrape JS supplier sites\nPOST /scrape"]
    D --> D2["Browserless CT306\n10.0.3.106:3500\nfallback scraper"]
    D --> E["Unstructured CT117\n10.0.1.117:8000\nextract text from HTML/PDFs\nmultipart/form-data"]
    D --> F["Tika CT115\n10.0.1.115:9998\nparse XLS DOC procurement docs"]
    E --> G["Qdrant CT102\n10.0.1.102:6333\nsemantic search over supplier docs\n768-dim nomic-embed-text"]
    G --> H["LiteLLM CT205\n10.0.2.205:4000\nGroq llama-3.3-70b\ninfer missing supply chain links"]
    H --> C

    C --> I["Superset CT206\n10.0.2.206:8088\nSQL dashboards"]
    C --> J["Metabase CT202\n10.0.2.202:3000\nalternative dashboards"]
    C --> K["n8n CT104\n10.0.1.104:5678\nweekly scheduled refresh"]
    C --> L["PostgreSQL CT100\n10.0.1.100:5432\nknopenkonings DB\nstructured entity table"]
    H --> M["Langfuse CT112\n10.0.1.112:3000\nLLM tracing + cost"]
```

---

## Quick Start (Dry Run)

```bash
# 1. VPN required
bash scripts/vpn-connect.sh connect

# 2. Run all 8 dry-run steps
bash usecases/uc4-supply-chain/scripts/dry_run.sh

# 3. Health check only
bash usecases/uc4-supply-chain/scripts/health_check.sh
```

---

## Services

| Service | Container | IP:Port | Role |
|---------|-----------|---------|------|
| Neo4j | CT114 | 10.0.1.114:7474 (HTTP) / :7687 (Bolt) | Supply chain graph |
| LangGraph | CT119 | 10.0.1.119:8000 | Agent orchestration |
| Browserless (prod) | CT400 | 10.0.5.100:3500 | JS scraping |
| Browserless (acc) | CT306 | 10.0.3.106:3500 | Fallback scraper |
| Unstructured | CT117 | 10.0.1.117:8000 | HTML/PDF extraction |
| Tika | CT115 | 10.0.1.115:9998 | Binary doc parsing |
| Qdrant | CT102 | 10.0.1.102:6333 | Vector search |
| LiteLLM | CT205 | 10.0.2.205:4000 | LLM inference |
| Superset | CT206 | 10.0.2.206:8088 | SQL dashboards |
| Metabase | CT202 | 10.0.2.202:3000 | Alternative dashboards |
| n8n | CT104 | 10.0.1.104:5678 | Scheduled refresh |
| PostgreSQL | CT100 | 10.0.1.100:5432 | Structured entity table |
| Langfuse | CT112 | 10.0.1.112:3000 | LLM tracing |

---

## Credentials

Stored in `passwords.kdbx` (master: `SupplyChainBaby100!`).

```python
from pykeepass import PyKeePass
kp = PyKeePass('usecases/uc4-supply-chain/passwords.kdbx', password='SupplyChainBaby100!')
neo4j = kp.find_entries(title='Neo4j', first=True)
print(neo4j.password)
```

---

## Neo4j Graph Schema

```cypher
// Node types
(p:Product {name, sku, category})
(s:Supplier {name, country, website, tier})
(r:RawMaterial {name, origin, material_type})
(c:Company {name, country, industry})
(cert:Certificate {name, issuer, valid_until})

// Relationships
(p)-[:SUPPLIED_BY {since, contract_value}]->(s)
(s)-[:SOURCED_FROM {volume_kg_year}]->(r)
(s)-[:CERTIFIED_BY]->(cert)
(s)-[:OWNED_BY]->(c)
(c)-[:SUBSIDIARY_OF]->(c)
```

---

## Critical Notes

- Browserless: endpoint is `/scrape` (NOT `/chromium/content`), port 3500
- CT400 has no SSH keys — use `pct exec 400 --` on node-4 (root@10.0.0.18)
- Unstructured requires `multipart/form-data` with `files` field — plain `text/html` body returns 422
- Embedding model: `ollama/nomic-embed-text` (768 dims) — NOT `text-embedding-3-small`
- Superset login issues: `systemctl restart superset` fixes PendingRollbackError
- Neo4j password: KeePass UC4 `Neo4j` entry, or CT114 `/root/.credentials/neo4j.txt`

See `CLAUDE.md` for full dry-run procedures and common failure fixes.
