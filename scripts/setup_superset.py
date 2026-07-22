"""
UC4 Supply Chain — Superset Dashboard Setup
Creates: database connection, dataset, and 3 charts + 1 dashboard

Usage:
  export $(grep -v '^#' .env | xargs)
  python3 scripts/setup_superset.py

Requires Superset running (CT206, 10.0.2.206:8088) and knopenkonings.suppliers
table populated (run src/postgres_sync.py first).
"""
import json
import os
import sys
import urllib.request
import urllib.error

SUPERSET_URL = os.getenv("SUPERSET_URL",      "http://10.0.2.206:8088")
SUPERSET_USER = os.getenv("SUPERSET_USER",    "admin@research-ready.nl")
SUPERSET_PASS = os.getenv("SUPERSET_PASSWORD", "")
PG_HOST  = os.getenv("PG_HOST",     "10.0.1.100")
PG_PORT  = os.getenv("PG_PORT",     "5432")
PG_USER  = os.getenv("PG_USER",     "postgres")
PG_PASS  = os.getenv("PG_PASSWORD", "")
PG_DB    = os.getenv("PG_DATABASE", "knopenkonings")


def _post(path: str, body: dict, token: str,
          method: str = "POST", csrf: str = "") -> dict:
    h = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    if csrf:
        h["X-CSRFToken"] = csrf
    req = urllib.request.Request(
        f"{SUPERSET_URL}{path}",
        data=json.dumps(body).encode(),
        headers=h,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode()
        raise RuntimeError(f"{method} {path} → HTTP {exc.code}: {body_text[:300]}") from exc


def _get(path: str, token: str) -> dict:
    req = urllib.request.Request(
        f"{SUPERSET_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def login() -> tuple[str, str]:
    """Return (jwt_token, csrf_token)."""
    data = _post(
        "/api/v1/security/login",
        {"username": SUPERSET_USER, "password": SUPERSET_PASS, "provider": "db"},
        token="",
    )
    jwt = data["access_token"]
    csrf_data = _get("/api/v1/security/csrf_token/", jwt)
    csrf = csrf_data.get("result", "")
    print(f"Logged in as {SUPERSET_USER}")
    return jwt, csrf


def create_database(token: str, csrf: str) -> int:
    """Create PostgreSQL knopenkonings database connection. Return id."""
    # Check if it already exists
    existing = _get("/api/v1/database/?q=(filters:!((col:database_name,opr:eq,val:knopenkonings)))", token)
    if existing.get("count", 0) > 0:
        db_id = existing["result"][0]["id"]
        print(f"Database 'knopenkonings' already exists (id={db_id})")
        return db_id

    result = _post(
        "/api/v1/database/",
        {
            "database_name": "knopenkonings",
            "sqlalchemy_uri": (
                f"postgresql+psycopg2://{PG_USER}:{PG_PASS}"
                f"@{PG_HOST}:{PG_PORT}/{PG_DB}"
            ),
            "expose_in_sqllab": True,
            "allow_run_async": True,
        },
        token, csrf=csrf,
    )
    db_id = result["id"]
    print(f"Created database connection: id={db_id}")
    return db_id


def create_dataset(token: str, csrf: str, db_id: int) -> int:
    """Create suppliers dataset from knopenkonings.suppliers table."""
    existing = _get(
        f"/api/v1/dataset/?q=(filters:!((col:table_name,opr:eq,val:suppliers)))",
        token,
    )
    if existing.get("count", 0) > 0:
        ds_id = existing["result"][0]["id"]
        print(f"Dataset 'suppliers' already exists (id={ds_id})")
        return ds_id

    result = _post(
        "/api/v1/dataset/",
        {
            "database":   db_id,
            "schema":     "public",
            "table_name": "suppliers",
        },
        token, csrf=csrf,
    )
    ds_id = result["id"]
    print(f"Created dataset: id={ds_id}")
    return ds_id


def create_charts(token: str, csrf: str, ds_id: int) -> list[int]:
    """Create 3 charts. Return list of chart ids."""
    chart_ids = []

    charts = [
        {
            "slice_name":    "Suppliers by Country",
            "viz_type":      "echarts_bar",
            "datasource_id": ds_id,
            "datasource_type": "table",
            "params": json.dumps({
                "metrics":        [{"aggregate": "COUNT", "column": {"column_name": "id"}, "expressionType": "SIMPLE", "label": "COUNT(id)"}],
                "groupby":        ["country"],
                "row_limit":      50,
                "order_desc":     True,
                "x_axis":         "country",
                "x_axis_title":   "Country (ISO 2)",
                "y_axis_title":   "Supplier Count",
                "rich_tooltip":   True,
                "orientation":    "vertical",
            }),
        },
        {
            "slice_name":    "Tier Distribution",
            "viz_type":      "pie",
            "datasource_id": ds_id,
            "datasource_type": "table",
            "params": json.dumps({
                "metrics": [{"aggregate": "COUNT", "column": {"column_name": "id"}, "expressionType": "SIMPLE", "label": "COUNT(id)"}],
                "groupby": ["tier"],
                "row_limit": 10,
                "show_labels": True,
                "show_legend": True,
                "label_type": "key_percent",
            }),
        },
        {
            "slice_name":    "Risk Flag Heatmap",
            "viz_type":      "table",
            "datasource_id": ds_id,
            "datasource_type": "table",
            "params": json.dumps({
                "adhoc_filters": [],
                "all_columns": ["name", "country", "tier", "risk_flags", "inferred"],
                "order_by_cols": ["tier", "country"],
                "row_limit": 200,
                "include_search": True,
                "page_length": 25,
                "adhoc_filters": [
                    {
                        "clause": "WHERE",
                        "expressionType": "SQL",
                        "sqlExpression": "risk_flags IS NOT NULL AND array_length(risk_flags, 1) > 0",
                    }
                ],
            }),
        },
    ]

    for chart in charts:
        try:
            result = _post("/api/v1/chart/", chart, token, csrf=csrf)
            cid = result["id"]
            chart_ids.append(cid)
            print(f"Created chart: '{chart['slice_name']}' (id={cid})")
        except Exception as exc:
            print(f"WARNING: chart '{chart['slice_name']}' failed: {exc}")

    return chart_ids


def create_dashboard(token: str, csrf: str, chart_ids: list[int]) -> int:
    """Create 'Supply Chain Overview' dashboard with the 3 charts."""
    # Build position_json layout
    positions = {"DASHBOARD_VERSION_KEY": "v2"}
    row_id = "ROW-1"
    positions["ROOT_ID"] = {
        "children": ["GRID_ID"],
        "id": "ROOT_ID",
        "type": "ROOT",
    }
    positions["GRID_ID"] = {
        "children": [row_id],
        "id": "GRID_ID",
        "type": "GRID",
    }
    col_children = []
    x = 0
    for i, cid in enumerate(chart_ids):
        col_id = f"COLUMN-{i+1}"
        chart_key = f"CHART-{i+1}"
        width = 12 if len(chart_ids) == 1 else (8 if i == 0 else 4)
        col_children.append(col_id)
        positions[col_id] = {
            "children": [chart_key],
            "id": col_id,
            "type": "COLUMN",
            "meta": {"background": "BACKGROUND_TRANSPARENT", "width": width},
        }
        positions[chart_key] = {
            "children": [],
            "id": chart_key,
            "type": "CHART",
            "meta": {"chartId": cid, "height": 50, "width": width, "sliceName": f"chart-{cid}"},
        }
        x += width

    positions[row_id] = {
        "children": col_children,
        "id": row_id,
        "type": "ROW",
        "meta": {"background": "BACKGROUND_TRANSPARENT"},
    }

    result = _post(
        "/api/v1/dashboard/",
        {
            "dashboard_title": "Supply Chain Overview",
            "published":       True,
            "position_json":   json.dumps(positions),
            "charts":          chart_ids,
        },
        token, csrf=csrf,
    )
    dash_id = result["id"]
    print(f"Created dashboard: 'Supply Chain Overview' (id={dash_id})")
    print(f"Open: {SUPERSET_URL}/superset/dashboard/{dash_id}/")
    return dash_id


def main() -> None:
    if not SUPERSET_PASS:
        sys.exit("ERROR: SUPERSET_PASSWORD not set. Run: export $(grep -v '^#' .env | xargs)")

    token, csrf = login()
    db_id   = create_database(token, csrf)
    ds_id   = create_dataset(token, csrf, db_id)
    c_ids   = create_charts(token, csrf, ds_id)
    if c_ids:
        create_dashboard(token, csrf, c_ids)
    else:
        print("No charts created — skipping dashboard.")
    print("\nDone. If Superset shows a PendingRollbackError, restart it:")
    print("  ssh -J root@10.0.0.15 root@10.0.2.206 systemctl restart superset")


if __name__ == "__main__":
    main()
