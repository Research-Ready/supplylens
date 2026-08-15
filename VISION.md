# SupplyLens — Research Vision & Concept Document

**Institution:** University research project
**Industry partner:** Scania AB (ground truth validation)
**Status:** Concept — pre-implementation
**Date:** 2026-08-15

---

## The Problem: Supply Chain Blindness

Companies typically know their supply chain only 2–3 tiers deep. Beyond that, it becomes
an ever-expanding spider's web — opaque, undocumented, and deliberately obscured. Even
Scania, a sophisticated manufacturer, has no reliable picture of who supplies their
suppliers' suppliers.

This blindness has consequences:
- Environmental violations hidden in Tier 3–5 (mines, smelters, plantations)
- Labor abuses (forced labor, child labor) invisible to the brand
- Geopolitical risk undetected until disruption hits
- Cheaper, greener material alternatives suppressed because change costs money
- Regulatory due diligence laws (EU CSDD, LkSG, UK Modern Slavery Act) impossible
  to comply with honestly

**The holy grail of supply chain** is full end-to-end visibility — knowing every node,
every relationship, every practice from raw material to finished product. It has never
been achieved at scale.

---

## The Research Hypothesis

**AI can infer hidden supply chain nodes by fusing multiple weak OSINT signals, each
with an independently verifiable evidence trail, to produce a probabilistic knowledge
graph of the complete supply chain — including nodes the company itself does not know.**

The core contribution is the **multi-signal confidence fusion methodology**:

```
Signal 1: Trade flow data (UN Comtrade, bill of lading)        → weight 0.30
Signal 2: Facility location data (OpenSupplyHub, satellite)    → weight 0.25
Signal 3: Corporate structure (OpenCorporates, GLEIF LEI)      → weight 0.20
Signal 4: Document extraction (annual reports, filings)        → weight 0.15
Signal 5: News & incident data (GDELT, NGO databases)          → weight 0.10
──────────────────────────────────────────────────────────────────────────
Inferred node confidence score: weighted sum + uncertainty band
```

Every inferred node is stored with:
- Confidence score (0.0–1.0)
- Contributing signals (what evidence supports this)
- Source documents (URL + SHA256 hash + timestamp)
- Inference method version

This methodology is validated against Scania's known supplier data. Where Scania can
confirm or deny an inferred node, the confidence weights are calibrated.

---

## The Three Research Use Cases

