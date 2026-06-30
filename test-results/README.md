# UC4 Test Results

Dry-run output files are stored here, named `dry_run_YYYYMMDD_HHMMSS.txt`.

Each file contains step-by-step PASS/FAIL for all 8 pipeline steps:

1. Neo4j seed (BTN-001 supply chain)
2. Neo4j backward traversal (>=4 paths expected)
3. Browserless scrape via CT400 `/scrape` endpoint
4. Unstructured HTML extraction (multipart/form-data)
5. LiteLLM inference (Groq llama-3.3-70b)
6. Neo4j inferred link store
7. Qdrant embedding (nomic-embed-text, 768 dims)
8. Superset dashboard JWT login

## Current status (2026-06-30)

All 8 steps passing. See `CLAUDE.md` for details.

## Generating a new test run

```bash
cd /path/to/InstallLocalAiPackage
bash usecases/uc4-supply-chain/scripts/dry_run.sh 2>&1 | tee usecases/uc4-supply-chain/test-results/dry_run_$(date +%Y%m%d_%H%M%S).txt
```
