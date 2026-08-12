"""Kotaemon RAG Client — UC4 Supply Chain (CT120, port 8501)

Wraps Kotaemon's Gradio queue API for:
  - Document ingestion (POST /upload → /file)
  - RAG queries (queue/join → queue/status poll)
  - Health check + circuit breaker
  - Structured fact-sheet generation from Neo4j data

Kotaemon is Gradio-based; it doesn't expose a clean REST API.
We use the undocumented Gradio queue and file upload APIs.
Falls back gracefully when CT120 is unreachable.

Usage:
    from kotaemon_client import KotaemonClient
    kc = KotaemonClient("http://10.0.1.120:8501")
    if kc.health():
        answer = kc.query("Who supplies steel to Scania?")
        kc.ingest_text("ZF Friedrichshafen", "ZF is a Tier-1 gearbox supplier...")
"""

import json
import logging
import os
import tempfile
import time
import uuid
import urllib.request
import urllib.error
import urllib.parse
from typing import Optional

log = logging.getLogger(__name__)

KOTAEMON_URL     = os.getenv("KOTAEMON_URL",      "http://10.0.1.120:8501")
KOTAEMON_USER    = os.getenv("KOTAEMON_USER",     "admin@research-ready.nl")
KOTAEMON_PASS    = os.getenv("KOTAEMON_PASSWORD", "")

# Gradio API constants (Kotaemon uses Gradio 3.x queue API)
# fn_index values discovered by inspecting /info endpoint
FN_CHAT   = 0   # chat submit (fn_index in Gradio 3)
FN_UPLOAD = 1   # file upload (fn_index in Gradio 3)

# Circuit breaker: stop hammering if CT120 is down
_CIRCUIT_OPEN  = False
_CIRCUIT_RESET = 0.0   # unix timestamp when to retry
CIRCUIT_TIMEOUT = 120  # seconds before retry after open


