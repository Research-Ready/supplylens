# UC4 Running Logs

Production pipeline execution logs are stored here as JSON lines.

## Format

Each log entry (one JSON object per line) follows this schema:

```json
{
  "timestamp": "2026-06-30T14:23:01Z",
  "input_companies": ["Scania AB"],
  "relationships_found": 12,
  "nodes_created": 8,
  "duration_s": 47,
  "neo4j_query": "MATCH (s:Supplier) RETURN count(s)",
  "status": "success"
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | ISO 8601 | When the pipeline run started |
| `input_companies` | string[] | Company names / product SKUs passed as input |
| `relationships_found` | int | Total SUPPLIED_BY + SOURCED_FROM edges discovered in this run |
| `nodes_created` | int | New nodes merged into Neo4j (0 if all already existed) |
| `duration_s` | float | Wall-clock seconds for full pipeline (scrape + extract + LLM + store) |
| `neo4j_query` | string | Final verification Cypher query run to confirm storage |
| `status` | string | `"success"` or `"failed"` |

## Log files

Files are named `YYYYMMDD_HHMMSS.jsonl` (one per pipeline trigger from n8n).

Example:
```
running_logs/
  20260630_142301.jsonl
  20260707_060001.jsonl   ← weekly Monday 06:00 n8n trigger
```

## n8n trigger

UC4 pipeline is triggered weekly (Monday 06:00) by n8n workflow on CT104.
Logs are written by the LangGraph agent as it completes each run.
