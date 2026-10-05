# SupplyLens — Build Plan

> **See VISION.md for the full research concept, methodology, and academic context.**

**Concept:** Given a company name, product, or barcode — automatically map its
complete supply chain using OSINT, infer hidden nodes with AI confidence scoring,
flag violations, and produce EDRM-compliant evidence for regulatory enforcement.

**Industry partner:** Scania AB (ground truth validation)
**Goal:** Multi-signal OSINT inference + EDRM evidence chain + EU regulatory output

---

## What exists now

> **Infrastructure note (2026-10-05):** Proxmox server (10.0.x.x) is DOWN. All services run on local Docker Compose (`~/localstack/docker-compose.yml`). Start: `cd ~/localstack && docker compose up -d neo4j qdrant litellm langgraph n8n`

### Local stack services

| Service | URL | Status |
|---|---|---|
| Neo4j | http://localhost:7474 (bolt :7687) | ✅ Running (251 nodes seeded) |
| LangGraph Agent | http://localhost:8000 | ✅ Running |
| LiteLLM | http://localhost:4000 | ✅ Running (→ Ollama qwen3:8b) |
| Qdrant | http://localhost:6333 | ✅ Running |
| n8n | http://localhost:5678 | ✅ Running (workflows not imported) |
| Kotaemon | http://10.0.1.120:8501 | ⛔ Server down |
| Superset | http://10.0.2.206:8088 | ⛔ Server down |
| Metabase | http://10.0.2.202:3000 | ⛔ Server down |

### Visualizations (served at http://localhost:8765)

> Start: `cd ~/Nextcloud/Github/uc4-supply-chain/docs && python3 -m http.server 8765`
> Launcher: http://localhost:8765/index.html

| File | What you see | Backend |
|---|---|---|
| docs/index.html | Launcher — links to all 5 views, service status | Static |
| docs/supply_chain_geo.html | D3 world map, supplier pins by country, risk choropleth | Live Neo4j |
| docs/supply_chain_map.html | Supply chain relationship map, tier drill-down | Live Neo4j |
| docs/supplylens_3d.html | Three.js 3D force graph, 251 nodes, orbit+zoom, click for evidence | Live Neo4j |
| graphify-out/graph.html | Codebase knowledge graph, 34 nodes, 7 communities | Embedded |
| reports/_site/index.html | Quarto docs site: architecture, data model, services, status | Static |

> **Note:** 29 custom D3 dashboards were deleted in commit 87813fe (2026-08-15) and replaced by NeoDash (server-side). NeoDash is unavailable until server returns. The three files above are the working local replacements.

### Other assets

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
| example_outputs/sample_graph.cypher | v10: 2305 lines; 17 events; SCANIA-AXL autonomous truck AI chain (NVIDIA/TSMC/ASML/JSR) |
| scripts/ingest_kotaemon.py | Bulk ingest supplier docs into Kotaemon |
| scripts/seed_scania.sh | Load cypher into Neo4j CT114 |
| config/n8n_workflow.json | 14-node n8n weekly refresh workflow |

---

## Epic 6: OSIRIS-Inspired SupplyLens Intelligence Dashboard

> Inspiration: https://github.com/simplifaisoul/osiris — open-source Palantir alternative.
> Goal: replace flat D3 maps with a GPU-accelerated WebGL globe, OSIRIS-style HUD layer system, and a portable env-config so the stack switches between localhost and server with one variable.
> Copy freely from OSIRIS: MapLibre GL setup, CSS design tokens, Docker/nginx pattern, layer toggle HUD, `.env.example` structure.

**Working software:** A unified SupplyLens dashboard — OSIRIS aesthetic, live Neo4j data, runs on localhost and server from the same Docker image.

