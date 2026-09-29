# Requirements

<!-- Generated from docs/requirements.yml by ResearchReady/workbook/scripts/workflows.py --write-repos. Edit the YAML, not this file. -->

Live service status from the ResearchReady probe (2026-09-28T20:52). ✅ up / available · ⚠️ partial · ❔ not probed (internal only or no public route) · ❌ down / broken · ⏳ missing · ❓ open decision.

## Shared services

| Item | Status | Needed for | Note |
|---|---|---|---|
| neo4j — supply-chain graph | ✅ up | Epic 2 | CT114 · https://neo4j.research-ready.nl |
| browserless — scrape supplier pages | ✅ up | Epic 3 | CT400 · https://browserless.research-ready.nl |
| unstructured — extract text | ✅ up | Epic 3 | CT117 · https://unstructured.research-ready.nl |
| tika — extract binary files | ❌ down | Epic 3 | CT115 · https://tika.research-ready.nl |
| qdrant — embeddings | ✅ up | Epic 3 | CT102 · https://qdrant.research-ready.nl |
| litellm — infer hidden suppliers | ✅ up | Epic 3 | CT205 · https://litellm.research-ready.nl |
| langgraph — SupplyLens agent (POST /runs) | ✅ up | Epic 3 | CT119 · https://langgraph.research-ready.nl |
| kotaemon — evidence RAG + citations | ✅ up | Epic 3 | CT129 · https://kotaemon.research-ready.nl Inventory has Kotaemon on CT129 and it answers; PLAN.md said CT120 / not provisioned |
| n8n — weekly refresh | ✅ up | Epic 4 | CT104 · https://n8n.research-ready.nl |
| postgres — knopenkonings.suppliers | ❔ not probed | Epic 4 | CT100 |
| superset — BI dashboards | ✅ up | Epic 4 | CT206 · https://superset.research-ready.nl |
| metabase — BI dashboards (alternative) | ✅ up | Epic 4 | CT202 · https://metabase.research-ready.nl |
| gitea — SupplyLens book CI | ✅ up | Epic 5 | CT200 · https://gitea.research-ready.nl |

## Tools & code

| Item | Status | Needed for | Note |
|---|---|---|---|
| Static dashboards + analysis modules (src/*.py, docs/*.html) | ✅ available | Epic 1 |  |
| Seed script (scripts/seed_scania.sh) | ✅ available | Epic 2 |  |
| Agent packaged as a LangGraph service | ⏳ missing | Epic 3 | src/agent.py exists |
| Scorecard PDF export (scripts/export_scorecard.py) | ⏳ missing | Epic 5 |  |

## Access & keys

| Item | Status | Needed for | Note |
|---|---|---|---|
| VPN route to bastion 10.0.0.16 (for seeding over SSH) | ❌ broken | Epic 2 | infra D-3 |
| Neo4j password | ✅ available | Epic 2 | KeePass entry Neo4j |
| Groq key for inference | ✅ available | Epic 3 |  |

## Data

| Item | Status | Needed for | Note |
|---|---|---|---|
| Scania graph cypher v10 (example_outputs/sample_graph.cypher) | ✅ available | Epic 2 |  |
| Synthetic supplier evidence documents | ✅ available | Epic 3 |  |
| Real supplier documents / ground truth from Scania | ⏳ missing | Epic 5 |  |

## Decisions & external actions

| Item | Status | Needed for | Note |
|---|---|---|---|
| Seed via SSH (needs VPN) or via the public Neo4j endpoint | ❓ open decision | Epic 2 |  |
| BI tool: Superset or Metabase | ❓ open decision | Epic 4 |  |
