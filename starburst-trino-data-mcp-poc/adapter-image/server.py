# Source equivalent of the HomeLab adapter ConfigMap. Package with Dockerfile
# for an office/air-gapped deployment; retain only the three bounded tools.
import os

from fastmcp import FastMCP
from trino.dbapi import connect

TRINO_HOST = os.environ["TRINO_HOST"]
PRODUCT_ID = "homelab-risk-summary-v1"
ALLOWED_BANDS = {"low", "medium", "high"}
mcp = FastMCP("trino-readonly-data-product")


def query(sql):
    connection = connect(
        host=TRINO_HOST,
        port=8080,
        user="data-mcp-poc",
        catalog="memory",
        schema="default",
        http_scheme="http",
    )
    try:
        cursor = connection.cursor()
        cursor.execute(sql)
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        connection.close()


@mcp.tool()
def search_data_products(query_text: str) -> list[dict]:
    """Find the one curated synthetic data product by a simple keyword."""
    if query_text.strip().lower() not in {"*", "risk", "overdue", "account", "accounts", "balance"}:
        return []
    return [{
        "data_product_id": PRODUCT_ID,
        "name": "Homelab overdue-account risk summary",
        "catalog": "memory",
        "schema": "default",
        "classification": "synthetic-lab-data",
    }]


@mcp.tool()
def get_data_product_details(data_product_id: str) -> dict:
    """Return curated metadata, not a general catalogue browser."""
    if data_product_id != PRODUCT_ID:
        raise ValueError("unknown data product")
    return {
        "data_product_id": PRODUCT_ID,
        "table": "memory.default.account_risk",
        "columns": [
            {"name": "risk_band", "type": "varchar"},
            {"name": "overdue_accounts", "type": "bigint"},
            {"name": "overdue_balance", "type": "decimal(12,2)"},
        ],
        "writes_supported": False,
        "arbitrary_sql_supported": False,
    }


@mcp.tool()
def get_overdue_risk_summary(risk_band: str | None = None) -> list[dict]:
    """Return a small fixed aggregate; arbitrary SQL and writes are absent."""
    if risk_band is not None and risk_band not in ALLOWED_BANDS:
        raise ValueError("risk_band must be one of low, medium, high")
    predicate = "" if risk_band is None else " WHERE risk_band = '" + risk_band + "'"
    rows = query(
        "SELECT risk_band, overdue_accounts, overdue_balance FROM "
        "memory.default.account_risk" + predicate + " ORDER BY risk_band"
    )
    return [{key: str(value) for key, value in row.items()} for row in rows]


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000, path="/mcp", show_banner=False)