### E1 — Environment Config Layer *(prerequisite — do this first)*
- **E1.1** `docs/config.js` → `window.UC4_CONFIG = { NEO4J_HOST, NEO4J_PASS, NEO4J_DB }` — single source of truth
- **E1.2** Auto-detect: try `localhost:7474` on load, fall back to server IP on fail; show badge which is active
- **E1.3** Replace all hardcoded IPs/passwords in `supply_chain_geo.html`, `supply_chain_map.html`, `supplylens_3d.html` with `window.UC4_CONFIG`
- **E1.4** `scripts/serve.sh [local|server]` — writes correct `config.js` and starts HTTP server
- Status: ⛔ NOT BUILT

### E2 — MapLibre GL Globe *(replaces D3 flat map — copy OSIRIS map init)*
- **E2.1** Port `supply_chain_geo.html` to MapLibre GL JS — same Neo4j query, WebGL globe renderer
- **E2.2** Great-circle arcs between supplier nodes (animated flow lines, copy OSIRIS arc pattern)
- **E2.3** Animated pulse rings on risk-flagged nodes (`SINGLE_SOURCE`, `GEOPOLITICAL_RISK`)
- **E2.4** Country choropleth fill by supplier risk concentration
- **E2.5** Zoom-to-fit Scania supply chain on load (Sweden centroid → world)
- Status: ⛔ NOT BUILT

### E3 — OSIRIS-Style HUD Layer System
- **E3.1** HUD panel (top-left) — 8 toggleable layers with icons (copy OSIRIS CSS + toggle pattern):
  Tier 1 · Tier 2 · Tier 3+ · Raw Materials · Certificates · Risk Events · Logistics Hubs · Inferred Links
- **E3.2** Layer state persisted to `localStorage`
- **E3.3** "Risk only" mode — dim all non-risk nodes
- **E3.4** Live node count badge per layer
- Status: ⛔ NOT BUILT

### E4 — HUD Interface (OSIRIS aesthetic)
- **E4.1** Top-right stats panel: node count, link count, risk count, data source badge
- **E4.2** Bottom news ticker: recent `Event` nodes from Neo4j scrolling left
- **E4.3** Globe search bar — type supplier name → globe flies to pin
- **E4.4** Sidebar evidence panel from `supplylens_3d.html` ported into globe view
- **E4.5** CSS transitions on all panel open/close (copy OSIRIS Framer Motion → CSS equivalent)
- Status: ⛔ NOT BUILT

### E5 — Unified Launcher (OSIRIS home screen)
- **E5.1** Redesign `docs/index.html` as dark HUD — OSIRIS aesthetic, not card grid
- **E5.2** Live service status dots (Neo4j, LiteLLM, Qdrant) checked on load
- **E5.3** "Last graph update" from Neo4j node count query
- Status: 🟡 IN PROGRESS (basic card launcher exists; needs HUD redesign)

### E6 — Docker Portable Package
- **E6.1** nginx container serving `docs/` on port 8090; env var `UC4_NEO4J_HOST` injected into `config.js` at startup
- **E6.2** Merge into existing `docker/docker-compose.yml`; add `uc4-viz` service
- **E6.3** One-liner: `NEO4J_HOST=localhost docker compose up` — works both local and server
- **E6.4** Copy OSIRIS `.env.example` pattern — document every variable
- Status: ⛔ NOT BUILT

---

### OSINT Data Sources to Add (OSIRIS-inspired)

OSIRIS aggregates 16 free intel layers. UC4 supply chain equivalents:

| Source | What it adds | API / method |
|---|---|---|
| OpenCorporates | Company registration, ownership, subsidiaries | REST, keyless |
| OpenSanctions | OFAC/EU sanctions hits on supplier names | REST, keyless |
| GLEIF | Legal entity identifiers (LEI) — ownership chains | REST, keyless |
| TradeMap (ITC) | Trade flows by HS code — verify sourcing claims | Scrape |
| Panjiva / ImportYeti | US import records — who ships what from where | Scrape |
| OpenStreetMap Overpass | Factory/warehouse locations by tag | REST, keyless |
| USGS Minerals | Mine locations for raw materials (cobalt, lithium, rare earths) | REST, keyless |
| MarineTraffic / AIS | Vessel positions — detect logistics disruption | REST, free tier |
| GDACS | Natural disaster alerts near supplier locations | RSS, keyless |
| ACLED | Armed conflict events near supplier regions | REST, free tier |
| Companies House (UK) | Director/ownership data for EU subsidiaries | REST, keyless |
| Orbis via OpenCorporates | Cross-border corporate graph enrichment | via OpenCorporates |

