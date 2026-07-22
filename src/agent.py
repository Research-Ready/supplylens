"""UC4 Supply Chain Enrichment Agent — LangGraph StateGraph (CT119 :8000)
Graph: initialize → scrape → extract → embed → infer → merge → (loop until depth limit)
Trigger: POST /runs {"assistant_id": "supply-chain-enrichment",
                     "input": {"product": "...", "company": "...", "depth": 3}}
"""
import json
import logging
import os
import sys
import uuid
import urllib.request
import urllib.error
from typing import Dict, List, TypedDict

from langgraph.graph import StateGraph, END

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from neo4j_client import Neo4jClient

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

# Service config — env vars, defaults to internal cluster IPs
NEO4J_URL    = os.getenv("NEO4J_URL",            "http://10.0.1.114:7474")
NEO4J_USER   = os.getenv("NEO4J_USER",           "neo4j")
NEO4J_PASS   = os.getenv("NEO4J_PASSWORD",       "")
BROWSERLESS  = os.getenv("BROWSERLESS_PROD_URL", "http://10.0.5.100:3500")
UNSTRUCTURED = os.getenv("UNSTRUCTURED_URL",     "http://10.0.1.117:8000")
LITELLM      = os.getenv("LITELLM_URL",          "http://10.0.2.205:4000")
LITELLM_KEY  = os.getenv("LITELLM_KEY",          "")
QDRANT       = os.getenv("QDRANT_URL",           "http://10.0.1.102:6333")
QDRANT_KEY   = os.getenv("QDRANT_API_KEY",       "")
LLM_MODEL    = os.getenv("LLM_MODEL",            "researcher-llm")
EMBED_MODEL  = os.getenv("EMBED_MODEL",          "ollama/nomic-embed-text")
EMBED_DIMS   = 768
QDRANT_COLL  = "supplier_docs"
SCRAPE_WAIT  = int(os.getenv("SCRAPE_WAIT_FOR_MS", "1000"))

GEO_RISK_COUNTRIES = {"CN", "RU", "IR", "BY"}


class EnrichState(TypedDict):
    product:       str
    company:       str
    depth:         int           # max tier depth to traverse
    current_depth: int
    pending:       List[str]     # supplier names to process this iteration
    processed:     List[str]     # already handled (across all iterations)
    # Ephemeral per-iteration (reset by merge node)
    scraped:       Dict[str, str]   # supplier_name → raw HTML
    texts:         Dict[str, str]   # supplier_name → extracted plain text
    inferred:      List[Dict]       # new nodes from LLM
    # Cumulative
    stats:         Dict[str, int]   # nodes_added, edges_added, scraped, inferred
    errors:        List[str]        # non-fatal error messages


def _post_json(url: str, body: dict,
               headers: dict | None = None, timeout: int = 30) -> dict:
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers=h, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _post_multipart(url: str, html: bytes,
                    filename: str, timeout: int = 30) -> bytes:
    """Send HTML as multipart/form-data (required by Unstructured API)."""
    boundary = ("----UC4Boundary" + uuid.uuid4().hex[:12]).encode()
    body = (
        b"--" + boundary + b"\r\n"
        b'Content-Disposition: form-data; name="files"; filename="'
        + filename.encode() + b'"\r\n'
        b"Content-Type: text/html\r\n\r\n"
        + html
        + b"\r\n--" + boundary + b"--\r\n"
    )
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary.decode()}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _neo4j() -> Neo4jClient:
    return Neo4jClient(NEO4J_URL, NEO4J_USER, NEO4J_PASS)


def _embed(text: str) -> list[float]:
    data = _post_json(
        f"{LITELLM}/v1/embeddings",
        {"model": EMBED_MODEL, "input": text},
        {"Authorization": f"Bearer {LITELLM_KEY}"},
        timeout=20,
    )
    return data["data"][0]["embedding"]


