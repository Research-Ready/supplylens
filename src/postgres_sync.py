"""
UC4 Supply Chain — Sync Neo4j Supplier nodes → PostgreSQL knopenkonings.suppliers

Run from local machine (VPN active) or from CT100:
  python3 src/postgres_sync.py
  python3 src/postgres_sync.py --dry-run

Credentials from environment (copy .env.example → .env and fill in values):
  export $(grep -v '^#' .env | xargs) && python3 src/postgres_sync.py
"""
import base64
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    sys.exit("ERROR: pip install psycopg2-binary")

NEO4J_URL  = os.getenv("NEO4J_URL",      "http://10.0.1.114:7474")
NEO4J_USER = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "")
PG_HOST    = os.getenv("PG_HOST",        "10.0.1.100")
PG_PORT    = int(os.getenv("PG_PORT",    "5432"))
PG_USER    = os.getenv("PG_USER",        "postgres")
PG_PASS    = os.getenv("PG_PASSWORD",    "")
PG_DB      = os.getenv("PG_DATABASE",    "knopenkonings")

DDL = """
CREATE TABLE IF NOT EXISTS suppliers (
    id              SERIAL PRIMARY KEY,
    name            TEXT        NOT NULL,
    country         CHAR(2),
    tier            INTEGER,
    website         TEXT,
    risk_flags      TEXT[],
    inferred        BOOLEAN     NOT NULL DEFAULT false,
    confidence      FLOAT,
    source          TEXT,
    neo4j_sync_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT suppliers_name_uniq UNIQUE (name)
);
CREATE INDEX IF NOT EXISTS suppliers_country_idx ON suppliers (country);
CREATE INDEX IF NOT EXISTS suppliers_tier_idx    ON suppliers (tier);
"""

UPSERT_SQL = """
INSERT INTO suppliers
    (name, country, tier, website, risk_flags, inferred, confidence, source, neo4j_sync_at)
VALUES
    (%(name)s, %(country)s, %(tier)s, %(website)s,
     %(risk_flags)s, %(inferred)s, %(confidence)s, %(source)s, %(sync_at)s)
ON CONFLICT (name) DO UPDATE SET
    country       = EXCLUDED.country,
    tier          = EXCLUDED.tier,
    website       = EXCLUDED.website,
    risk_flags    = EXCLUDED.risk_flags,
    inferred      = EXCLUDED.inferred,
    confidence    = EXCLUDED.confidence,
    source        = EXCLUDED.source,
    neo4j_sync_at = EXCLUDED.neo4j_sync_at;
"""


def neo4j_fetch() -> list[dict]:
    """Fetch all Supplier nodes from Neo4j via HTTP API."""
    auth = "Basic " + base64.b64encode(f"{NEO4J_USER}:{NEO4J_PASS}".encode()).decode()
    query = """
    MATCH (s:Supplier)
    OPTIONAL MATCH (s)-[rel:SOURCED_FROM]->()
    RETURN DISTINCT
        s.name       AS name,
        s.country    AS country,
        s.tier       AS tier,
        s.website    AS website,
        s.risk_flags AS risk_flags,
        s.inferred   AS inferred,
        rel.confidence AS confidence,
        rel.source     AS source
    ORDER BY s.tier NULLS LAST, s.name
    """
    payload = {"statements": [{"statement": query}]}
    req = urllib.request.Request(
        NEO4J_URL.rstrip("/") + "/db/neo4j/tx/commit",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": auth},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    if data.get("errors"):
        raise RuntimeError(f"Neo4j: {data['errors']}")
    cols = data["results"][0]["columns"]
    return [dict(zip(cols, row["row"])) for row in data["results"][0]["data"]]


def sync(dry_run: bool = False) -> None:
    print(f"Neo4j: {NEO4J_URL}")
    rows = neo4j_fetch()
    print(f"Found {len(rows)} supplier nodes")

    if not rows:
        print("Nothing to sync.")
        return

    if dry_run:
        print("\nDry run — rows that would be upserted:")
        for r in rows:
            flags = ",".join(r.get("risk_flags") or []) or "-"
            print(
                f"  [T{r.get('tier', '?')}] {r['name']}"
                f" ({r.get('country', '??')}) flags={flags}"
                f" inferred={r.get('inferred', False)}"
            )
        return

    print(f"\nConnecting to PostgreSQL {PG_HOST}/{PG_DB}...")
    conn = psycopg2.connect(
        host=PG_HOST, port=PG_PORT,
        user=PG_USER, password=PG_PASS,
        dbname=PG_DB,
    )
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(DDL)
                print("Schema ensured.")

        sync_at = datetime.now(timezone.utc)
        upserted = 0
        with conn:
            with conn.cursor() as cur:
                for row in rows:
                    country = (row.get("country") or "XX")
                    cur.execute(UPSERT_SQL, {
                        "name":       row.get("name") or "",
                        "country":    country[:2].upper(),
                        "tier":       row.get("tier"),
                        "website":    row.get("website"),
                        "risk_flags": row.get("risk_flags") or [],
                        "inferred":   bool(row.get("inferred")),
                        "confidence": row.get("confidence"),
                        "source":     row.get("source"),
                        "sync_at":    sync_at,
                    })
                    upserted += 1
        print(f"Synced {upserted} rows → {PG_DB}.suppliers")
    finally:
        conn.close()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    sync(dry_run=dry_run)