All can be wired into the LangGraph enrichment agent (`src/agent.py`) as new nodes.

---

## Epics

_Epics are ordered from very simple to advanced; each one ends in **working software** you can demo. Items keep their original IDs (A–G). Requirements are in `docs/requirements.yml`._

## Epic 1: Static SupplyLens demo

**Working software:** The interactive dashboards (`docs/*.html`) run in a browser on the embedded Scania data: logistics risk, financial monitor, deep dive, chain diff, carbon, dual sourcing.

**Demo:** Open `docs/supplier_deep_dive.html` and `docs/logistics_risk.html` offline.

**Requires:** none (static files)

**A2 — Evidence geo map** `docs/evidence_map.html`
- What: D3 world map, supplier pins at real lat/lon, supply chain arcs,
  click supplier → evidence sidebar (docs, claims, confidence, source)
- Data: lat/lon already in cypher v8 for mines/logistics
- Status: BUILT

**A4 — EDRM pipeline tracker** `docs/edrm_tracker.html`
- What: per-supplier status grid — Scraped / Extracted / RAG-indexed / Reviewed
- Shows: pipeline completeness %, next action per supplier
- Status: BUILT

**C2 — Logistics route risk** `src/logistics_risk.py`
- What: score Suez / Malacca / Trans-Sib routes by disruption probability
- Which products halt, for how long, alt routes + cost premium
- Status: BUILT (7 routes, per-supplier routing map, €456M rev-at-risk demo)

**C3 — Financial monitoring script** `scripts/financial_monitor.py`
- What: weekly check — Z-score thresholds, covenant breach alerts
- Write alerts to Neo4j, surface in dashboard
- Status: BUILT (20 suppliers, Altman Z + ND/EBITDA + credit rating; FinancialAlert nodes)

**D1 — Logistics Risk Dashboard** `docs/logistics_risk.html`
- 7 chokepoint routes (Suez/Malacca/Trans-Sib/Cape/Panama/Bosphorus/Hormuz)
- D3 probability bars, scatter (Rev@Risk vs Delay, bubble=prob), supplier×route matrix
- Status: BUILT

**D2 — Financial Monitor Dashboard** `docs/financial_monitor.html`
- Altman Z-Score + ND/EBITDA D3 bars with zone thresholds (red 1.81 / yellow 2.99)
- D3 scatter: Z vs ND/EBITDA, quadrant shading; CRITICAL/HIGH/MEDIUM alert cards
- Status: BUILT

**D3 — Kotaemon RAG Search UI** `docs/kotaemon_search.html`
- Chat UI over 20 indexed supplier docs; citation display; 5 demo answers offline
- Live health-check of CT120 (10.0.1.120:8501) every 30s; real API call if online
- Status: BUILT

**D4 — Cypher v10 — Autonomous Truck AI chain** (appended to sample_graph.cypher)
- SCANIA-AXL Level 4 autonomous truck product
- T1: NVIDIA Corporation, Mobileye Global, Luminar Technologies (DISTRESS), Knorr-Bremse, HERE, Parker Hannifin
- T2: TSMC (Taiwan risk), ARM Holdings (SINGLE_SOURCE), ASML (export controls), Synopsys, Cadence
- T3: Shin-Etsu Chemical, JSR Corporation (EUV photoresist), Cryoin Engineering (Ukraine neon), Orano
- RawMaterials: Silicon Wafers, EUV Photoresist, Neon Gas, Hafnium, Germanium (China export controls)
- 17 events total (added NVIDIA export controls 2023, ASML China restriction, neon shortage 2022)
- Status: BUILT

