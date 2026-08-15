"""Bounded PostgreSQL tools for the Kubernetes inventory MCP proof.

This intentionally exposes no generic SQL tool. Add a tool only alongside an
approved view, a typed input contract, and tests for its access boundary.
"""

import os

import psycopg
from fastmcp import FastMCP


mcp = FastMCP("postgres-kubernetes-inventory-readonly")
DATABASE_URL = os.environ["POSTGRES_CONNECTION_STRING"]


def query(sql: str, params: tuple[object, ...] = ()) -> list[dict[str, object]]:
    """Execute a fixed, parameterised SELECT and return named result fields."""
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            columns = [item.name for item in cur.description]
            return [dict(zip(columns, row, strict=True)) for row in cur.fetchall()]


@mcp.tool()
def get_kubernetes_inventory_data_product_details() -> dict[str, object]:
    """Describe the synthetic Kubernetes namespace and image inventory product."""
    return {
        "data_product": "synthetic-kubernetes-namespace-image-inventory-v1",
        "functions": [
            "get_namespace_workload_summary",
            "get_namespace_container_images",
            "get_image_risk_summary",
        ],
        "allowed_namespaces": ["payments", "catalogue", "developer-tools"],
        "writes_supported": False,
        "arbitrary_sql_supported": False,
        "vector_search_exposed": False,
    }


@mcp.tool()
def get_namespace_workload_summary(namespace_name: str) -> list[dict[str, object]]:
    """Return the synthetic workload and running-pod summary for one namespace."""
    return query(
        """SELECT DISTINCT namespace_name, environment, owner_team, workload_count,
                  running_pod_count, namespace_observed_at
           FROM public.v_namespace_image_summary WHERE namespace_name = %s""",
        (namespace_name,),
    )


@mcp.tool()
def get_namespace_container_images(
    namespace_name: str, limit: int = 20
) -> list[dict[str, object]]:
    """Return at most 20 synthetic image records for one namespace."""
    if not 1 <= limit <= 20:
        raise ValueError("limit must be between 1 and 20")
    return query(
        """SELECT namespace_name, workload_name, image_repository, image_tag,
                  image_digest, critical_findings, high_findings, scanned_at
           FROM public.v_namespace_image_summary WHERE namespace_name = %s
           ORDER BY workload_name LIMIT %s""",
        (namespace_name, limit),
    )


@mcp.tool()
def get_image_risk_summary(
    namespace_name: str, severity_min: str = "high"
) -> list[dict[str, object]]:
    """Return synthetic image-risk rows at high or critical severity."""
    predicates = {
        "critical": "critical_findings > 0",
        "high": "critical_findings > 0 OR high_findings > 0",
    }
    try:
        predicate = predicates[severity_min]
    except KeyError as error:
        raise ValueError("severity_min must be high or critical") from error
    return query(
        f"""SELECT namespace_name, workload_name, image_repository, image_tag,
                   critical_findings, high_findings, scanned_at
            FROM public.v_namespace_image_summary WHERE namespace_name = %s
            AND ({predicate}) ORDER BY workload_name""",
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
