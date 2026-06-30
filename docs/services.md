# UC4 Services Reference

## Service Status (as of 2026-06-30)

All 8 dry-run steps pass. See `CLAUDE.md` for dry-run procedure.

---

## Neo4j — CT114

| Property | Value |
|----------|-------|
| Container | CT114 (node-1, 10.0.0.16) |
| IP:Port | 10.0.1.114:7474 (HTTP API) / :7687 (Bolt) |
| User | `neo4j` |
| Password | KeePass UC4 → Neo4j / CT114 `/root/.credentials/neo4j.txt` |
| Systemd | `neo4j.service` |
| Data dir | `/var/lib/neo4j/data/` |

SSH: `ssh -o ProxyJump=root@10.0.0.16 root@10.0.1.114`

Health check:
```bash
ssh -o ProxyJump=root@10.0.0.16 root@10.0.1.114 "systemctl is-active neo4j"
# Expected: active
```

---

## LangGraph — CT119

| Property | Value |
|----------|-------|
| Container | CT119 (node-1) |
| IP:Port | 10.0.1.119:8000 |
| Auth | None |
| Systemd | `langgraph.service` |

Health: `curl -s -o /dev/null -w '%{http_code}' http://10.0.1.119:8000/health`
Expected: `200`

---

## Browserless (prod) — CT400

| Property | Value |
|----------|-------|
| Container | CT400 (node-4, 10.0.0.18) |
| IP:Port | 10.0.5.100:3500 |
| Auth | None (internal) |
| Endpoint | `POST /scrape` |
| SSH | CT400 has NO SSH keys — use `pct exec 400 --` on node-4 |

Access pattern:
```bash
ssh -i ~/.ssh/proxmox_node3 root@10.0.0.18 "pct exec 400 -- python3 -c 'import urllib.request; ...'"
```

Health: `curl -s -o /dev/null -w '%{http_code}' http://10.0.5.100:3500/health`
Expected: `200` (root `/` returns 404 — that is normal)

---

## Browserless (acc fallback) — CT306

| Property | Value |
|----------|-------|
| Container | CT306 (node-3, 10.0.0.17) |
| IP:Port | 10.0.3.106:3500 |
| Auth | None |

SSH (node-3 uses proxmox_node3 key with ProxyCommand):
```bash
ssh -i ~/.ssh/proxmox_node3 \
  -o "ProxyCommand=ssh -i ~/.ssh/proxmox_node3 -W %h:%p root@10.0.0.17" \
  root@10.0.3.106
```

---

## Unstructured — CT117

| Property | Value |
|----------|-------|
| Container | CT117 (node-1) |
| IP:Port | 10.0.1.117:8000 |
| Endpoint | `POST /general/v0/general` |
| Auth | None |
| CRITICAL | Must use `multipart/form-data` with `files` field |

Plain `text/html` body returns HTTP 422. Always use multipart:
```
Content-Type: multipart/form-data; boundary=...
body: --boundary\r\nContent-Disposition: form-data; name="files"; filename="doc.html"\r\n...
```

---

## Tika — CT115

| Property | Value |
|----------|-------|
| Container | CT115 (node-1) |
| IP:Port | 10.0.1.115:9998 |
| Endpoint | `PUT /tika` |
| Auth | None |

Health: `curl -s -o /dev/null -w '%{http_code}' http://10.0.1.115:9998/tika`
Expected: `200`

---

## Qdrant — CT102

| Property | Value |
|----------|-------|
| Container | CT102 (node-1) |
| IP:Port | 10.0.1.102:6333 |
| API Key | KeePass UC4 → Qdrant / CT102 `/etc/qdrant/config.yaml` `api_key` |
| Collection | `supplier_docs` |
| Embed model | `ollama/nomic-embed-text` (768 dims) via LiteLLM |

API key header: `api-key: <key>`
Health: `curl -s -o /dev/null -w '%{http_code}' http://10.0.1.102:6333/healthz`
Expected: `200`

---

## LiteLLM — CT205

| Property | Value |
|----------|-------|
| Container | CT205 (node-2, 10.0.0.15) |
| IP:Port | 10.0.2.205:4000 |
| Master key | KeePass UC4 → LiteLLM |
| Model for inference | `researcher-llm` → Groq `llama-3.3-70b-versatile` |
| Model for embeddings | `ollama/nomic-embed-text` (768 dims) |

Common issue: Groq API key gets box-drawing chars (`\xe2\x94\x80`) appended on line 230
of `/etc/litellm/config.yaml`. Remove and restart if `429` or `400` errors appear.

---

## Superset — CT206

| Property | Value |
|----------|-------|
| Container | CT206 (node-2) |
| IP:Port | 10.0.2.206:8088 |
| Admin user | `admin@research-ready.nl` |
| Admin password | KeePass UC4 → Superset |
| Systemd | `superset.service` |

Login issue fix: `systemctl restart superset` (clears PendingRollbackError on idle).

API token:
```bash
curl -s -X POST http://10.0.2.206:8088/api/v1/security/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"<pw>","provider":"db"}'
```

---

## Metabase — CT202

| Property | Value |
|----------|-------|
| Container | CT202 (node-2) |
| IP:Port | 10.0.2.202:3000 |
| Auth | Email + Password (KeePass main → Services → Metabase) |

---

## n8n — CT104

| Property | Value |
|----------|-------|
| Container | CT104 (node-1) |
| IP:Port | 10.0.1.104:5678 |
| Admin | `chris@research-ready.nl` |
| Password | KeePass main → Services → n8n |
| API key | `ssh root@10.0.1.104 "cat /root/.credentials/n8n.txt"` |

UC4 Cron trigger: every Monday 06:00 → full supply chain refresh.

---

## PostgreSQL knopenkonings — CT100

| Property | Value |
|----------|-------|
| Container | CT100 (node-1) |
| IP:Port | 10.0.1.100:5432 |
| User | `postgres` |
| Password | KeePass main vault → `postgres_password` |
| Database | `knopenkonings` |

Check DB exists: `ssh root@10.0.1.100 "psql -U postgres -l | grep knop"`
If missing: `ansible-playbook -i inventory/hosts.yml playbooks/05_platform.yml --tags postgres`

---

## Langfuse — CT112

| Property | Value |
|----------|-------|
| Container | CT112 (node-1) |
| IP:Port | 10.0.1.112:3000 |
| Keys | vault: `langfuse_public_key` + `langfuse_api_key` |

Used to trace all LiteLLM calls for cost monitoring and debugging inference failures.