class KotaemonClient:
    """Kotaemon RAG client with graceful offline fallback."""

    def __init__(self, base_url: str = KOTAEMON_URL,
                 username: str = KOTAEMON_USER,
                 password: str = KOTAEMON_PASS,
                 timeout: int = 30):
        self.base = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self._session_hash = uuid.uuid4().hex[:8]
        self._cookies: dict[str, str] = {}

    # ─── Low-level helpers ───────────────────────────────────────────────────

    def _get(self, path: str, timeout: int | None = None) -> bytes:
        req = urllib.request.Request(f"{self.base}{path}")
        if self._cookies:
            req.add_header("Cookie", "; ".join(f"{k}={v}" for k, v in self._cookies.items()))
        with urllib.request.urlopen(req, timeout=timeout or self.timeout) as r:
            # capture Set-Cookie
            cookie_hdr = r.headers.get("Set-Cookie", "")
            if cookie_hdr:
                for part in cookie_hdr.split(";"):
                    part = part.strip()
                    if "=" in part:
                        k, v = part.split("=", 1)
                        self._cookies[k.strip()] = v.strip()
            return r.read()

    def _post_json(self, path: str, body: dict, timeout: int | None = None) -> dict:
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            f"{self.base}{path}", data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        if self._cookies:
            req.add_header("Cookie", "; ".join(f"{k}={v}" for k, v in self._cookies.items()))
        with urllib.request.urlopen(req, timeout=timeout or self.timeout) as r:
            return json.loads(r.read())

    def _post_multipart(self, path: str, filename: str, content: bytes,
                        mime: str = "text/plain") -> dict:
        boundary = ("----UC4KotaemonBoundary" + uuid.uuid4().hex[:10]).encode()
        body = (
            b"--" + boundary + b"\r\n"
            b'Content-Disposition: form-data; name="files"; filename="'
            + filename.encode() + b'"\r\n'
            b"Content-Type: " + mime.encode() + b"\r\n\r\n"
            + content
            + b"\r\n--" + boundary + b"--\r\n"
        )
        req = urllib.request.Request(
            f"{self.base}{path}", data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary.decode()}"},
            method="POST",
        )
        if self._cookies:
            req.add_header("Cookie", "; ".join(f"{k}={v}" for k, v in self._cookies.items()))
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read())

    # ─── Circuit breaker ─────────────────────────────────────────────────────

    def _circuit_ok(self) -> bool:
        global _CIRCUIT_OPEN, _CIRCUIT_RESET
        if _CIRCUIT_OPEN:
            if time.time() >= _CIRCUIT_RESET:
                _CIRCUIT_OPEN = False
                log.info("kotaemon: circuit breaker reset — retrying CT120")
            else:
                return False
        return True

    def _trip_circuit(self) -> None:
        global _CIRCUIT_OPEN, _CIRCUIT_RESET
        _CIRCUIT_OPEN  = True
        _CIRCUIT_RESET = time.time() + CIRCUIT_TIMEOUT
        log.warning("kotaemon: circuit breaker OPEN — CT120 unreachable, retry in %ds", CIRCUIT_TIMEOUT)

    # ─── Public API ──────────────────────────────────────────────────────────

    def health(self) -> bool:
        """Returns True if Kotaemon is reachable."""
        if not self._circuit_ok():
            return False
        try:
            self._get("/", timeout=5)
            return True
        except Exception as exc:
            self._trip_circuit()
            log.debug("kotaemon health: %s", exc)
            return False

    def login(self) -> bool:
        """Authenticate if Kotaemon has login enabled. Optional — most installs are open."""
        if not self.password:
            return True
        try:
            body = {"data": [self.username, self.password], "fn_index": 0,
                    "session_hash": self._session_hash}
            self._post_json("/login", body, timeout=10)
            return True
        except Exception as exc:
            log.debug("kotaemon login: %s", exc)
            return False

    def query(self, question: str, query_timeout: int = 40) -> str:
        """RAG query via Gradio queue. Returns answer text or '' on failure."""
        if not self._circuit_ok():
            return ""
        try:
            # Gradio 3 queue: POST /queue/join → event_id → poll /queue/status
            join_body = {
                "data": [question, None],
                "event_data": None,
                "fn_index": FN_CHAT,
                "session_hash": self._session_hash,
            }
            join_resp = self._post_json("/queue/join", join_body, timeout=10)
            event_id = join_resp.get("event_id")
            if not event_id:
                log.debug("kotaemon query: no event_id in join response")
                return ""

            deadline = time.time() + query_timeout
            while time.time() < deadline:
                status_resp = self._post_json(
                    "/queue/status",
                    {"hash": event_id, "session_hash": self._session_hash},
                    timeout=10,
                )
                status = status_resp.get("status")
                if status == "complete":
                    data = status_resp.get("output", {}).get("data", [])
                    return self._extract_answer(data)
                if status == "error":
                    log.warning("kotaemon query error: %s", status_resp.get("output"))
                    return ""
                time.sleep(1.5)

            log.warning("kotaemon query timed out after %ds", query_timeout)
            return ""

        except urllib.error.URLError as exc:
            self._trip_circuit()
            log.debug("kotaemon query URL error: %s", exc)
            return ""
        except Exception as exc:
            log.warning("kotaemon query: %s", exc)
            return ""

    @staticmethod
    def _extract_answer(data: list) -> str:
        """Parse Gradio output data[] into plain text answer."""
        if not data:
            return ""
        first = data[0]
        # Chat history: [[user, bot], ...]
        if isinstance(first, list):
            for pair in reversed(first):
                if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                    return str(pair[1]) if pair[1] else ""
        # Plain string
        if isinstance(first, str):
            return first
        return str(first)

    def ingest_text(self, doc_name: str, text: str,
                    metadata: dict | None = None) -> bool:
        """Upload a text document to Kotaemon for indexing.

        Uses Gradio file upload API. Returns True on success.
        """
        if not self._circuit_ok():
            return False
        try:
            # Write to temp file — Kotaemon expects a real file upload
            content = text.encode("utf-8")
            if metadata:
                header = json.dumps(metadata, ensure_ascii=False)
                content = f"METADATA: {header}\n\n".encode() + content

            filename = doc_name.replace(" ", "_").replace("/", "-") + ".txt"
            resp = self._post_multipart("/upload", filename, content, "text/plain")
            log.info("kotaemon ingest: %s → %s", doc_name, resp)
            return True
        except urllib.error.URLError as exc:
            self._trip_circuit()
            log.debug("kotaemon ingest URL error: %s", exc)
            return False
        except Exception as exc:
            log.warning("kotaemon ingest: %s → %s", doc_name, exc)
            return False

    def batch_ingest(self, docs: dict[str, str],
                     delay_sec: float = 1.0) -> dict[str, bool]:
        """Ingest multiple documents. docs = {name: text}. Returns {name: success}."""
        results = {}
        for name, text in docs.items():
            results[name] = self.ingest_text(name, text)
            if delay_sec > 0:
                time.sleep(delay_sec)
        return results

    def build_supplier_fact_sheet(self, name: str, country: str, tier: int,
                                  risk: str, flags: list[str],
                                  upstream: list[str], downstream: list[str],
                                  certs: list[str],
                                  contract_value: str | None = None,
                                  events: list[str] | None = None,
                                  cbam_product: str | None = None,
                                  cbam_co2: float | None = None) -> str:
        """Generate a structured fact sheet text suitable for Kotaemon ingestion.

        Format mirrors what Kotaemon's RAG needs for good retrieval.
        """
        lines = [
            f"SUPPLIER FACT SHEET: {name}",
            "=" * 60,
            f"Company:        {name}",
            f"Country:        {country}",
            f"Supply Tier:    T{tier}",
            f"Risk Level:     {risk}",
        ]
        if contract_value:
            lines.append(f"Contract Value: {contract_value}/year")
        if flags:
            lines.append(f"Risk Flags:     {', '.join(flags)}")
        if certs:
            lines.append(f"Certifications: {', '.join(certs)}")
        if cbam_product:
            lines.append(f"CBAM Product:   {cbam_product}")
        if cbam_co2:
            lines.append(f"CO2 Intensity:  {cbam_co2:.0f} kg/tonne")
        lines.append("")
        if upstream:
            lines.append("UPSTREAM SUPPLIERS:")
            for u in upstream:
                lines.append(f"  - {u}")
        if downstream:
            lines.append("")
            lines.append("DOWNSTREAM (SUPPLIED TO):")
            for d in downstream:
                lines.append(f"  - {d}")
        if events:
            lines.append("")
            lines.append("DISRUPTION EVENTS:")
            for e in events:
                lines.append(f"  ! {e}")
        lines.append("")
        lines.append("RISK ANALYSIS:")
        risk_notes = {
            "CRITICAL": f"{name} is rated CRITICAL risk. Immediate alternative sourcing required.",
            "HIGH":     f"{name} is rated HIGH risk. Dual-sourcing or qualification of alternatives recommended.",
            "MEDIUM":   f"{name} is rated MEDIUM risk. Monitoring and contingency planning advised.",
            "LOW":      f"{name} is rated LOW risk. Normal monitoring cadence.",
        }
        lines.append(risk_notes.get(risk, f"{name}: unknown risk level."))
        if "SANC" in flags or "SANCTIONS" in flags:
            lines.append(f"WARNING: {name} appears on OFAC/EU/UN sanctions watchlist. Legal review required before any new contracts.")
        if "UFLPA" in flags:
            lines.append(f"WARNING: {name} at risk under UFLPA — US Customs may detain imports. Audit required.")
        if "GEO" in flags:
            lines.append(f"NOTE: {name} is in a geopolitically sensitive region ({country}). Monitor for export controls.")
        if cbam_product:
            lines.append(f"NOTE: CBAM applies to {cbam_product} imports from {country}. Verify carbon certificates.")
        return "\n".join(lines)


