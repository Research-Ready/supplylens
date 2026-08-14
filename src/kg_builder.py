"""
kg_builder.py — Kotaemon RAG → Neo4j knowledge graph pipeline

Queries Kotaemon for supplier documents, extracts entity-relationship
triples via LiteLLM, then MERGEs them into Neo4j.

Usage:
  python3 src/kg_builder.py --demo
  python3 src/kg_builder.py --supplier "ZF Friedrichshafen" --depth 2
  python3 src/kg_builder.py --all --dry-run
  python3 src/kg_builder.py --cypher-out /tmp/kg_triples.cypher
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

# ── Config ──────────────────────────────────────────────────────────────────

NEO4J_HTTP = "http://10.0.1.114:7474/db/neo4j/tx/commit"
LITELLM_URL = "http://10.0.2.205:4000/v1/chat/completions"
KOTAEMON_URL = "http://10.0.1.120:8501"

# Circuit breaker: if Kotaemon fails this many times consecutively, use demo
KOTAEMON_FAIL_LIMIT = 3
KOTAEMON_TIMEOUT = 20

# ── Data structures ──────────────────────────────────────────────────────────

@dataclass
class Triple:
    """A subject-predicate-object triple extracted from a document."""
    subject: str
    subject_type: str       # Supplier | RawMaterial | Company | Product | Certificate
    predicate: str          # SUPPLIED_BY | SOURCED_FROM | CERTIFIED_BY | OWNED_BY
    obj: str
    obj_type: str
    properties: dict = field(default_factory=dict)
    confidence: float = 0.8
    source: str = "kotaemon_rag"
    citation: str = ""


@dataclass
class KGBuildResult:
    supplier: str
    triples: list[Triple]
    cypher_statements: list[str]
    neo4j_merged: int
    errors: list[str]
    duration_s: float


# ── Demo data (offline mode) ─────────────────────────────────────────────────

DEMO_TRIPLES: dict[str, list[dict]] = {
    "ZF Friedrichshafen": [
        {"subject": "ZF Friedrichshafen", "subject_type": "Supplier",
         "predicate": "SOURCED_FROM", "obj": "Saarstahl AG", "obj_type": "Supplier",
         "properties": {"material": "steel billets", "volume_kt_year": 120},
         "confidence": 0.91, "citation": "[Source: ZF Annual Report 2023, p.47]"},
        {"subject": "ZF Friedrichshafen", "subject_type": "Supplier",
         "predicate": "SOURCED_FROM", "obj": "ThyssenKrupp Steel", "obj_type": "Supplier",
         "properties": {"material": "cold-rolled strip", "since": 2018},
         "confidence": 0.85, "citation": "[Source: ZF Sustainability Report 2023, p.12]"},
        {"subject": "ZF Friedrichshafen", "subject_type": "Supplier",
         "predicate": "CERTIFIED_BY", "obj": "ISO 9001:2015", "obj_type": "Certificate",
         "properties": {"issuer": "TÜV SÜD", "valid_until": "2026-12-31"},
         "confidence": 0.97, "citation": "[Source: ZF Supplier Portal, certification page]"},
        {"subject": "ZF Friedrichshafen", "subject_type": "Supplier",
         "predicate": "OWNED_BY", "obj": "ZF Group", "obj_type": "Company",
         "properties": {"ownership_pct": 100, "country": "Germany"},
         "confidence": 0.99, "citation": "[Source: ZF Annual Report 2023, p.3]"},
    ],
    "CATL": [
        {"subject": "CATL", "subject_type": "Supplier",
         "predicate": "SOURCED_FROM", "obj": "Glencore DRC", "obj_type": "Supplier",
         "properties": {"material": "cobalt", "volume_t_year": 5000},
         "confidence": 0.88, "citation": "[Source: CATL ESG Report 2023, p.31]"},
        {"subject": "CATL", "subject_type": "Supplier",
         "predicate": "SOURCED_FROM", "obj": "SQM Lithium", "obj_type": "Supplier",
         "properties": {"material": "lithium carbonate", "volume_t_year": 8000},
         "confidence": 0.82, "citation": "[Source: Bloomberg Supply Chain Database]"},
        {"subject": "CATL", "subject_type": "Supplier",
         "predicate": "CERTIFIED_BY", "obj": "IATF 16949", "obj_type": "Certificate",
         "properties": {"issuer": "Bureau Veritas", "valid_until": "2025-09-30"},
         "confidence": 0.94, "citation": "[Source: CATL Supplier Portal 2023]"},
        {"subject": "CATL", "subject_type": "Supplier",
         "predicate": "SOURCED_FROM", "obj": "Hunan Shanshan NMC", "obj_type": "Supplier",
         "properties": {"material": "NMC cathode active material", "volume_t_year": 15000},
         "confidence": 0.79, "citation": "[Source: Reuters commodity desk 2024-02]"},
    ],
    "TSMC": [
        {"subject": "TSMC", "subject_type": "Supplier",
         "predicate": "SOURCED_FROM", "obj": "JSR Corporation", "obj_type": "Supplier",
         "properties": {"material": "EUV photoresist", "sole_source": True},
         "confidence": 0.95, "citation": "[Source: TSMC Annual Report 2023, p.88]"},
        {"subject": "TSMC", "subject_type": "Supplier",
         "predicate": "SOURCED_FROM", "obj": "ASML", "obj_type": "Supplier",
         "properties": {"material": "EUV lithography machines", "units_year": 12},
         "confidence": 0.99, "citation": "[Source: ASML Annual Report 2023, p.15]"},
        {"subject": "TSMC", "subject_type": "Supplier",
         "predicate": "CERTIFIED_BY", "obj": "ISO 14001:2015", "obj_type": "Certificate",
         "properties": {"issuer": "SGS", "valid_until": "2025-06-30"},
         "confidence": 0.96, "citation": "[Source: TSMC CSR Report 2023, Appendix A]"},
        {"subject": "TSMC", "subject_type": "Supplier",
         "predicate": "SOURCED_FROM", "obj": "Cryoin Engineering", "obj_type": "Supplier",
         "properties": {"material": "neon gas", "origin": "Ukraine"},
         "confidence": 0.87, "citation": "[Source: Bloomberg Neon supply chain analysis 2022]"},
    ],
    "Bosch": [
        {"subject": "Bosch", "subject_type": "Supplier",
         "predicate": "SOURCED_FROM", "obj": "Infineon Technologies", "obj_type": "Supplier",
         "properties": {"material": "automotive MCUs", "sole_source": False},
         "confidence": 0.89, "citation": "[Source: Bosch Supplier Relations Report 2023, p.22]"},
        {"subject": "Bosch", "subject_type": "Supplier",
         "predicate": "SOURCED_FROM", "obj": "Sensata Technologies", "obj_type": "Supplier",
         "properties": {"material": "pressure sensors", "annual_units_m": 40},
         "confidence": 0.84, "citation": "[Source: Bosch Annual Report 2023, p.67]"},
        {"subject": "Bosch", "subject_type": "Supplier",
         "predicate": "CERTIFIED_BY", "obj": "IATF 16949", "obj_type": "Certificate",
         "properties": {"issuer": "DQS", "valid_until": "2026-03-31"},
         "confidence": 0.98, "citation": "[Source: Bosch Quality Portal]"},
    ],
    "SSAB": [
        {"subject": "SSAB", "subject_type": "Supplier",
         "predicate": "SOURCED_FROM", "obj": "LKAB", "obj_type": "Supplier",
         "properties": {"material": "iron ore pellets", "volume_mt_year": 2.1},
         "confidence": 0.97, "citation": "[Source: SSAB Sustainability Report 2023, p.18]"},
        {"subject": "SSAB", "subject_type": "Supplier",
         "predicate": "SOURCED_FROM", "obj": "H2 Green Steel", "obj_type": "Supplier",
         "properties": {"material": "green hydrogen DRI", "volume_mt_year": 0.5, "planned": True},
         "confidence": 0.75, "citation": "[Source: SSAB Press Release 2024-01-15]"},
        {"subject": "SSAB", "subject_type": "Supplier",
         "predicate": "CERTIFIED_BY", "obj": "SSAB Zero Carbon Certificate", "obj_type": "Certificate",
         "properties": {"issuer": "SSAB internal", "valid_until": "2030-12-31"},
         "confidence": 0.91, "citation": "[Source: SSAB HYBRIT project documentation]"},
    ],
}

KNOWN_SUPPLIERS = list(DEMO_TRIPLES.keys()) + [
    "Norilsk Nickel", "Luminar Technologies", "Leoni AG",
    "JSR Corporation", "Mobileye", "Dana Incorporated",
]

# ── Kotaemon client ──────────────────────────────────────────────────────────

class KotaemonClient:
    """Thin client for Kotaemon Gradio API.  Falls back to demo on failure."""

    def __init__(self, base_url: str = KOTAEMON_URL,
                 fail_limit: int = KOTAEMON_FAIL_LIMIT,
                 timeout: int = KOTAEMON_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.fail_limit = fail_limit
        self.timeout = timeout
        self._failures = 0
        self._open = True

    def _trip(self, err: str) -> None:
        self._failures += 1
        if self._failures >= self.fail_limit:
            self._open = False

    def health(self) -> bool:
        try:
            req = urllib.request.Request(
                f"{self.base_url}/",
                headers={"User-Agent": "kg-builder/1.0"},
            )
            r = urllib.request.urlopen(req, timeout=5)
            return r.status < 500
        except Exception:
            return False

    def query(self, question: str, collection: str = "supplier_docs") -> Optional[str]:
        """Send a RAG query to Kotaemon.  Returns answer text or None."""
        if not self._open:
            return None
        payload = {
            "fn_index": 0,
            "data": [question, collection],
            "session_hash": "kg_builder",
        }
        try:
            req = urllib.request.Request(
                f"{self.base_url}/run/predict",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            r = urllib.request.urlopen(req, timeout=self.timeout)
            d = json.loads(r.read())
            answer = d.get("data", [None])[0]
            self._failures = 0  # reset on success
            return answer
        except Exception as exc:
            self._trip(str(exc))
            return None

    def extract_citations(self, answer: str) -> list[str]:
        """Parse [Source: doc, p.N] patterns from RAG answer."""
        import re
        return re.findall(r'\[Source:[^\]]+\]', answer or "")


# ── LLM triple extractor ─────────────────────────────────────────────────────

TRIPLE_EXTRACTION_PROMPT = """You are a supply chain knowledge graph extractor.