**E1 — Chain Diff** `src/chain_diff.py` + `docs/chain_diff.html`
- Snapshot diff: new risk flags, Altman Z threshold crossings, tier changes, new suppliers
- Visual diff dashboard: CRITICAL/HIGH/MEDIUM severity filter, new nodes/relationships/events
- Status: BUILT (commit b2c0978)

**E2 — Supplier Deep Dive** `docs/supplier_deep_dive.html`
- Per-supplier comprehensive view: risk ring, financial bars, credit rating, events, logistics, evidence, compliance, alt suppliers
- 9 suppliers embedded: ZF/CATL/TSMC/Norilsk/Luminar/Leoni/SSAB/JSR/Bosch
- Status: BUILT (commit b2c0978)

**F1 — Carbon & CBAM tracker** `src/carbon_tracker.py` + `docs/carbon_footprint.html`
- Scope 1/2/3 emissions for 12 Scania suppliers; CBAM certificate cost; SBTi on-track check; CDP scores
- D3 bar chart: 5 modes (Scope1+2, Scope3, CO2 intensity, CBAM cost, YoY trend)
- Sidebar: per-supplier scope bars + SBTi/CDP badges + CBAM detail
- Status: BUILT (Phase 10)

**F2 — Dual sourcing optimizer** `src/dual_sourcing.py` + `docs/dual_sourcing.html`
- 9 suppliers × all alternatives; risk-weighted priority score; budget slider (greedy knapsack)
- Action tiers: IMMEDIATE/SHORT_TERM/MEDIUM_TERM/MONITOR
- D3 scatter: Priority vs Qualification Cost (bubble = rev@risk)
- Filter by action tier or single-source flag; per-supplier detail panel
- Status: BUILT (Phase 10)

## Epic 2: Live Scania graph

**Working software:** The Scania graph is seeded in Neo4j with evidence on every node, and the 3D graph and evidence map read it live instead of hard-coded data.

**Demo:** Click a supplier in `docs/supplylens_3d.html`; its evidence comes from Neo4j.

**Requires:** neo4j · seed via VPN or the public Neo4j endpoint

**A1 — Evidence store** `src/evidence_store.py`
- What: every Neo4j node gets `source_doc`, `source_excerpt`, `confidence` properties
- Functions: `store_evidence()`, `get_evidence()`, `mark_reviewed()`
- CLI: `python3 src/evidence_store.py get "Norilsk Nickel"`
- Status: BUILT (commit 3a2d19e)

**G1 — Seed the Scania demo graph into Neo4j**
- What: run `bash scripts/seed_scania.sh` (loads `example_outputs/sample_graph.cypher` v10 into CT114)
- Done when: `MATCH (n) RETURN count(n)` on CT114 matches the node count in the cypher file
- Blocked by: bastion 10.0.0.16 and CT114 unreachable over VPN (infra D-3, see SCANIA_DEMO_STATUS.md)
- Status: BLOCKED (needs VPN)

**A3 — 3D graph live evidence** (update `docs/supplylens_3d.html`)
- What: pull evidence from Neo4j via SSH tunnel instead of hardcoded JS
- Currently: evidence panel has hardcoded JS data
- Status: PARTIALLY BUILT (hardcoded evidence only)

**E3 — A3 live evidence in 3D graph** `docs/supplylens_3d.html`
- Three.js + 3d-force-graph, full Scania+autonomous-truck dataset embedded
- Fetches live from Neo4j localhost:7474 on load; falls back to embedded if offline
- Click node → evidence panel (risk badges, financials, upstream path)
- Filter by tier/type/risk; auto-rotate; dashed inferred links
- Status: BUILT

## Epic 3: Automated mapping agent

**Working software:** `POST /runs {"company": "Scania AB"}` scrapes, extracts, retrieves cited evidence from Kotaemon, infers hidden suppliers and merges them into Neo4j.

**Demo:** Run the agent for one supplier; new nodes appear with citations and confidence.

**Requires:** langgraph, browserless, unstructured, tika, kotaemon, qdrant, litellm