def build_all_fact_sheets(neo4j_url: str, neo4j_user: str,
                          neo4j_pass: str) -> dict[str, str]:
    """Query Neo4j and build fact sheets for all suppliers.

    Returns {supplier_name: fact_sheet_text}
    """
    import base64
    auth = base64.b64encode(f"{neo4j_user}:{neo4j_pass}".encode()).decode()
    query = """
    MATCH (s:Supplier)
    OPTIONAL MATCH (s)<-[:SUPPLIED_BY|SOURCED_FROM]-(upstream)
    OPTIONAL MATCH (s)-[:SUPPLIED_BY|SOURCED_FROM]->(downstream)
    OPTIONAL MATCH (s)-[:CERTIFIED_BY]->(cert)
    RETURN s.name AS name, s.country AS country, s.tier AS tier,
           s.risk AS risk, s.flags AS flags,
           s.contract_value AS contract_value,
           s.cbam_product AS cbam_product,
           s.cbam_co2_intensity_kg_per_tonne AS cbam_co2,
           collect(DISTINCT upstream.name) AS upstream,
           collect(DISTINCT downstream.name) AS downstream,
           collect(DISTINCT cert.name) AS certs
    """
    body = {"statements": [{"statement": query}]}
    req = urllib.request.Request(
        f"{neo4j_url}/db/neo4j/tx/commit",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Basic {auth}"},
        method="POST",
    )
    sheets = {}
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read())
        rows = d["results"][0]["data"]
        cols = d["results"][0]["columns"]
        for row in rows:
            record = {cols[i]: row["row"][i] for i in range(len(cols))}
            name = record.get("name") or "Unknown"
            kc = KotaemonClient()
            sheets[name] = kc.build_supplier_fact_sheet(
                name=name,
                country=record.get("country") or "XX",
                tier=int(record.get("tier") or 1),
                risk=record.get("risk") or "LOW",
                flags=record.get("flags") or [],
                upstream=[x for x in (record.get("upstream") or []) if x],
                downstream=[x for x in (record.get("downstream") or []) if x],
                certs=[x for x in (record.get("certs") or []) if x],
                contract_value=record.get("contract_value"),
                cbam_product=record.get("cbam_product"),
                cbam_co2=float(record.get("cbam_co2") or 0) or None,
            )
    except Exception as exc:
        log.warning("build_all_fact_sheets: Neo4j error: %s", exc)
    return sheets


