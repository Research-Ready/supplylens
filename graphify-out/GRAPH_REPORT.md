# Graph Report - .  (2026-07-11)

## Corpus Check
- Corpus is ~9,255 words - fits in a single context window. You may not need a graph.

## Summary
- 34 nodes · 68 edges · 7 communities (6 shown, 1 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 5 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_AI Pipeline and Inference|AI Pipeline and Inference]]
- [[_COMMUNITY_Dry-Run Automation|Dry-Run Automation]]
- [[_COMMUNITY_Scraping and Recovery|Scraping and Recovery]]
- [[_COMMUNITY_Service Config and Gotchas|Service Config and Gotchas]]
- [[_COMMUNITY_Scheduling and Outputs|Scheduling and Outputs]]
- [[_COMMUNITY_Test Procedures and Runbook|Test Procedures and Runbook]]
- [[_COMMUNITY_Health Check Scripts|Health Check Scripts]]

## God Nodes (most connected - your core abstractions)
1. `UC4 CLAUDE.md — dry-run runbook, pipeline config, service credentials, common fixes` - 15 edges
2. `UC4 Architecture — component roles, data flow sequence, risk flag logic, network requirements` - 10 edges
3. `UC4 Services Reference — per-service config, ports, auth, health check commands` - 9 edges
4. `UC4 Recovery Playbook — service-specific fixes and full stack restart order` - 7 edges
5. `dry_run.sh script` - 5 edges
6. `log()` - 4 edges
7. `ok()` - 4 edges
8. `fail()` - 4 edges
9. `check_http()` - 4 edges
10. `UC4 README.md — pipeline overview, mermaid flowchart, quick-start, credentials summary` - 4 edges

## Surprising Connections (you probably didn't know these)
- `UC4 Architecture — component roles, data flow sequence, risk flag logic, network requirements` --semantically_similar_to--> `UC4 README.md — pipeline overview, mermaid flowchart, quick-start, credentials summary`  [INFERRED] [semantically similar]
  docs/architecture.md → README.md
- `UC4 CLAUDE.md — dry-run runbook, pipeline config, service credentials, common fixes` --conceptually_related_to--> `UC4 Architecture — component roles, data flow sequence, risk flag logic, network requirements`  [INFERRED]
  CLAUDE.md → docs/architecture.md
- `UC4 dry-run 8-step test procedure — verifies full pipeline from Neo4j seed through Superset JWT login` --conceptually_related_to--> `LangGraph enrichment loop — orchestrates iterative scrape/extract/infer/store cycle until depth limit or no new nodes`  [INFERRED]
  test-results/README.md → docs/architecture.md
- `UC4 Test Results README — 8-step dry-run PASS/FAIL tracking and run generation instructions` --references--> `UC4 CLAUDE.md — dry-run runbook, pipeline config, service credentials, common fixes`  [EXTRACTED]
  test-results/README.md → CLAUDE.md
- `UC4 CLAUDE.md — dry-run runbook, pipeline config, service credentials, common fixes` --references--> `Supply Chain Graph — directed Neo4j graph with SUPPLIED_BY and SOURCED_FROM relationships across tiers`  [EXTRACTED]
  CLAUDE.md → docs/architecture.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **UC4 core pipeline services — LangGraph orchestrates Neo4j, Browserless, Unstructured, Tika, Qdrant, LiteLLM** — docs_architecture, docs_services, concept_langgraph_enrichment_loop, concept_supply_chain_graph, concept_nomic_embed [EXTRACTED 1.00]
- **Dry-run validation set — CLAUDE.md procedures verified by test-results, documented in services.md and recovery.md** — uc4_supply_chain_claude, test_results_readme, docs_services, docs_recovery, concept_dry_run_8_steps [EXTRACTED 1.00]
- **UC4 operational gotchas cluster — multipart requirement, /scrape endpoint, nomic-embed, pct exec, Groq key corruption, Superset rollback** — concept_multipart_unstructured, concept_browserless_scrape_endpoint, concept_nomic_embed, concept_pct_exec_ct400, concept_groq_key_corruption, concept_superset_pending_rollback [INFERRED 0.95]
- **UC4 demo scenarios — Scania AB (trucks) and Knopenkoning (buttons) both exercise the same pipeline** — concept_scania_demo, concept_knopenkoning_demo, data_sample_supplier_text, concept_supply_chain_graph [EXTRACTED 1.00]

## Communities (7 total, 1 thin omitted)