def _qdrant_ensure_collection() -> None:
    """Create Qdrant collection if it doesn't already exist."""
    try:
        req = urllib.request.Request(
            f"{QDRANT}/collections/{QDRANT_COLL}",
            headers={"api-key": QDRANT_KEY},
        )
        with urllib.request.urlopen(req, timeout=10):
            return  # already exists
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
    # 404 — create it
    create_req = urllib.request.Request(
        f"{QDRANT}/collections/{QDRANT_COLL}",
        data=json.dumps({"vectors": {"size": EMBED_DIMS, "distance": "Cosine"}}).encode(),
        headers={"Content-Type": "application/json", "api-key": QDRANT_KEY},
        method="PUT",
    )
    with urllib.request.urlopen(create_req, timeout=15) as r:
        r.read()
    log.info("Created Qdrant collection: %s (%d dims)", QDRANT_COLL, EMBED_DIMS)


def _qdrant_upsert(points: list[dict]) -> None:
    req = urllib.request.Request(
        f"{QDRANT}/collections/{QDRANT_COLL}/points",
        data=json.dumps({"points": points}).encode(),
        headers={"Content-Type": "application/json", "api-key": QDRANT_KEY},
        method="PUT",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        r.read()


INFER_PROMPT = """\
You are a supply chain analyst. Extract ALL upstream suppliers and raw materials \
mentioned in the following text about {company}.

Source text:
{text}

Return ONLY a JSON array. Each element must have:
  "type":       "Supplier" or "RawMaterial"
  "name":       company or material name (string)
  "country":    ISO 2-letter code, best guess (e.g. "DE", "CN", "SE")
  "tier":       integer — 2 for sub-supplier, 3 for raw material source
  "component":  what they supply (string)
  "risk_flags": array — include "GEOPOLITICAL_RISK" if country is CN/RU/IR/BY,
                        include "SINGLE_SOURCE" if text implies only one source

JSON array only. No markdown fences, no explanation.
"""


def initialize(state: EnrichState) -> dict:
    """Query Neo4j for Tier-1 suppliers with websites; seed the pending queue."""
    db = _neo4j()
    rows = db.run(
        """
        MATCH (p:Product)-[:SUPPLIED_BY]->(s:Supplier)
        WHERE (p.name CONTAINS $product OR p.name CONTAINS $company)
          AND s.website IS NOT NULL
        RETURN s.name AS name
        """,
        {"product": state["product"], "company": state["company"]},
    )
    pending = [r["name"] for r in rows]
    log.info("initialize: %d Tier-1 suppliers queued: %s", len(pending), pending)
    return {
        "pending":       pending,
        "processed":     [],
        "current_depth": 1,
        "scraped":       {},
        "texts":         {},
        "inferred":      [],
        "stats":         {"nodes_added": 0, "edges_added": 0, "scraped": 0, "inferred": 0},
        "errors":        [],
    }


def scrape(state: EnrichState) -> dict:
    """Browserless-scrape the website of each pending supplier."""
    db = _neo4j()
    scraped: Dict[str, str] = {}
    errors = list(state["errors"])

    for name in state["pending"]:
        rows = db.run(
            "MATCH (s:Supplier {name: $name}) RETURN s.website AS website",
            {"name": name},
        )
        if not rows or not rows[0].get("website"):
            log.info("scrape: no website for %s — skipping", name)
            continue
        url = rows[0]["website"]
        try:
            data = _post_json(
                f"{BROWSERLESS}/scrape",
                {"url": url, "wait_for": SCRAPE_WAIT},
                timeout=40,
            )
            html = data.get("html", "")
            if html:
                scraped[name] = html
                log.info("scrape: %s → %d chars", name, len(html))
            else:
                errors.append(f"scrape: empty response for {name} ({url})")
        except Exception as exc:
            errors.append(f"scrape: {name} failed — {exc}")
            log.warning("scrape: %s error: %s", name, exc)

    stats = {**state["stats"], "scraped": state["stats"]["scraped"] + len(scraped)}
    return {"scraped": scraped, "stats": stats, "errors": errors}


def extract(state: EnrichState) -> dict:
    """Extract plain text from scraped HTML via Unstructured API."""
    texts: Dict[str, str] = {}
    errors = list(state["errors"])

    for name, html in state["scraped"].items():
        try:
            raw = _post_multipart(
                f"{UNSTRUCTURED}/general/v0/general",
                html.encode() if isinstance(html, str) else html,
                name.replace(" ", "_") + ".html",
                timeout=30,
            )
            elements = json.loads(raw)
            combined = " ".join(el["text"] for el in elements if el.get("text"))
            if combined:
                texts[name] = combined
                log.info("extract: %s → %d chars text", name, len(combined))
        except Exception as exc:
            errors.append(f"extract: {name} failed — {exc}")
            log.warning("extract: %s error: %s", name, exc)

    return {"texts": texts, "errors": errors}


def embed(state: EnrichState) -> dict:
    """Embed text chunks and upsert into Qdrant supplier_docs collection."""
    errors = list(state["errors"])
    if not state["texts"]:
        return {"errors": errors}

    try:
        _qdrant_ensure_collection()
        points = []
        for name, text in state["texts"].items():
            chunks = [text[i:i + 1000] for i in range(0, len(text), 1000)]
            for idx, chunk in enumerate(chunks[:5]):  # cap at 5 chunks/supplier
                try:
                    vector = _embed(chunk)
                    points.append({
                        "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{name}:{idx}")),
                        "vector": vector,
                        "payload": {
                            "supplier":  name,
                            "chunk_idx": idx,
                            "preview":   chunk[:200],
                        },
                    })
                except Exception as exc:
                    errors.append(f"embed: {name}[{idx}] failed — {exc}")
        if points:
            _qdrant_upsert(points)
            log.info("embed: upserted %d vectors", len(points))
    except Exception as exc:
        errors.append(f"embed: Qdrant error — {exc}")
        log.error("embed: %s", exc)

    return {"errors": errors}