def main() -> None:
    import argparse, sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(description="Kotaemon client CLI")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("health", help="Check CT120 reachability")

    qp = sub.add_parser("query", help="RAG query")
    qp.add_argument("question", nargs="+")

    ip = sub.add_parser("ingest-all", help="Build + ingest all supplier fact sheets from Neo4j")
    ip.add_argument("--neo4j-url",  default=os.getenv("NEO4J_URL",  "http://10.0.1.114:7474"))
    ip.add_argument("--neo4j-user", default=os.getenv("NEO4J_USER", "neo4j"))
    ip.add_argument("--neo4j-pass", default=os.getenv("NEO4J_PASSWORD", ""))
    ip.add_argument("--dry-run",    action="store_true")

    sp = sub.add_parser("fact-sheet", help="Print fact sheet for one supplier (Neo4j)")
    sp.add_argument("supplier")
    sp.add_argument("--neo4j-url",  default=os.getenv("NEO4J_URL",  "http://10.0.1.114:7474"))
    sp.add_argument("--neo4j-user", default=os.getenv("NEO4J_USER", "neo4j"))
    sp.add_argument("--neo4j-pass", default=os.getenv("NEO4J_PASSWORD", ""))

    args = p.parse_args()

    kc = KotaemonClient(
        base_url=os.getenv("KOTAEMON_URL", KOTAEMON_URL),
        password=os.getenv("KOTAEMON_PASSWORD", KOTAEMON_PASS),
    )

    if args.cmd == "health":
        ok = kc.health()
        print(f"Kotaemon {'ONLINE' if ok else 'OFFLINE'} ({kc.base})")
        sys.exit(0 if ok else 1)

    elif args.cmd == "query":
        question = " ".join(args.question)
        print(f"[Query] {question}")
        answer = kc.query(question, query_timeout=60)
        if answer:
            print(f"\n[Answer]\n{answer}")
        else:
            print("[No answer — Kotaemon offline or no matching documents]")

    elif args.cmd == "ingest-all":
        sheets = build_all_fact_sheets(args.neo4j_url, args.neo4j_user, args.neo4j_pass)
        print(f"Built {len(sheets)} fact sheets from Neo4j")
        if args.dry_run:
            for name, text in list(sheets.items())[:3]:
                print(f"\n─── {name} ───\n{text[:500]}...")
        else:
            if not kc.health():
                print("ERROR: Kotaemon offline — cannot ingest")
                sys.exit(1)
            results = kc.batch_ingest(sheets, delay_sec=2.0)
            ok = sum(v for v in results.values())
            print(f"Ingested {ok}/{len(results)} documents")

    elif args.cmd == "fact-sheet":
        sheets = build_all_fact_sheets(args.neo4j_url, args.neo4j_user, args.neo4j_pass)
        match = {k: v for k, v in sheets.items() if args.supplier.lower() in k.lower()}
        if not match:
            print(f"Supplier '{args.supplier}' not found")
            sys.exit(1)
        for name, text in match.items():
            print(f"\n{'='*60}\n{text}")
    else:
        p.print_help()


if __name__ == "__main__":
    main()