**B1 — Deploy Kotaemon CT120**
- What: run `bash scripts/provision_ct120.sh` on cluster
- Then: `python3 scripts/ingest_kotaemon.py` loads synthetic docs
- Status: PARTIALLY BUILT — Kotaemon answers at kotaemon.research-ready.nl (inventory: CT129, port 7860, probed 2026-09-28); verify the synthetic docs are ingested

**B2 — Citation extraction** (update `src/kotaemon_client.py`)
- What: parse `[Source: doc_name, p.N]` from Kotaemon answers
- Write citations back to Neo4j node as evidence via evidence_store
- Status: BUILT (commit c0e9f23)

**B3 — Wire citations into pipeline** (update `src/agent.py`)
- What: call `store_evidence()` in merge node after each inferred fact
- Result: every LLM-inferred supply chain link has a document citation
- Status: BUILT (commit c0e9f23)

**C1 — Cypher v9: event evidence links**
- What: each Event node gets `source_doc` + `source_url` properties
- Add: Taiwan Strait risk, Red Sea Houthi events with citations
- Status: BUILT (14 events, backfilled citations on all 12 existing, :AFFECTED_BY rel)

**E5 — Point SupplyLens at Kotaemon on CT129**
- Kotaemon runs on CT129:7860 (inventory), not CT120 (that is monitoring); update `scripts/provision_ct120.sh`, `src/kotaemon_client.py` and the D3 search UI health check (10.0.1.120:8501)
- Then: `python3 scripts/ingest_kotaemon.py` loads the synthetic docs
- Status: URL UPDATE DONE (2026-09-30 — all CT120:8501 refs changed to CT129:7860); doc ingest still blocked (needs VPN)

**G2 — Deploy the SupplyLens agent on CT119**
- What: serve `src/agent.py` as LangGraph `POST /runs` (scrape → extract → embed → infer → merge)
- Done when: `POST /runs {"company": "Scania AB"}` adds or updates suppliers in Neo4j with evidence
- Depends on: G1
- Status: BUILT locally — `src/agent_server.py` (FastAPI) + `docker/docker-compose.yml`; remote CT119 deploy still blocked (needs VPN)

## Epic 4: Self-refreshing intelligence

**Working software:** A weekly n8n run refreshes the graph, syncs suppliers to PostgreSQL and updates the BI dashboards; the chain diff shows what changed.

**Demo:** After Monday's run, the chain diff and Superset show the week's changes.

**Requires:** n8n, postgres, superset or metabase

**G3 — Activate the weekly n8n refresh**
- What: import `config/n8n_workflow.json` into n8n CT104; Monday 06:00 cron calls G2
- Done when: one scheduled execution finishes and the chain diff (E1) shows its changes
- Depends on: G2
- Status: NOT BUILT

**G4 — Schedule the PostgreSQL supplier sync**
- What: run `src/postgres_sync.py` after each refresh so Superset/Metabase can read `knopenkonings.suppliers`
- Done when: supplier rows match Neo4j after a G3 run
- Status: PARTIALLY BUILT (local test PASS 2026-09-30: 120 rows → knopenkonings.suppliers; not scheduled; PG_USER=localstack on local stack)

**G5 — Provision Superset dashboards**
- What: supplier count by country, tier pie, risk heatmap on CT206 (`scripts/setup_superset.py`)
- Done when: the three charts load from `knopenkonings.suppliers`
- Depends on: G4
- Status: NOT BUILT

## Epic 5: Deliverables for Scania

**Working software:** Per-supplier scorecard PDFs and a validated graph, documented in the SupplyLens book.

**Demo:** Hand Scania a scorecard PDF and the validation figures.

**Requires:** gitea (book CI) · Scania ground truth

**E4 — Supplier scorecard PDF export** `scripts/export_scorecard.py`
- Per-supplier A4 PDF: risk ring, flag pills, financials, certs, evidence, upstream path
- CLI: `--supplier NAME`, `--product SKU`, `--dry-run`, `--output-dir`
- Output: `output/scorecards/{slug}.pdf`; falls back to embedded data if Neo4j offline
- Status: BUILT

