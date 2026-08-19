"""Typed Azure Entra PostgreSQL tools for the FastMCP UAMI bundle.

The Pod has no PostgreSQL password. DefaultAzureCredential obtains its token
from AKS workload identity and EntraConnection supplies a fresh token whenever
a new PostgreSQL connection is opened.
"""

import os
import re

from azure.identity import DefaultAzureCredential
from azure_postgresql_auth.psycopg3 import EntraConnection
from fastmcp import FastMCP
from psycopg import sql


mcp = FastMCP("postgres-kubernetes-inventory-entra-readonly")
CREDENTIAL = DefaultAzureCredential()
DB_HOST = os.environ["POSTGRES_HOST"]
DB_NAME = os.environ["POSTGRES_DATABASE"]
QUALIFIED_NAME = re.compile(r"^[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*$")


def required_qualified_name(variable: str) -> tuple[str, str]:
    """Return a validated lower-case schema and relation name."""
    value = os.environ[variable]
    if not QUALIFIED_NAME.fullmatch(value):
        raise ValueError(f"{variable} must be a lower-case schema-qualified name")
    schema, relation = value.split(".", 1)
    return schema, relation


APPROVED_SCHEMA, APPROVED_VIEW_NAME = required_qualified_name("APPROVED_VIEW")
APPROVED_VIEW = sql.SQL("{}.{}").format(
    sql.Identifier(APPROVED_SCHEMA), sql.Identifier(APPROVED_VIEW_NAME)
)


def query(statement: sql.Composable, params: tuple[object, ...] = ()) -> list[dict[str, object]]:
    """Run a fixed, parameterised SELECT using a fresh Entra-authenticated connection."""
    with EntraConnection.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        sslmode="require",
        connect_timeout=10,
        credential=CREDENTIAL,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(statement, params)
            columns = [item.name for item in cur.description]
            return [dict(zip(columns, row, strict=True)) for row in cur.fetchall()]


@mcp.tool()
def get_inventory_data_product_details() -> dict[str, object]:
    """Describe the bounded synthetic namespace inventory data product."""
    return {
        "data_product": "synthetic-kubernetes-namespace-inventory-v1",
        "functions": ["get_namespace_count", "get_namespace_summary"],
        "authentication": "Azure Entra workload identity",
        "writes_supported": False,
        "arbitrary_sql_supported": False,
    }


@mcp.tool()
def get_namespace_count() -> list[dict[str, object]]:
    """Return the number of distinct namespaces in the approved inventory view."""
    return query(
        sql.SQL("SELECT count(DISTINCT namespace_name) AS namespace_count FROM {}")
        .format(APPROVED_VIEW)
    )


@mcp.tool()
def get_namespace_summary(namespace_name: str) -> list[dict[str, object]]:
    """Return the approved ownership and workload summary for one namespace."""
    return query(
        sql.SQL(
            """SELECT namespace_name, owner_team, workload_type, lob, region,
                      workload_count, running_pod_count, observed_at
               FROM {}
               WHERE namespace_name = %s"""
        ).format(APPROVED_VIEW),
        (namespace_name,),
    )


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8000,
        path="/mcp",
        show_banner=False,
    )
