"""Neo4j HTTP API client — UC4 Supply Chain (stdlib only, no external deps)."""
import base64
import json
import urllib.request
from typing import Any


class Neo4jClient:
    def __init__(self, url: str, user: str, password: str) -> None:
        creds = base64.b64encode(f"{user}:{password}".encode()).decode()
        self._auth = "Basic " + creds
        self._url = url.rstrip("/") + "/db/neo4j/tx/commit"

    def _request(self, statements: list[dict]) -> list[dict]:
        payload = {"statements": statements}
        req = urllib.request.Request(
            self._url,
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": self._auth,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        if data.get("errors"):
            raise RuntimeError(f"Neo4j error: {data['errors']}")
        return data["results"]

    def run(self, query: str, params: dict[str, Any] | None = None) -> list[dict]:
        """Run a single Cypher query and return rows as dicts."""
        results = self._request([{"statement": query, "parameters": params or {}}])
        cols = results[0]["columns"]
        return [dict(zip(cols, row["row"])) for row in results[0]["data"]]

    def run_batch(self, queries: list[str]) -> None:
        """Execute multiple Cypher statements in one transaction (no return values)."""
        self._request([{"statement": q} for q in queries])