**G6 — Validate against Scania ground truth**
- What: compare the inferred tier-1/2 suppliers with a supplier list confirmed by Scania
- Done when: precision/recall of inferred links is reported in the book
- Status: NOT BUILT

## Build history (original execution order)

1. A1 — evidence_store.py ✓
2. A2 — evidence_map.html ✓
3. A4 — edrm_tracker.html ✓
4. B2 — kotaemon citation extraction ✓
5. B3 — wire citations into pipeline ✓
6. C1 — cypher v9 event evidence ✓
7. C2 — logistics route risk ✓
8. C3 — financial monitor ✓
9. D1 — logistics risk dashboard ✓
10. D2 — financial monitor dashboard ✓
11. D3 — Kotaemon search UI ✓
12. D4 — cypher v10 AI chain ✓
13. E1 — chain diff ✓
14. E2 — supplier deep dive ✓
15. F1 — carbon tracker + dashboard ✓
16. F2 — dual sourcing optimizer + dashboard ✓
17. E3 — 3D graph live evidence ✓
18. E4 — scorecard PDF export ✓
19. E5 — CT129 URL update ✓ (doc ingest VPN-blocked)
20. R1 — local dry-run 10/10 PASS ✓ (remote blocked, JSON output wired)
21. G4-local — postgres sync tested ✓ (120 rows, local stack)

## Definition of done

SupplyLens is done for the Scania demo when:

1. The Scania graph is seeded and the agent refreshes it weekly without manual steps (G1–G3)
2. Every inferred supplier carries evidence and a confidence score (A1, B3 — done)
3. Dashboards and the SupplyLens book show live data, not hard-coded examples (E3, G5)
4. A supplier scorecard PDF can be handed to Scania (E4)
5. The dry-run writes `test-results/` JSON and passes, so the coordinator shows UC4 green (R1)

## Risks & blockers

| Risk / blocker | Impact | Mitigation |
|---|---|---|
| VPN routing broken (infra D-3) | G1, G2, E5 cannot run on the cluster | Fix on the VPN server (ip_forward, FORWARD chain); until then work on local artefacts |
| Kotaemon CT120 not provisioned | Evidence RAG and citations stay synthetic | E5 once VPN works |
| LiteLLM model routing changes (Groq key, embedding model) | Inference step fails silently | Keep dry-run step 5/7 in CI; alias `ollama/nomic-embed-text` |
| Superset loses DB session (PendingRollbackError) | Dashboards error | `systemctl restart superset`; health check in dry-run |
| Evidence is synthetic for part of the graph | Demo credibility with Scania | Label synthetic evidence in the UI; replace via Kotaemon ingest |

## Documentation & readiness

**R1 — Dry-run writes JSON results**
- What: `scripts/dry_run.sh` writes `test-results/dry_run_YYYYMMDD_HHMMSS.json` with `steps: [{name, status}]`
- Local variant: `scripts/dry_run_local.py` tests localhost stack (steps 3/4/8 skipped)
- Done when: the ResearchReady workbook shows UC4's latest dry-run from the file, not from CLAUDE.md
- Status: BUILT (JSON output wired; remote run blocked until cluster returns)

**R2 — Colour-coded workflow**
- What: `docs/workflow.yml` describes every step with its status; rendered into the book and the workbook
- Status: DONE ✅ (2026-09-28)

**R3 — Complete plan**
- What: goal, status, definition of done, risks, readiness in this file
- Status: DONE ✅ (2026-09-28)

**R4 — Keep the book current**
- What: after each phase, update `reports/06-status.qmd`; CI (`build-book.yml`) publishes it
- Done when: book status chapter matches this plan
- Status: PARTIALLY BUILT (CI works; status chapter last updated before Phase 10)

### Next

Work the epics in order: finish Epic 2 (seed + live evidence), then Epic 3. R1 can be done any time.