### Community 0 - "AI Pipeline and Inference"
Cohesion: 0.38
Nodes (10): Knopenkoning demo scenario — BTN-001 button supply chain: AMS Buttons BV → Shenzhen Metal Co → raw materials, LangGraph enrichment loop — orchestrates iterative scrape/extract/infer/store cycle until depth limit or no new nodes, LLM-inferred supply chain link — edges written to Neo4j with inferred:true and confidence score from LiteLLM inference, ollama/nomic-embed-text embedding model — 768-dim vectors via LiteLLM; text-embedding-3-small not configured, Supply chain risk flags — SINGLE_SOURCE and GEOPOLITICAL_RISK written to Supplier nodes by LangGraph agent, Scania AB demo scenario — tier 1/2/3 supplier graph for R-series heavy truck including ZF, Bosch, SSAB, Michelin, Dana, Cummins, Supply Chain Graph — directed Neo4j graph with SUPPLIED_BY and SOURCED_FROM relationships across tiers, Sample supplier text — ZF Friedrichshafen, SSAB AB, AMS Buttons BV supplier profiles (+2 more)

### Community 1 - "Dry-Run Automation"
Cohesion: 0.87
Nodes (5): dry_run.sh script, check_http(), fail(), log(), ok()

### Community 2 - "Scraping and Recovery"
Cohesion: 0.50
Nodes (4): Browserless /scrape endpoint — custom Playwright server; /chromium/content is invalid; port 3500 on both CT400 and CT306, Groq API key corruption fix — box-drawing chars (\xe2\x94\x80) appended to gsk_ key in /etc/litellm/config.yaml line 230, pct exec 400 access pattern — CT400 has no SSH keys; access only via pct exec on node-4 (root@10.0.0.18), UC4 Recovery Playbook — service-specific fixes and full stack restart order

### Community 3 - "Service Config and Gotchas"
Cohesion: 0.50
Nodes (4): knopenkonings database — PostgreSQL structured entity table for supply chain data on CT100, Unstructured multipart/form-data requirement — plain text/html body returns 422; files field required, Superset PendingRollbackError fix — SQLAlchemy connection state after idle; resolved by systemctl restart superset, UC4 Services Reference — per-service config, ports, auth, health check commands

### Community 4 - "Scheduling and Outputs"
Cohesion: 0.67
Nodes (4): n8n weekly supply chain refresh — cron every Monday 06:00; scrape → extract → infer → MERGE pipeline, Pipeline running log schema — JSONL with timestamp, input_companies, relationships_found, nodes_created, duration_s, status, UC4 Example Outputs README — sample_graph.cypher usage and running log schema, UC4 Running Logs README — JSONL log schema, field descriptions, n8n trigger schedule

### Community 5 - "Test Procedures and Runbook"
Cohesion: 1.00
Nodes (3): UC4 dry-run 8-step test procedure — verifies full pipeline from Neo4j seed through Superset JWT login, UC4 Test Results README — 8-step dry-run PASS/FAIL tracking and run generation instructions, UC4 CLAUDE.md — dry-run runbook, pipeline config, service credentials, common fixes

## Knowledge Gaps
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `UC4 CLAUDE.md — dry-run runbook, pipeline config, service credentials, common fixes` connect `Test Procedures and Runbook` to `AI Pipeline and Inference`, `Scraping and Recovery`, `Service Config and Gotchas`, `Scheduling and Outputs`?**
  _High betweenness centrality (0.270) - this node is a cross-community bridge._
- **Why does `n8n weekly supply chain refresh — cron every Monday 06:00; scrape → extract → infer → MERGE pipeline` connect `Scheduling and Outputs` to `Service Config and Gotchas`, `Test Procedures and Runbook`?**
  _High betweenness centrality (0.119) - this node is a cross-community bridge._
- **Why does `UC4 Architecture — component roles, data flow sequence, risk flag logic, network requirements` connect `AI Pipeline and Inference` to `Scraping and Recovery`, `Service Config and Gotchas`, `Test Procedures and Runbook`?**
  _High betweenness centrality (0.101) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `UC4 Architecture — component roles, data flow sequence, risk flag logic, network requirements` (e.g. with `Sample supplier text — ZF Friedrichshafen, SSAB AB, AMS Buttons BV supplier profiles` and `UC4 README.md — pipeline overview, mermaid flowchart, quick-start, credentials summary`) actually correct?**
  _`UC4 Architecture — component roles, data flow sequence, risk flag logic, network requirements` has 3 INFERRED edges - model-reasoned connections that need verification._