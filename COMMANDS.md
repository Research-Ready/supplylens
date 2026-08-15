# SupplyLens — Quick Commands

## SSH Tunnels (run on laptop before opening any UI)

```bash
# Neo4j — HTTP + Bolt (run this first, always)
ssh -f -L 17474:localhost:7474 -L 17687:localhost:7687 -N -o ProxyJump=root@10.0.0.16 root@10.0.1.114
```

## Open UIs in browser

```bash
# Neo4j Browser
xdg-open "http://localhost:17474/browser/?dbms=bolt://localhost:17687&db=neo4j"

# Superset
xdg-open "http://10.0.2.206:8088"

# Metabase
xdg-open "http://10.0.2.202:3000"

# Kotaemon (RAG)
xdg-open "http://10.0.1.120:8501"

# n8n
xdg-open "http://10.0.1.104:5678"

# LangGraph
xdg-open "http://10.0.1.119:8000"

# SupplyLens dashboard (local)
xdg-open "/home/chris/Nextcloud/Github/uc4-supply-chain/docs/dashboard.html"
```

## Neo4j credentials

- URL: `bolt://localhost:17687`
- Username: `neo4j`
- Password: `jGFrfiNAuwW8YPsZXIofcNwb`

## Neo4j Browser — useful Cypher queries

```cypher
-- See everything (first 50 nodes)
MATCH (n) RETURN n LIMIT 50

-- Full Scania supply chain graph
MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 200

-- All suppliers
MATCH (s:Supplier) RETURN s ORDER BY s.tier

-- All risk flags
MATCH (n) WHERE n.risk_flags IS NOT NULL RETURN n.name, n.risk_flags

-- Supply chain from Scania downward
MATCH path = (p:Product)-[:SUPPLIED_BY|SOURCED_FROM*1..5]->(n)
RETURN path LIMIT 100

-- All events / incidents
MATCH (e:Event) RETURN e ORDER BY e.date DESC

-- Nodes with evidence
MATCH (n) WHERE n.source_doc IS NOT NULL RETURN n.name, n.source_doc, n.confidence
```

## Git

```bash
# Check status
git status

# Commit and push everything
git add -A && git commit -m "your message" && git push origin main
```

## Service health check

```bash
for svc in \
  "10.0.1.114:7474/ neo4j" \
  "10.0.1.102:6333/healthz qdrant" \
  "10.0.5.100:3500/ browserless" \
  "10.0.1.117:8000/health unstructured" \
  "10.0.1.119:8000/health langgraph" \
  "10.0.2.206:8088/ superset" \
  "10.0.2.202:3000/ metabase"; do
  addr="${svc%% *}"; name="${svc##* }"
  code=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 3 "http://$addr" 2>/dev/null)
  printf "%-20s %s\n" "$name" "${code:-DEAD}"
done
```
