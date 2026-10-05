"""SupplyLens Agent Server — FastAPI wrapper around the LangGraph enrichment graph.

Endpoints:
  GET  /health           — liveness + dependency status
  POST /runs             — start a supply-chain enrichment run (background)
  GET  /runs/{run_id}    — poll run status / result

Environment (all have defaults for local Docker Compose):
  NEO4J_URL         http://neo4j:7474
  NEO4J_PASSWORD    changeme
  LITELLM_URL       http://litellm:4000
  LITELLM_KEY       sk-uc4local
  QDRANT_URL        http://qdrant:6333
  LLM_MODEL         gpt-4o-mini
  EMBED_MODEL       nomic-embed-text

Usage:
  curl http://localhost:8090/health
  curl -X POST http://localhost:8090/runs \\
       -H 'Content-Type: application/json' \\
       -d '{"company":"Scania AB","product":"Scania R-series Truck","depth":2}'
"""
import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import urllib.request
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = FastAPI(title="SupplyLens Agent", version="1.0")

# In-memory run store — fine for single-instance local use
_runs: Dict[str, Dict[str, Any]] = {}


# ── helpers ──────────────────────────────────────────────────────────────────

def _http_ok(url: str, timeout: int = 4) -> bool:
    try:
        code = urllib.request.urlopen(
            urllib.request.Request(url), timeout=timeout
        ).status
        return code == 200
    except Exception:
        return False


def _build_graph():
    """Import and compile the LangGraph supply-chain enrichment graph."""
    # Set env vars the agent reads at import time
    os.environ.setdefault("NEO4J_URL",       "http://neo4j:7474")
    os.environ.setdefault("NEO4J_PASSWORD",  "changeme")
    os.environ.setdefault("LITELLM_URL",     "http://litellm:4000")
    os.environ.setdefault("LITELLM_KEY",     "sk-uc4local")
    os.environ.setdefault("QDRANT_URL",      "http://qdrant:6333")
    os.environ.setdefault("LLM_MODEL",       "gpt-4o-mini")
    os.environ.setdefault("EMBED_MODEL",     "nomic-embed-text")
    # Point at non-existent browserless/unstructured so agent skips gracefully
    os.environ.setdefault("BROWSERLESS_PROD_URL", "http://localhost:1")
    os.environ.setdefault("UNSTRUCTURED_URL",      "http://localhost:1")
    os.environ.setdefault("KOTAEMON_URL",           "http://localhost:1")

    from agent import graph  # noqa: PLC0415 — lazy import after env setup
    return graph


_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        _graph = _build_graph()
    return _graph


# ── schemas ───────────────────────────────────────────────────────────────────

class RunRequest(BaseModel):
    company: str
    product: str = ""
    depth: int = 2


class RunResponse(BaseModel):
    run_id: str
    status: str
    started_at: str


class RunStatus(BaseModel):
    run_id: str
    status: str        # pending | running | completed | failed
    started_at: str
    finished_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ── background task ───────────────────────────────────────────────────────────

async def _execute_run(run_id: str, company: str, product: str, depth: int):
    _runs[run_id]["status"] = "running"
    try:
        graph = _get_graph()
        state_in = {
            "product":       product or company,
            "company":       company,
            "depth":         depth,
            "current_depth": 0,
            "pending":       [company],
            "processed":     [],
            "scraped":       {},
            "texts":         {},
        }
        # Run in thread pool — LangGraph is sync
        loop = asyncio.get_event_loop()
        out = await loop.run_in_executor(None, lambda: graph.invoke(state_in))
        _runs[run_id].update({
            "status":      "completed",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "result": {
                "processed":  out.get("processed", []),
                "node_count": len(out.get("processed", [])),
            },
        })
    except Exception as exc:
        log.exception("Run %s failed", run_id)
        _runs[run_id].update({
            "status":      "failed",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "error":       str(exc),
        })


# ── endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    neo4j   = _http_ok(os.environ.get("NEO4J_URL",   "http://neo4j:7474") + "/")
    litellm = _http_ok(os.environ.get("LITELLM_URL", "http://litellm:4000") + "/health/liveliness")
    qdrant  = _http_ok(os.environ.get("QDRANT_URL",  "http://qdrant:6333") + "/healthz")
    return {
        "status": "ok",
        "deps": {"neo4j": neo4j, "litellm": litellm, "qdrant": qdrant},
    }


@app.post("/runs", response_model=RunResponse, status_code=202)
async def start_run(req: RunRequest):
    run_id = str(uuid.uuid4())
    started = datetime.now(timezone.utc).isoformat()
    _runs[run_id] = {"status": "pending", "started_at": started}
    asyncio.create_task(_execute_run(run_id, req.company, req.product, req.depth))
    return RunResponse(run_id=run_id, status="pending", started_at=started)


@app.get("/runs/{run_id}", response_model=RunStatus)
def get_run(run_id: str):
    run = _runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return RunStatus(run_id=run_id, **run)


@app.get("/runs")
def list_runs():
    return [{"run_id": k, **{f: v for f, v in v.items() if f != "result"}}
            for k, v in _runs.items()]
