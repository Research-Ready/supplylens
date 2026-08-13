# SupplyLens — Build Plan

**Concept:** Given a company name, automatically discover its full supply chain
by fact-finding public documents (annual reports, filings, news), store evidence
in a graph with citations, and visualize as 3D graph + 2D evidence map.

---

## What exists now

### Live services (VPN required)

| Service | URL | Role |
|---|---|---|
| Neo4j Browser | http://10.0.1.114:7474 | Query supply chain graph |
| LangGraph Agent | http://10.0.1.119:8000 | Enrichment pipeline |
| Kotaemon RAG | http://10.0.1.120:8501 | Chat with supplier docs |
| Superset | http://10.0.2.206:8088 | SQL dashboards |
| Metabase | http://10.0.2.202:3000 | Alt dashboards |
| n8n | http://10.0.1.104:5678 | Scheduled refresh |
| LiteLLM | http://10.0.2.205:4000 | LLM + embeddings |
| Qdrant | http://10.0.1.102:6333 | Vector search |

### Dashboard (open docs/dashboard.html in browser)

17 tabs:

| Tab | File | What you see |
|---|---|---|
| Risk | dashboard.html (inline) | Risk leaderboard, score bars |
| Graph | dashboard.html (inline) | D3 force graph, 2D |
| Geo | supply_chain_geo.html | World map, supplier pins |
| Events | dashboard.html (inline) | Supply chain events timeline |
| Disruption | disruption_impact.html | Revenue at risk per scenario |
| Finance | financial_exposure.html | Contract values, exposure |
| Resilience | resilience_dashboard.html | 6-dim HHI resilience radar |
| SupplierIntel | supplier_intel.html | Per-supplier detail cards |
| Report | report_demo.html | Auto-generated procurement report |
| Compliance | compliance_tracker.html | 7-regulation matrix |
| SharedSuppliers | shared_suppliers.html | Cross-product concentration |
| TierDrill | tier_drill.html | Collapsible T0→T4 tree |
| CBAM | cbam_dashboard.html | Carbon border tax liability |
| Scenarios | scenario_dashboard.html | 7 stress test scenarios |
| Network | network_analytics.html | Centrality, HHI, bottlenecks |
| Monte Carlo | simulation_dashboard.html | 10k-trial disruption sim |
| Fin Health | financial_health.html | Altman Z-scores, leverage |

### Standalone

| File | What you see |
|---|---|
| docs/supplylens_3d.html | 3D Three.js graph — click node for evidence panel |

### Code

| File | What it does |
|---|---|
| src/agent.py | LangGraph: scrape→extract→kotaemon_rag→embed→infer→compliance_check→merge |
| src/neo4j_client.py | Cypher query wrapper |
| src/kotaemon_client.py | Kotaemon RAG client, circuit breaker, fact sheet builder |
| src/risk_scorer.py | Risk flag → score logic |
| src/cbam_calculator.py | CBAM liability per supplier |
| src/alternative_sourcing.py | Alt supplier scorer, SWITCH_NOW/DUAL_SOURCE |
| src/disruption_model.py | Disruption scenarios, revenue-at-risk |
| src/resilience_scorer.py | 6-dim HHI resilience |
| src/scenario_modeler.py | 7 named scenarios with best/base/worst |
| src/supply_chain_simulator.py | Monte Carlo 10k trials, P10/P50/P90 |
| src/graph_analyzer.py | Degree/betweenness/HHI/bottleneck/longest-path |
| src/sanctions_screener.py | Fuzzy OFAC/EU/UN name screening |
| src/procurement_report.py | HTML procurement report per SKU |
| src/postgres_sync.py | Neo4j → PostgreSQL knopenkonings.suppliers |
| example_outputs/sample_graph.cypher | v8: 80+ nodes, T0→T4, mines, logistics, fin health |
| scripts/ingest_kotaemon.py | Bulk ingest supplier docs into Kotaemon |
| scripts/seed_scania.sh | Load cypher into Neo4j CT114 |
| config/n8n_workflow.json | 14-node n8n weekly refresh workflow |

---

## Build plan — ordered

### A. SupplyLens evidence layer

**A1 — Evidence store** `src/evidence_store.py`
- What: every Neo4j node gets `source_doc`, `source_excerpt`, `confidence` properties
- Functions: `store_evidence()`, `get_evidence()`, `mark_reviewed()`
- CLI: `python3 src/evidence_store.py get "Norilsk Nickel"`
- Status: BUILT (commit 3a2d19e)

**A2 — Evidence geo map** `docs/evidence_map.html`
- What: D3 world map, supplier pins at real lat/lon, supply chain arcs,
  click supplier → evidence sidebar (docs, claims, confidence, source)
- Data: lat/lon already in cypher v8 for mines/logistics
- Status: BUILT

**A3 — 3D graph live evidence** (update `docs/supplylens_3d.html`)
- What: pull evidence from Neo4j via SSH tunnel instead of hardcoded JS
- Currently: evidence panel has hardcoded JS data
- Status: PARTIALLY BUILT (hardcoded evidence only)

**A4 — EDRM pipeline tracker** `docs/edrm_tracker.html`
- What: per-supplier status grid — Scraped / Extracted / RAG-indexed / Reviewed
- Shows: pipeline completeness %, next action per supplier
- Status: BUILT

---

### B. Kotaemon integration

**B1 — Deploy Kotaemon CT120**
- What: run `bash scripts/provision_ct120.sh` on cluster
- Then: `python3 scripts/ingest_kotaemon.py` loads synthetic docs
- Status: CT120 not provisioned (script exists)

**B2 — Citation extraction** (update `src/kotaemon_client.py`)
- What: parse `[Source: doc_name, p.N]` from Kotaemon answers
- Write citations back to Neo4j node as evidence via evidence_store
- Status: NOT BUILT

**B3 — Wire citations into pipeline** (update `src/agent.py`)
- What: call `store_evidence()` in merge node after each inferred fact
- Result: every LLM-inferred supply chain link has a document citation
- Status: NOT BUILT

---

### C. More supply chain depth

**C1 — Cypher v9: event evidence links**
- What: each Event node gets `source_doc` + `source_url` properties
- Add: Taiwan Strait risk, Red Sea Houthi events with citations
- Status: BUILT (14 events, backfilled citations on all 12 existing, :AFFECTED_BY rel)

**C2 — Logistics route risk** `src/logistics_risk.py`
- What: score Suez / Malacca / Trans-Sib routes by disruption probability
- Which products halt, for how long, alt routes + cost premium
- Status: BUILT (7 routes, per-supplier routing map, €456M rev-at-risk demo)

**C3 — Financial monitoring script** `scripts/financial_monitor.py`
- What: weekly check — Z-score thresholds, covenant breach alerts
- Write alerts to Neo4j, surface in dashboard
- Status: BUILT (20 suppliers, Altman Z + ND/EBITDA + credit rating; FinancialAlert nodes)

---

## Execution order

1. A1 — evidence_store.py  ← START HERE
2. A2 — evidence_map.html
3. A4 — edrm_tracker.html
4. B2 — kotaemon citation extraction
5. B3 — wire citations into pipeline
6. A3 — 3D graph live evidence pull
7. C1 — cypher v9 event evidence
8. C2 — logistics route risk
9. C3 — financial monitor
10. B1 — deploy CT120 (needs VPN + cluster access)
