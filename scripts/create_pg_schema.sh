#!/usr/bin/env bash
# UC4 Supply Chain — Create knopenkonings PostgreSQL schema on CT100
#
# Creates database, tables, and indexes for structured supplier data.
# Mirrors the Neo4j supply chain graph into queryable SQL tables.
#
# Usage:
#   bash scripts/create_pg_schema.sh
#   bash scripts/create_pg_schema.sh --drop-first   # drop + recreate
#
# Requirements:
#   - SSH access to root@10.0.1.100 (via bastion root@10.0.0.16)
#   - postgres_password in ansible/inventory/group_vars/vault.yml
#     OR KeePass passwords.kdbx (master: SupplyChainBaby100!)

set -euo pipefail

PG_HOST="10.0.1.100"
PG_USER="postgres"
DB_NAME="knopenkonings"
DROP_FIRST="${1:-}"

PROXMOX_NODE="root@10.0.0.16"

echo "╔══════════════════════════════════════════════════════╗"
echo "║  UC4 — Create knopenkonings PostgreSQL schema        ║"
echo "╚══════════════════════════════════════════════════════╝"

# ── Get PG password ────────────────────────────────────────────────────────────
VAULT="ansible/inventory/group_vars/vault.yml"
if [[ -f "$VAULT" ]]; then
  PG_PW=$(grep "^postgres_password" "$VAULT" | awk '{print $2}' | tr -d '"')
else
  echo "[WARN] vault.yml not found locally — reading from CT100"
  PG_PW=$(ssh -o ProxyJump="$PROXMOX_NODE" root@"$PG_HOST" \
    "cat /root/.credentials/postgres.txt 2>/dev/null || echo ''" 2>/dev/null || echo "")
fi

if [[ -z "$PG_PW" ]]; then
  echo -n "PostgreSQL password: "
  read -r -s PG_PW
  echo
fi

echo "Connecting to CT100 ($PG_HOST) via bastion ($PROXMOX_NODE)..."

# ── SSH wrapper to run psql ────────────────────────────────────────────────────
run_psql() {
  ssh -o ProxyJump="$PROXMOX_NODE" root@"$PG_HOST" \
    "PGPASSWORD='$PG_PW' psql -U $PG_USER -c \"$1\" 2>&1" || true
}

run_psql_db() {
  local db="$1"; shift
  ssh -o ProxyJump="$PROXMOX_NODE" root@"$PG_HOST" \
    "PGPASSWORD='$PG_PW' psql -U $PG_USER -d $db -c \"$1\" 2>&1" || true
}

run_psql_file() {
  local db="$1"; local sql="$2"
  ssh -o ProxyJump="$PROXMOX_NODE" root@"$PG_HOST" \
    "PGPASSWORD='$PG_PW' psql -U $PG_USER -d $db" <<< "$sql"
}

# ── Create database ────────────────────────────────────────────────────────────
echo
echo "[1/4] Creating database '$DB_NAME'..."
DB_EXISTS=$(ssh -o ProxyJump="$PROXMOX_NODE" root@"$PG_HOST" \
  "PGPASSWORD='$PG_PW' psql -U $PG_USER -tAc \"SELECT 1 FROM pg_database WHERE datname='$DB_NAME'\"" 2>/dev/null || echo "")

if [[ "$DB_EXISTS" == "1" ]]; then
  if [[ "$DROP_FIRST" == "--drop-first" ]]; then
    echo "  Dropping existing database..."
    run_psql "DROP DATABASE $DB_NAME;"
    run_psql "CREATE DATABASE $DB_NAME OWNER $PG_USER ENCODING 'UTF8';"
    echo "  Database recreated."
  else
    echo "  Database '$DB_NAME' already exists — skipping create."
  fi
else
  run_psql "CREATE DATABASE $DB_NAME OWNER $PG_USER ENCODING 'UTF8';"
  echo "  Database created."
fi

# ── Create schema + tables ────────────────────────────────────────────────────
echo
echo "[2/4] Creating tables..."

run_psql_file "$DB_NAME" "
-- ============================================================
-- UC4 knopenkonings supply chain schema
-- ============================================================