def infer(state: EnrichState) -> dict:
    """Call LiteLLM to infer new supplier/material nodes from extracted text."""
    inferred: List[Dict] = []
    errors = list(state["errors"])

    for name, text in state["texts"].items():
        try:
            prompt = INFER_PROMPT.format(company=name, text=text[:3000])
            response = _post_json(
                f"{LITELLM}/v1/chat/completions",
                {
                    "model":       LLM_MODEL,
                    "messages":    [{"role": "user", "content": prompt}],
                    "max_tokens":  1000,
                    "temperature": 0.1,
                },
                {"Authorization": f"Bearer {LITELLM_KEY}"},
                timeout=120,
            )
            content = response["choices"][0]["message"]["content"].strip()
            # Strip markdown fences if LLM added them
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(
                    l for l in lines
                    if not l.startswith("```")
                )
            nodes = json.loads(content)
            for node in nodes:
                node["_from"] = name
            inferred.extend(nodes)
            log.info("infer: %s → %d new nodes", name, len(nodes))
        except Exception as exc:
            errors.append(f"infer: {name} failed — {exc}")
            log.warning("infer: %s error: %s", name, exc)

    stats = {**state["stats"], "inferred": state["stats"]["inferred"] + len(inferred)}
    return {"inferred": inferred, "stats": stats, "errors": errors}


