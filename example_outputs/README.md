# UC4 Example Outputs

This directory contains sample outputs from the UC4 supply chain pipeline.

## Files

- `sample_graph.cypher` — Neo4j Cypher statements to seed the full Scania/Knopenkoning supply chain demo graph.

## How to use sample_graph.cypher

```bash
# Get Neo4j password from UC4 KeePass
NEO4J_PW=$(python3 -c "
from pykeepass import PyKeePass
kp = PyKeePass('usecases/uc4-supply-chain/passwords.kdbx', password='SupplyChainBaby100!')
print(kp.find_entries(title='Neo4j', first=True).password)
")

# Copy cypher file to CT114 and run
scp -o ProxyJump=root@10.0.0.16 \
  usecases/uc4-supply-chain/example_outputs/sample_graph.cypher \
  root@10.0.1.114:/tmp/

ssh -o ProxyJump=root@10.0.0.16 root@10.0.1.114 "
  cypher-shell -u neo4j -p '$NEO4J_PW' --file /tmp/sample_graph.cypher
"

# Or paste directly into Neo4j Browser at http://10.0.1.114:7474
# Credentials: neo4j / (from KeePass UC4 -> Neo4j)
```

## Running Logs Format

Logs are stored in `../running_logs/` as JSON lines with this schema:
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
