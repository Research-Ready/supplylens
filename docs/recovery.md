# UC4 Recovery Playbook

## Quick Diagnosis

```bash
# Run full health check first
bash usecases/uc4-supply-chain/scripts/health_check.sh
```

---

## Service-Specific Fixes

### Neo4j auth 401

Symptom: `curl: (401) Unauthorized` on port 7474.

Fix:
```bash
# Read actual password from container
ssh -o ProxyJump=root@10.0.0.16 root@10.0.1.114 "cat /root/.credentials/neo4j.txt"
# Verify with:
NEO4J_PW=<password>
AUTH=$(python3 -c "import base64; print(base64.b64encode(f'neo4j:$NEO4J_PW'.encode()).decode())")
curl -s -H "Authorization: Basic $AUTH" http://localhost:7474/db/neo4j/tx/commit \
  -H 'Content-Type: application/json' \
  -d '{"statements":[{"statement":"RETURN 1"}]}'
```

### Neo4j OOM / traversal hangs

Symptom: query times out, `java.lang.OutOfMemoryError` in logs.

Fix:
```bash
# Limit depth to 3 (not 5)
# Change: -[:SUPPLIED_BY|SOURCED_FROM*1..5]->
# To:     -[:SUPPLIED_BY|SOURCED_FROM*1..3]->

# Restart Neo4j
ssh -o ProxyJump=root@10.0.0.16 root@10.0.1.114 "systemctl restart neo4j"
```

### Browserless 404 on POST

Symptom: `curl: (404)` when posting to `/chromium/content` or `/api/screenshot`.

Fix: Use the correct endpoint — this is a custom Playwright server.
- Scraping: `POST /scrape` (body: `{"url": "...", "wait_for": 1000}`)
- PDF: `POST /pdf`
- Screenshot: `POST /screenshot`
- Health: `GET /health`

### CT400 SSH denied (publickey)

Symptom: `ssh root@10.0.5.100` returns `Permission denied (publickey)`.

Fix: CT400 has no SSH keys configured. Use `pct exec` on node-4:
```bash
ssh -i ~/.ssh/proxmox_node3 root@10.0.0.18 "pct exec 400 -- curl http://localhost:3500/health"
```

### Unstructured HTTP 422

Symptom: `422 Unprocessable Entity` when posting to `/general/v0/general`.

Fix: Must use `multipart/form-data` with a `files` field. Example:
```python
import requests
with open('doc.html', 'rb') as f:
    r = requests.post('http://10.0.1.117:8000/general/v0/general',
                      files={'files': ('doc.html', f, 'text/html')})
```
Plain `text/html` body without multipart returns 422 unconditionally.

### Qdrant 403 Forbidden

Symptom: `403` on any Qdrant API call.

Fix: Include API key header in all requests:
```bash
QDRANT_KEY=$(python3 -c "
from pykeepass import PyKeePass
kp = PyKeePass('usecases/uc4-supply-chain/passwords.kdbx', password='SupplyChainBaby100!')
print(kp.find_entries(title='Qdrant', first=True).password)
")
curl -H "api-key: $QDRANT_KEY" http://localhost:6333/collections
```

### LiteLLM 429 / corrupt Groq key

Symptom: `429 Too Many Requests` or `400 invalid_api_key` from `researcher-llm`.

Fix: Box-drawing characters appended to Groq key in config:
```bash
ssh -o ProxyJump=root@10.0.0.15 root@10.0.2.205 "
  # Find the corrupt line (should contain only gsk_...)
  grep -n 'gsk_' /etc/litellm/config.yaml
  # Remove non-ASCII chars from that line
  sed -i 's/\xE2\x94\x80//g' /etc/litellm/config.yaml
  systemctl restart litellm
"
```

### LiteLLM embedding model not found

Symptom: `model not found: text-embedding-3-small`.

Fix: Use `ollama/nomic-embed-text` — that is the only embedding model configured:
```python
{"model": "ollama/nomic-embed-text", "input": "your text here"}
# Returns 768-dimensional vector
```

### Superset 401 / 500 on login

Symptom: Login returns 401 even with correct password, or 500 Internal Server Error.

Fix: SQLAlchemy PendingRollbackError after idle connection:
```bash
ssh -o ProxyJump=root@10.0.0.15 root@10.0.2.206 "systemctl restart superset"
# Wait ~10 seconds for startup, then retry login
```

### Superset admin password wrong

The admin password is in KeePass under `superset_ui_password` (NOT `superset_secret_key`).
`superset_secret_key` is the Flask app signing key, not the UI login password.

### LangGraph not responding

```bash
ssh -o ProxyJump=root@10.0.0.16 root@10.0.1.119 "systemctl status langgraph && journalctl -u langgraph -n 30"
```

### knopenkonings database missing

```bash
# Check
ssh -o ProxyJump=root@10.0.0.16 root@10.0.1.100 "psql -U postgres -l | grep knop"
# Create
ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/05_platform.yml --tags postgres
```

### Cross-node routing fails (CT400 unreachable from CT114)

Symptom: `curl: (000) connection refused` when CT114 tries to reach CT400 (10.0.5.100).

Fix: Check ip_forward on node-1:
```bash
ssh ProxmoxTest "sysctl net.ipv4.ip_forward"
# If 0: sysctl -w net.ipv4.ip_forward=1
# Persist: /etc/sysctl.d/99-proxmox.conf
```

---

## Full Stack Restart Order

If everything is down, restart in this order:

1. PostgreSQL (CT100) — other services depend on it
2. Neo4j (CT114)
3. Qdrant (CT102)
4. Unstructured (CT117), Tika (CT115)
5. LiteLLM (CT205)
6. LangGraph (CT119)
7. Browserless CT400, CT306
8. Superset (CT206), Metabase (CT202)
9. n8n (CT104)

```bash
for ct_ip in \
  "root@10.0.1.100:postgresql" \
  "root@10.0.1.114:neo4j" \
  "root@10.0.1.102:qdrant" \
  "root@10.0.1.117:unstructured" \
  "root@10.0.1.115:tika" \
  "root@10.0.2.205:litellm" \
  "root@10.0.1.119:langgraph" \
  "root@10.0.2.206:superset"; do
  host="${ct_ip%%:*}"
  svc="${ct_ip##*:}"
  echo "Restarting $svc on $host..."
  # Use appropriate ProxyJump per node
done
```