-- Suppliers table (mirrors Neo4j Supplier nodes)
CREATE TABLE IF NOT EXISTS suppliers (
    id              SERIAL PRIMARY KEY,
    neo4j_id        BIGINT UNIQUE,
    name            TEXT NOT NULL,
    country         CHAR(2),
    tier            INT CHECK (tier BETWEEN 1 AND 5),
    website         TEXT,
    industry        TEXT,
    risk_score      FLOAT CHECK (risk_score >= 0 AND risk_score <= 1),
    risk_summary    TEXT,                   -- comma-sep risk flags
    risk_level      TEXT CHECK (risk_level IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    annual_revenue_eur BIGINT,
    employee_count     INT,
    founded_year       INT,
    certifications     TEXT[],             -- ISO 9001, IATF, REACH, etc.
    inferred        BOOL DEFAULT FALSE,
    demo            BOOL DEFAULT FALSE,
    last_synced_at  TIMESTAMPTZ DEFAULT now(),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Products table (mirrors Neo4j Product nodes)
CREATE TABLE IF NOT EXISTS products (
    id              SERIAL PRIMARY KEY,
    neo4j_id        BIGINT UNIQUE,
    sku             TEXT UNIQUE NOT NULL,
    name            TEXT NOT NULL,
    category        TEXT,
    manufacturer    TEXT,
    annual_revenue_eur BIGINT,
    demo            BOOL DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Supply relationships (mirrors SUPPLIED_BY / SOURCED_FROM edges)
CREATE TABLE IF NOT EXISTS supply_relationships (
    id              SERIAL PRIMARY KEY,
    customer_name   TEXT NOT NULL,
    supplier_name   TEXT NOT NULL,
    relationship    TEXT NOT NULL CHECK (relationship IN ('SUPPLIED_BY','SOURCED_FROM')),
    component       TEXT,
    since_date      DATE,
    contract_value_eur BIGINT,
    volume_kg_year  BIGINT,
    lead_time_days  INT,
    single_source   BOOL DEFAULT FALSE,
    inferred        BOOL DEFAULT FALSE,
    confidence      FLOAT,
    demo            BOOL DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Raw materials (mirrors Neo4j RawMaterial nodes)
CREATE TABLE IF NOT EXISTS raw_materials (
    id              SERIAL PRIMARY KEY,
    neo4j_id        BIGINT UNIQUE,
    name            TEXT NOT NULL,
    origin_country  CHAR(2),
    material_type   TEXT,
    risk_flags      TEXT[],
    inferred        BOOL DEFAULT FALSE,
    demo            BOOL DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Disruption events log
CREATE TABLE IF NOT EXISTS disruption_events (
    id              SERIAL PRIMARY KEY,
    scenario_key    TEXT,
    description     TEXT NOT NULL,
    severity        TEXT CHECK (severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    disrupted_suppliers TEXT[],
    affected_skus   TEXT[],
    revenue_at_risk_eur BIGINT,
    recovery_days   INT,
    occurred_at     TIMESTAMPTZ DEFAULT now(),
    notes           TEXT
);

-- Risk score history (for trend tracking)
CREATE TABLE IF NOT EXISTS risk_score_history (
    id              SERIAL PRIMARY KEY,
    supplier_name   TEXT NOT NULL,
    risk_score      FLOAT NOT NULL,
    risk_level      TEXT,
    flags           TEXT,
    scored_at       TIMESTAMPTZ DEFAULT now()
);

-- KPI snapshots (for dashboards)
CREATE TABLE IF NOT EXISTS kpi_snapshots (
    id              SERIAL PRIMARY KEY,
    snapshot_at     TIMESTAMPTZ DEFAULT now(),
    total_suppliers INT,
    high_risk_count INT,
    critical_count  INT,
    countries_count INT,
    avg_risk_score  FLOAT,
    tier1_count     INT,
    tier2_count     INT,
    tier3_count     INT,
    tier4_count     INT
);

-- ── Indexes ──────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_suppliers_country     ON suppliers (country);
CREATE INDEX IF NOT EXISTS idx_suppliers_tier        ON suppliers (tier);
CREATE INDEX IF NOT EXISTS idx_suppliers_risk_level  ON suppliers (risk_level);
CREATE INDEX IF NOT EXISTS idx_suppliers_risk_score  ON suppliers (risk_score DESC);
CREATE INDEX IF NOT EXISTS idx_suppliers_name        ON suppliers USING gin (to_tsvector('english', name));
CREATE INDEX IF NOT EXISTS idx_supply_customer       ON supply_relationships (customer_name);
CREATE INDEX IF NOT EXISTS idx_supply_supplier       ON supply_relationships (supplier_name);
CREATE INDEX IF NOT EXISTS idx_disruption_severity   ON disruption_events (severity, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_risk_history_supplier ON risk_score_history (supplier_name, scored_at DESC);

-- ── Views ─────────────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW v_high_risk_suppliers AS
    SELECT name, country, tier, risk_score, risk_summary, risk_level
    FROM suppliers
    WHERE risk_level IN ('HIGH','CRITICAL')
    ORDER BY risk_score DESC;

CREATE OR REPLACE VIEW v_supply_chain_by_product AS
    SELECT
        p.sku,
        p.name AS product,
        sr.customer_name,
        sr.supplier_name,
        s.country,
        s.tier,
        s.risk_level,
        s.risk_score,
        sr.component,
        sr.single_source,
        sr.contract_value_eur
    FROM supply_relationships sr
    JOIN products p ON p.name = sr.customer_name OR p.sku = sr.customer_name
    LEFT JOIN suppliers s ON s.name = sr.supplier_name
    ORDER BY sr.customer_name, s.tier;

CREATE OR REPLACE VIEW v_country_risk_summary AS
    SELECT
        country,
        count(*) AS supplier_count,
        round(avg(risk_score)::numeric, 3) AS avg_risk,
        count(*) FILTER (WHERE risk_level = 'CRITICAL') AS critical_count,
        count(*) FILTER (WHERE risk_level = 'HIGH') AS high_count,
        array_agg(DISTINCT tier ORDER BY tier) AS tiers_present
    FROM suppliers
    WHERE country IS NOT NULL
    GROUP BY country
    ORDER BY avg_risk DESC;

-- Trigger: auto-update updated_at on suppliers
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS \$\$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
\$\$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_suppliers_updated_at ON suppliers;
CREATE TRIGGER trg_suppliers_updated_at
    BEFORE UPDATE ON suppliers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

SELECT 'Schema created successfully.' AS status;
"

echo "  Tables + views + indexes created."

# ── Insert initial KPI snapshot ────────────────────────────────────────────────
echo
echo "[3/4] Inserting initial KPI snapshot..."
run_psql_db "$DB_NAME" "
INSERT INTO kpi_snapshots (total_suppliers, high_risk_count, critical_count,
  countries_count, avg_risk_score, tier1_count, tier2_count, tier3_count, tier4_count)
VALUES (0, 0, 0, 0, 0, 0, 0, 0, 0)
ON CONFLICT DO NOTHING;
"
echo "  Snapshot inserted."

# ── Verify ─────────────────────────────────────────────────────────────────────
echo
echo "[4/4] Verifying schema..."
TABLE_COUNT=$(ssh -o ProxyJump="$PROXMOX_NODE" root@"$PG_HOST" \
  "PGPASSWORD='$PG_PW' psql -U $PG_USER -d $DB_NAME -tAc \
  \"SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'\"" 2>/dev/null || echo "0")

echo "  Tables found: $TABLE_COUNT"

echo
echo "╔══════════════════════════════════════════════════════╗"
echo "║  knopenkonings schema ready on CT100                 ║"
echo "║  Tables: suppliers, products, supply_relationships,  ║"
echo "║          raw_materials, disruption_events,           ║"
echo "║          risk_score_history, kpi_snapshots           ║"
echo "║  Views:  v_high_risk_suppliers, v_supply_chain...,   ║"
echo "║          v_country_risk_summary                      ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  Next: python3 src/postgres_sync.py                  ║"
echo "╚══════════════════════════════════════════════════════╝"