### Use Case 1 — Supply Chain Mapping
Researcher types "Scania AB" or a product barcode.
The system automatically:
- Resolves company identity (GS1, OpenCorporates)
- Scrapes known supplier disclosures (annual reports, sustainability reports)
- Pulls trade flow data (what flows into/out of Scania's known facilities)
- Cross-references facility databases (OpenSupplyHub)
- Infers Tier 3–5 nodes with confidence scores
- Flags violations from GDELT + NGO databases

Output: A probabilistic supply chain graph with evidence for every claim.

### Use Case 2 — Material Alternative Research
Researcher identifies a component (e.g. a specific steel grade from a sanctions-listed
Russian supplier). The system:
- Maps who else uses this component
- Finds alternative materials/suppliers (MatWeb, materials science databases + LLM)
- Calculates cost delta and CO2 reduction potential
- Identifies whether the company already has knowledge of the alternative
  (searched in their own disclosed documents and filings)

Output: Evidence-backed improvement proposal with cost/CO2 calculation.

### Use Case 3 — Suppressed Evidence & Regulatory Filing
If the research reveals that a company:
- Knew about a cheaper/greener alternative (evidence: internal documents, patents, filings)
- Chose not to implement it (evidence: no change, continued sourcing from harmful supplier)
- Actively lobbied against the change (evidence: lobbying records, GDELT)

Then the EDRM evidence chain allows the researcher to file a formal report with the
European Commission or national authority. The report is legally defensible because
every claim traces back to a hashed source document with full chain of custody.

**The enforcement loop:**
```
Research finds suppressed improvement
        ↓
EDRM report filed with EU authority
        ↓
Fine issued (based on available evidence)
        ↓
Fine > cost of implementing improvement
        ↓
Company implements improvement
        ↓
World is slightly better
```

---

## The Three Interfaces

### Interface 1 — Geographic Map (Primary)
**Tool:** Kepler.gl (Uber open source, self-hostable)

World map with supply chain arcs:
- Node = supplier facility, mine, factory, port
- Arc = material/product flow, thickness = volume, color = risk level
- Click node → evidence panel opens (all data found about this node)
- Confidence shown as node opacity (0.4 = inferred, 1.0 = confirmed)
- Violation flags shown as red pulsing nodes
- Filter by: tier, country, risk flag, confidence threshold, material type

### Interface 2 — Knowledge Graph (Analysis)
**Tool:** Neo4j Bloom (included with Neo4j)

Network topology view:
- Full graph exploration
- Shortest path between two suppliers
- Who else uses this component (shared node query)
- Community detection (clusters of co-dependent suppliers)
- Bottleneck identification (single-source nodes)

### Interface 3 — Process Flow (Documentation)
**Tool:** bpmn.io (open source, embeddable)

BPMN-style linear view of the supply chain:
- Left to right: raw material → processing → component → assembly → product
- Each step shows: who does it, where, what inputs/outputs
- Used for reports and regulatory submissions
- Exportable as standardized BPMN XML

---

## The EDRM Evidence Layer

Every piece of data in the system is stored EDRM-compliant from the moment it enters:

```
IDENTIFICATION  → what sources exist (URLs, documents, databases)
PRESERVATION    → SHA256 hash of source content at time of collection
COLLECTION      → method (scraped/API/upload), timestamp, agent version
PROCESSING      → extraction method (Unstructured/Tika), model version, confidence
REVIEW          → researcher decision (confirmed/rejected/flagged), timestamp, ID
ANALYSIS        → inference method, signal weights, uncertainty score
PRODUCTION      → export format, recipient, case ID, timestamp
```

This means:
- No claim exists without a traceable source
- No source exists without a hash (tamper-evident)
- No inference exists without a confidence score and methodology version
- The full audit trail is queryable and exportable

EDRM is not just methodology — it is the legal framework that makes the regulatory
output admissible.

---

## Data Sources

| Source | What | Access |
|--------|------|--------|
| ImportYeti | US bill-of-lading: exact shipments company→company | Free web |
| UN Comtrade API | Aggregate trade flows by HS code, country-pair | Free API |
| OpenSupplyHub API | 900k+ verified manufacturing facilities, GPS, certs | Free API |
| OpenCorporates | 200M+ companies, ownership, subsidiaries | Free tier API |
| GLEIF (LEI data) | Legal Entity Identifiers, parent/child company graph | Free bulk download |
| GDELT | 500M+ global news events, queryable by actor/location/theme | Free API |
| Know The Chain | Forced labor benchmarks by sector | Free |
| WikiRate | Crowd-sourced ESG data, company-level | Free API |
| Sentinel Hub | ESA satellite imagery (deforestation, mine activity, smoke) | Free for research |
| Global Forest Watch | Deforestation alerts linked to commodities | Free API |
| Open Food Facts | Food product ingredients + origin + manufacturer | Free API |
| GS1 Verified by GS1 | Barcode prefix → brand owner company | Free |
| MatWeb | 175k materials, mechanical/chemical properties | Free tier |
| ECHA (EU chemicals) | REACH substance declarations, hazardous material suppliers | Free |
| ILO NORMLEX | Labor violation data by country/sector | Free |

---

## Academic Context

This work builds on:

- **[Helicase (arXiv 2605.26835, May 2025)](https://arxiv.org/html/2605.26835v1)** —
  uncertainty-guided supply chain KG construction with multi-agent LLMs. 85% Graph F1
  on hardest queries. Closest academic precedent. Our contribution: OSINT as primary
  signal (vs. company disclosures) + EDRM evidence chain + regulatory output.

- **[GNN link prediction (Taylor & Francis 2021)](https://www.tandfonline.com/doi/full/10.1080/00207543.2021.1956697)** —
  graph neural networks infer hidden supplier links from local graph structure only.
  Applicable for our Tier 3–5 inference.

- **[GenAI + KG relationship prediction (2025)](https://www.tandfonline.com/doi/full/10.1080/00207543.2025.2543964)** —
  LLM embeddings anchored to KG for multi-tier dependency inference.

- **[McKinsey: Supply chain resilience — is there a holy grail?](https://www.mckinsey.com/capabilities/operations/our-insights/supply-chain-resilience-is-there-a-holy-grail)** —
  confirms multi-tier transparency is the unsolved problem.

Commercial analog: **[Altana AI](https://altana.ai/)** — $1B+ valuation, maps 50% of
global trade using customs data + AI. Validates the market. Our differentiation:
open data sources + EDRM evidence chain + regulatory enforcement output.

---

## Technology Stack

### Existing (keep and use correctly)
| Tool | Role |
|------|------|
| Neo4j (CT114) | Supply chain knowledge graph storage |
| LangGraph (CT119) | AI agent orchestration (scrape → extract → infer → store) |
| Browserless (CT400) | Scrape JS-rendered supplier websites, annual reports |
| Unstructured (CT117) | Extract text from HTML/PDF |
| Tika (CT115) | Parse binary docs (Excel supplier lists, Word contracts) |
| LiteLLM (CT205) | LLM inference (entity extraction, material alternatives, report drafting) |
| Qdrant (CT102) | Semantic search over scraped supplier documents |
| Kotaemon (CT120) | RAG: chat with uploaded supplier PDFs, annual reports |
| n8n (CT104) | Scheduled data pulls (UN Comtrade weekly, GDELT daily, OpenSupplyHub) |
| PostgreSQL (CT100) | Structured entity table, researcher sessions, case management |
| Langfuse (CT112) | LLM call tracing (evidence chain for AI inference steps) |

### To add
| Tool | Role | Why |
|------|------|-----|
| **Kepler.gl** | Geographic map interface | Primary user interface, self-hostable |
| **Neo4j Bloom** | Graph exploration interface | Already included in Neo4j, needs enabling |
| **bpmn.io** | Process flow interface | Open source, embeddable, BPMN standard |
| **Grafana** (optional) | Operational monitoring | If Superset/Metabase insufficient |

### Custom code (minimal — glue only)
- `src/osint_pipeline.py` — orchestrates data source pulls into Neo4j
- `src/confidence_scorer.py` — multi-signal fusion, uncertainty quantification
- `src/edrm_store.py` — EDRM-compliant evidence storage (extends existing evidence_store.py)
- `src/report_generator.py` — generates EU-submissible regulatory report from EDRM data
- n8n workflows — scheduled data pulls from each OSINT source
- LangGraph agent — inference pipeline (OSINT signals → inferred nodes → Neo4j)

---

## Validation Strategy (with Scania)

1. **Phase 1 — Baseline**: Tool maps Scania Tier 1 from public sources only.
   Scania confirms accuracy. Establish precision/recall baseline.

2. **Phase 2 — Inference**: Tool infers Tier 2–3 from OSINT signals.
   Scania confirms/denies each inferred node. Calibrate confidence weights.

3. **Phase 3 — Unknown territory**: Tool infers Tier 4–5 (Scania has no data here).
   Independent verification via investigative journalism databases, NGO reports,
   trade data cross-reference.

4. **Phase 4 — Violation detection**: Tool flags known violations in the graph.
   Cross-reference with public enforcement actions to validate.

---

## The Contribution

**Technical:** Multi-signal OSINT confidence fusion for probabilistic supply chain
knowledge graph construction. Uncertainty quantification at node and edge level.

**Methodological:** EDRM evidence framework applied to supply chain research, enabling
regulatory-grade evidence production from academic research.

**Practical:** Working tool deployed with an actual manufacturer (Scania), with
validated results across at least 3 supply chain tiers.

**Policy:** Demonstration that AI-assisted OSINT can produce legally admissible evidence
of corporate environmental/social due diligence failures, enabling EU enforcement.

---

## What Success Looks Like

A researcher types "Scania AB".
Within minutes, the map shows supply chain arcs reaching from Sweden to Taiwan,
China, Russia, DRC, India.
Each node shows: what's known (confirmed), what's inferred (confidence score),
what violations are flagged (with sources).
The researcher clicks a cobalt mine node in DRC — child labor risk, 0.83 confidence,
3 source documents, GDELT incident 2024-03-14.
They click "generate report" — a structured EDRM-compliant PDF is produced,
every claim traceable, every source hashed.
That report is sent to the European Commission.
The world is slightly better.
