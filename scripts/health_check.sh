#!/usr/bin/env bash
# UC4 Supply Chain — health check for all pipeline services
# Usage: bash usecases/uc4-supply-chain/scripts/health_check.sh
# Requires VPN active

set -uo pipefail

PASS=0
FAIL=0

check() {
    local name="$1" url="$2" expected="${3:-200}"
    code=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 5 "$url" 2>/dev/null || echo "000")
    if [[ "$code" == "$expected" ]]; then
        printf "%-32s OK    (%s)\n" "$name" "$code"
        ((PASS++))
    else
        printf "%-32s FAIL  (expected %s, got %s) %s\n" "$name" "$expected" "$code" "$url"
        ((FAIL++))
    fi
}

echo "UC4 Supply Chain — Health Check $(date '+%Y-%m-%d %H:%M:%S')"
echo "================================================================="

# Neo4j: HTTP browser on 7474 returns 200
check "Neo4j CT114 HTTP"              "http://10.0.1.114:7474/"             "200"

# LangGraph
check "LangGraph CT119"               "http://10.0.1.119:8000/health"       "200"

# Browserless: root returns 404, /health returns 200
check "Browserless CT400 /health"     "http://10.0.5.100:3500/health"       "200"
check "Browserless CT306 /health"     "http://10.0.3.106:3500/health"       "200"

# Unstructured
check "Unstructured CT117"            "http://10.0.1.117:8000/health"       "200"

# Tika
check "Tika CT115"                    "http://10.0.1.115:9998/tika"         "200"

# Qdrant
check "Qdrant CT102"                  "http://10.0.1.102:6333/healthz"      "200"

# LiteLLM
check "LiteLLM CT205"                 "http://10.0.2.205:4000/health"       "200"

# Superset
check "Superset CT206"                "http://10.0.2.206:8088/health"       "200"

# Metabase
check "Metabase CT202"                "http://10.0.2.202:3000/api/health"   "200"

# n8n
check "n8n CT104"                     "http://10.0.1.104:5678/healthz"      "200"

# Langfuse
check "Langfuse CT112"                "http://10.0.1.112:3000/api/public/health" "200"

echo "================================================================="
echo "Result: $PASS OK, $FAIL FAILED"

if [[ $FAIL -gt 0 ]]; then
    echo ""
    echo "Quick fixes:"
    echo "  Neo4j:        ssh -J root@10.0.0.16 root@10.0.1.114 'systemctl restart neo4j'"
    echo "  LangGraph:    ssh -J root@10.0.0.16 root@10.0.1.119 'systemctl restart langgraph'"
    echo "  Unstructured: ssh -J root@10.0.0.16 root@10.0.1.117 'systemctl restart unstructured'"
    echo "  Qdrant:       ssh -J root@10.0.0.16 root@10.0.1.102 'systemctl restart qdrant'"
    echo "  LiteLLM:      ssh -J root@10.0.0.15 root@10.0.2.205 'systemctl restart litellm'"
    echo "  Superset:     ssh -J root@10.0.0.15 root@10.0.2.206 'systemctl restart superset'"
    echo "  CT400 access: ssh -i ~/.ssh/proxmox_node3 root@10.0.0.18 'pct exec 400 -- systemctl restart browserless'"
    echo "  CT306 access: ssh -i ~/.ssh/proxmox_node3 -o 'ProxyCommand=ssh -i ~/.ssh/proxmox_node3 -W %h:%p root@10.0.0.17' root@10.0.3.106 'systemctl restart browserless'"
    echo ""
    echo "  See docs/recovery.md for detailed troubleshooting."
    exit 1
fi

exit 0