def merge(state: EnrichState) -> dict:
    """MERGE inferred nodes into Neo4j; queue newly-found Suppliers for next depth."""
    db = _neo4j()
    nodes_added = 0
    edges_added = 0
    newly_found: List[str] = []
    processed = list(state["processed"]) + list(state["pending"])
    errors = list(state["errors"])

    for node in state["inferred"]:
        node_type = node.get("type", "Supplier")
        name      = (node.get("name") or "").strip()
        if not name:
            continue
        country   = (node.get("country") or "XX")[:2].upper()
        component = node.get("component", "")
        source    = node.get("_from", "")
        risk_flags = list(node.get("risk_flags") or [])
        if country in GEO_RISK_COUNTRIES and "GEOPOLITICAL_RISK" not in risk_flags:
            risk_flags.append("GEOPOLITICAL_RISK")

        try:
            if node_type == "Supplier":
                tier = int(node.get("tier") or (state["current_depth"] + 1))
                db.run(
                    """
                    MERGE (s:Supplier {name: $name})
                    ON CREATE SET s.country    = $country,
                                  s.tier       = $tier,
                                  s.inferred   = true,
                                  s.demo       = true
                    ON MATCH  SET s.country    = coalesce(s.country, $country)
                    SET s.risk_flags = $risk_flags
                    """,
                    {"name": name, "country": country,
                     "tier": tier, "risk_flags": risk_flags},
                )
                if source:
                    db.run(
                        """
                        MATCH (src:Supplier {name: $src}), (tgt:Supplier {name: $tgt})
                        MERGE (src)-[r:SOURCED_FROM]->(tgt)
                        ON CREATE SET r.component  = $component,
                                      r.inferred   = true,
                                      r.confidence = 0.7,
                                      r.source     = 'LLM inference'
                        """,
                        {"src": source, "tgt": name, "component": component},
                    )
                    edges_added += 1
                nodes_added += 1
                if name not in processed:
                    newly_found.append(name)

            else:  # RawMaterial
                mat_type = str(node.get("component") or "Unknown")
                db.run(
                    """
                    MERGE (r:RawMaterial {name: $name})
                    ON CREATE SET r.origin        = $country,
                                  r.material_type = $mat_type,
                                  r.inferred      = true,
                                  r.demo          = true
                    """,
                    {"name": name, "country": country, "mat_type": mat_type},
                )
                if source:
                    db.run(
                        """
                        MATCH (s:Supplier {name: $src}), (r:RawMaterial {name: $tgt})
                        MERGE (s)-[rel:SOURCED_FROM]->(r)
                        ON CREATE SET rel.component  = $component,
                                      rel.inferred   = true,
                                      rel.confidence = 0.7,
                                      rel.source     = 'LLM inference'
                        """,
                        {"src": source, "tgt": name, "component": component},
                    )
                    edges_added += 1
                nodes_added += 1

        except Exception as exc:
            errors.append(f"merge: {name} failed — {exc}")
            log.warning("merge: %s error: %s", name, exc)

    stats = {
        **state["stats"],
        "nodes_added": state["stats"]["nodes_added"] + nodes_added,
        "edges_added": state["stats"]["edges_added"] + edges_added,
    }
    log.info(
        "merge: depth=%d added %d nodes / %d edges; %d new suppliers queued",
        state["current_depth"], nodes_added, edges_added, len(newly_found),
    )

    return {
        "pending":       newly_found,
        "processed":     processed,
        "current_depth": state["current_depth"] + 1,
        "scraped":       {},
        "texts":         {},
        "inferred":      [],
        "stats":         stats,
        "errors":        errors,
    }


def route(state: EnrichState) -> str:
    """Decide whether to keep enriching or terminate."""
    if state["current_depth"] > state["depth"]:
        log.info("route: depth limit %d reached", state["depth"])
        return "end"
    if not state["pending"]:
        log.info("route: no more pending suppliers")
        return "end"
    log.info(
        "route: depth=%d, %d pending — continuing",
        state["current_depth"], len(state["pending"]),
    )
    return "continue"


_builder = StateGraph(EnrichState)
_builder.add_node("initialize", initialize)
_builder.add_node("scrape",     scrape)
_builder.add_node("extract",    extract)
_builder.add_node("embed",      embed)
_builder.add_node("infer",      infer)
_builder.add_node("merge",      merge)

_builder.set_entry_point("initialize")
_builder.add_edge("initialize", "scrape")
_builder.add_edge("scrape",     "extract")
_builder.add_edge("extract",    "embed")
_builder.add_edge("embed",      "infer")
_builder.add_edge("infer",      "merge")
_builder.add_conditional_edges(
    "merge", route, {"continue": "scrape", "end": END}
)

graph = _builder.compile()

# Local runner: python3 src/agent.py "Scania AB" "Scania R-series" 2
if __name__ == "__main__":
    _product = sys.argv[2] if len(sys.argv) > 2 else "Scania R-series Heavy Truck"
    _company = sys.argv[1] if len(sys.argv) > 1 else "Scania AB"
    _depth   = int(sys.argv[3]) if len(sys.argv) > 3 else 2

    _initial: EnrichState = {
        "product": _product, "company": _company, "depth": _depth,
        "current_depth": 0,
        "pending": [], "processed": [],
        "scraped": {}, "texts": {}, "inferred": [],
        "stats": {"nodes_added": 0, "edges_added": 0, "scraped": 0, "inferred": 0},
        "errors": [],
    }
    print(f"Running: {_product} / {_company} / depth={_depth}")
    _final = graph.invoke(_initial)
    print("Stats:", json.dumps(_final["stats"], indent=2))
    if _final["errors"]:
        print(f"Errors ({len(_final['errors'])}):")
        for e in _final["errors"]:
            print(f"  {e}")