Given the following text about a supplier, extract entity-relationship triples.

Output ONLY a JSON array of triples. Each triple must have:
- subject: entity name (string)
- subject_type: one of [Supplier, RawMaterial, Company, Product, Certificate]
- predicate: one of [SUPPLIED_BY, SOURCED_FROM, CERTIFIED_BY, OWNED_BY, SUBSIDIARY_OF]
- obj: target entity name (string)
- obj_type: one of [Supplier, RawMaterial, Company, Product, Certificate]
- properties: dict of extra facts (material, volume, year, country, etc.)
- confidence: 0.0–1.0

Text about {supplier}:
{text}

JSON array:"""


def extract_triples_llm(
    supplier: str,
    text: str,
    litellm_url: str,
    litellm_key: str,
    model: str = "researcher-llm",
    timeout: int = 30,
) -> list[Triple]:
    """Call LiteLLM to extract triples from RAG answer text."""
    prompt = TRIPLE_EXTRACTION_PROMPT.format(supplier=supplier, text=text)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 800,
        "temperature": 0.0,
    }
    try:
        req = urllib.request.Request(
            litellm_url,
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {litellm_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        r = urllib.request.urlopen(req, timeout=timeout)
        d = json.loads(r.read())
        content = d["choices"][0]["message"]["content"]
        # Strip markdown fences if present
        import re
        content = re.sub(r"```[a-z]*\n?", "", content).strip()
        raw = json.loads(content)
        triples = []
        for item in raw:
            triples.append(Triple(
                subject=item["subject"],
                subject_type=item.get("subject_type", "Supplier"),
                predicate=item["predicate"],
                obj=item["obj"],
                obj_type=item.get("obj_type", "Supplier"),
                properties=item.get("properties", {}),
                confidence=float(item.get("confidence", 0.8)),
                source="litellm_extract",
            ))
        return triples
    except Exception as exc:
        sys.stderr.write(f"LLM extract failed for {supplier}: {exc}\n")
        return []


# ── Cypher generator ─────────────────────────────────────────────────────────

NODE_LABELS = {
    "Supplier": "Supplier",
    "RawMaterial": "RawMaterial",
    "Company": "Company",
    "Product": "Product",
    "Certificate": "Certificate",
}

def _escape(s: str) -> str:
    return s.replace('"', '\\"').replace("'", "\\'")

def _props_cypher(props: dict, extra: dict = None) -> str:
    merged = {**(extra or {}), **props}
    if not merged:
        return ""
    parts = []
    for k, v in merged.items():
        if isinstance(v, str):
            parts.append(f'{k}: "{_escape(v)}"')
        elif isinstance(v, bool):
            parts.append(f"{k}: {'true' if v else 'false'}")
        else:
            parts.append(f"{k}: {v}")
    return "{" + ", ".join(parts) + "}"


def triples_to_cypher(triples: list[Triple]) -> list[str]:
    stmts = []
    for t in triples:
        s_label = NODE_LABELS.get(t.subject_type, "Supplier")
        o_label = NODE_LABELS.get(t.obj_type, "Supplier")
        s_name = _escape(t.subject)
        o_name = _escape(t.obj)

        # MERGE subject node
        stmts.append(f'MERGE (s:{s_label} {{name: "{s_name}"}})')
        # MERGE object node
        stmts.append(f'MERGE (o:{o_label} {{name: "{o_name}"}})')

        # Relationship properties
        rel_props = {
            "confidence": t.confidence,
            "source": t.source,
        }
        if t.citation:
            rel_props["citation"] = t.citation
        rel_props.update(t.properties)
        rel_props_str = _props_cypher(rel_props)

        rel_stmt = (
            f'MATCH (s:{s_label} {{name: "{s_name}"}}), (o:{o_label} {{name: "{o_name}"}}) '
            f'MERGE (s)-[r:{t.predicate}]->(o) '
            f'SET r += {rel_props_str}'
        )
        stmts.append(rel_stmt)

    return stmts


# ── Neo4j writer ─────────────────────────────────────────────────────────────

def neo4j_run(statements: list[str], neo4j_pw: str,
              base_url: str = NEO4J_HTTP) -> tuple[int, list[str]]:
    """Execute Cypher statements via Neo4j HTTP API. Returns (merged_count, errors)."""
    import base64
    auth = base64.b64encode(f"neo4j:{neo4j_pw}".encode()).decode()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {auth}",
    }
    payload = {"statements": [{"statement": s} for s in statements]}
    try:
        req = urllib.request.Request(
            base_url,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        r = urllib.request.urlopen(req, timeout=30)
        d = json.loads(r.read())
        errors = [str(e) for e in d.get("errors", [])]
        merged = sum(
            res.get("stats", {}).get("nodes-created", 0) +
            res.get("stats", {}).get("relationships-created", 0)
            for res in d.get("results", [])
        )
        return merged, errors
    except Exception as exc:
        return 0, [str(exc)]


# ── Core pipeline ─────────────────────────────────────────────────────────────

def build_for_supplier(
    supplier: str,
    kotaemon: KotaemonClient,
    litellm_url: str,
    litellm_key: str,
    neo4j_pw: Optional[str],
    dry_run: bool = False,
    demo_mode: bool = False,
) -> KGBuildResult:
    t0 = time.time()
    errors = []
    all_triples: list[Triple] = []

    if demo_mode or not kotaemon.health():
        # Use embedded demo triples
        raw = DEMO_TRIPLES.get(supplier, [])
        for item in raw:
            all_triples.append(Triple(**item))
        if not demo_mode:
            errors.append("Kotaemon offline — using demo triples")
    else:
        # Query Kotaemon with several angles
        queries = [
            f"What raw materials does {supplier} source and from which countries?",
            f"What certifications does {supplier} hold? List standards and issuers.",
            f"Who owns {supplier} and what is its corporate structure?",
            f"What are the key logistics risks in {supplier}'s supply chain?",
        ]
        combined_text = ""
        citations = []
        for q in queries:
            answer = kotaemon.query(q)
            if answer:
                combined_text += f"\n\n{answer}"
                citations.extend(kotaemon.extract_citations(answer))

        if combined_text.strip():
            triples = extract_triples_llm(
                supplier, combined_text,
                litellm_url, litellm_key,
            )
            # Tag citations
            for i, t in enumerate(triples):
                if i < len(citations):
                    t.citation = citations[i]
            all_triples.extend(triples)
        else:
            errors.append("No text retrieved from Kotaemon")

    cypher = triples_to_cypher(all_triples)
    merged = 0

    if not dry_run and neo4j_pw and cypher:
        merged, neo4j_errors = neo4j_run(cypher, neo4j_pw)
        errors.extend(neo4j_errors)

    return KGBuildResult(
        supplier=supplier,
        triples=all_triples,
        cypher_statements=cypher,
        neo4j_merged=merged,
        errors=errors,
        duration_s=time.time() - t0,
    )


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Kotaemon RAG → Neo4j KG builder")
    ap.add_argument("--supplier", help="Single supplier name to process")
    ap.add_argument("--all", action="store_true", help="Process all known suppliers")
    ap.add_argument("--demo", action="store_true", help="Demo mode — use embedded data, skip network")
    ap.add_argument("--dry-run", action="store_true", help="Generate Cypher but skip Neo4j write")
    ap.add_argument("--cypher-out", help="Write Cypher statements to file")
    ap.add_argument("--json", action="store_true", help="Output JSON summary")
    ap.add_argument("--litellm-key", default="sk-0xi1O45reIhzSzwWt90tvdX6")
    ap.add_argument("--neo4j-pw", default=None)
    ap.add_argument("--kotaemon-url", default=KOTAEMON_URL)
    ap.add_argument("--litellm-url", default=LITELLM_URL)
    args = ap.parse_args()

    if not args.supplier and not args.all and not args.demo:
        ap.print_help()
        sys.exit(1)

    kotaemon = KotaemonClient(base_url=args.kotaemon_url)

    if args.demo:
        targets = list(DEMO_TRIPLES.keys())
    elif args.all:
        targets = KNOWN_SUPPLIERS
    else:
        targets = [args.supplier]

    all_cypher = []
    results = []
    exit_code = 0

    for supplier in targets:
        result = build_for_supplier(
            supplier=supplier,
            kotaemon=kotaemon,
            litellm_url=args.litellm_url,
            litellm_key=args.litellm_key,
            neo4j_pw=args.neo4j_pw,
            dry_run=args.dry_run or not args.neo4j_pw,
            demo_mode=args.demo,
        )
        results.append(result)
        all_cypher.extend(result.cypher_statements)

        if not args.json:
            status = "OK" if not result.errors else f"WARN({len(result.errors)})"
            print(f"[{status}] {supplier}: {len(result.triples)} triples, "
                  f"{result.neo4j_merged} merged, {result.duration_s:.1f}s")
            for t in result.triples:
                print(f"  {t.subject} -[{t.predicate}]-> {t.obj} "
                      f"(conf={t.confidence:.2f})")
            for err in result.errors:
                print(f"  ! {err}", file=sys.stderr)

        if result.errors:
            exit_code = max(exit_code, 1)

    if args.cypher_out:
        with open(args.cypher_out, "w") as f:
            f.write("// Generated by kg_builder.py\n")
            for stmt in all_cypher:
                f.write(stmt + ";\n")
        if not args.json:
            print(f"\nCypher written: {args.cypher_out} ({len(all_cypher)} statements)")

    if args.json:
        out = []
        for r in results:
            out.append({
                "supplier": r.supplier,
                "triples": len(r.triples),
                "neo4j_merged": r.neo4j_merged,
                "errors": r.errors,
                "duration_s": round(r.duration_s, 2),
                "cypher_count": len(r.cypher_statements),
            })
        print(json.dumps(out, indent=2))

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
