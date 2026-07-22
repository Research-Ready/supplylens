#!/usr/bin/env bash
# UC4 Supply Chain — Seed Scania demo graph into Neo4j CT114
#
# Usage:
#   bash scripts/seed_scania.sh           # seed demo data
#   bash scripts/seed_scania.sh --clear   # clear demo nodes first, then re-seed
#
# Requires: VPN active, pykeepass (pip install pykeepass)

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CYPHER_FILE="${REPO_ROOT}/example_outputs/sample_graph.cypher"
BASTION="root@10.0.0.16"
NEO4J_CT="root@10.0.1.114"

if [[ ! -f "$CYPHER_FILE" ]]; then
    echo "ERROR: $CYPHER_FILE not found" >&2; exit 1
fi

# ---------------------------------------------------------------------------
# Credentials from KeePass
# ---------------------------------------------------------------------------
NEO4J_PW=$(python3 -c "
from pykeepass import PyKeePass
kp = PyKeePass('${REPO_ROOT}/passwords.kdbx', password='SupplyChainBaby100!')
e = kp.find_entries(title='Neo4j', first=True)
if not e:
    raise SystemExit('Neo4j entry not found in KeePass')
print(e.password)
")

# ---------------------------------------------------------------------------
# Optional: clear existing demo nodes
# ---------------------------------------------------------------------------
if [[ "${1:-}" == "--clear" ]]; then
    echo "Clearing demo nodes (WHERE n.demo = true)..."
    ssh -o StrictHostKeyChecking=accept-new \
        -o ProxyJump="$BASTION" "$NEO4J_CT" \
        "cypher-shell -u neo4j -p '${NEO4J_PW}' \
            'MATCH (n) WHERE n.demo = true DETACH DELETE n' 2>&1 && echo Cleared."
fi

# ---------------------------------------------------------------------------
# Upload and execute
# ---------------------------------------------------------------------------
echo "Uploading ${CYPHER_FILE##*/} to CT114..."
scp -q \
    -o StrictHostKeyChecking=accept-new \
    -o ProxyJump="$BASTION" \
    "$CYPHER_FILE" \
    "${NEO4J_CT}:/tmp/seed_scania.cypher"

echo "Running cypher-shell -f on CT114..."
ssh -o StrictHostKeyChecking=accept-new \
    -o ProxyJump="$BASTION" "$NEO4J_CT" \
    "cypher-shell -u neo4j -p '${NEO4J_PW}' -f /tmp/seed_scania.cypher 2>&1"

# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------
echo ""
echo "Verifying..."
RESULT=$(ssh -o StrictHostKeyChecking=accept-new \
    -o ProxyJump="$BASTION" "$NEO4J_CT" \
    "cypher-shell -u neo4j -p '${NEO4J_PW}' --format plain \
        'MATCH (n) WHERE n.demo = true RETURN count(n) AS nodes' 2>&1")

echo "$RESULT"
NODE_COUNT=$(echo "$RESULT" | grep -Eo '[0-9]+' | tail -1 || echo "0")

if [[ "${NODE_COUNT:-0}" -ge 10 ]]; then
    echo ""
    echo "Seed complete: ${NODE_COUNT} demo nodes in Neo4j CT114."
    echo "Run verification query:"
    echo "  MATCH path = (p:Product {sku:'SCANIA-R-500'})-[:SUPPLIED_BY|SOURCED_FROM*1..3]->(n)"
    echo "  RETURN [node IN nodes(path) | coalesce(node.name, node.sku)] AS chain, length(path) AS depth"
else
    echo "ERROR: expected >=10 demo nodes, got ${NODE_COUNT:-0}" >&2
    exit 1
fi
