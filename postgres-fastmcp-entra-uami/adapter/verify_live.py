"""Fail-closed live gates for the standalone UAMI adapter.

Run this inside the adapter Pod. It prints markers only, never tokens, rows,
connection strings, database identities, or environment-specific identifiers.
"""

from psycopg import sql

import server


def connect():
    return server.EntraConnection.connect(
        host=server.DB_HOST,
        dbname=server.DB_NAME,
        sslmode="require",
        connect_timeout=10,
        credential=server.CREDENTIAL,
    )


def main() -> None:
    approved_schema, approved_view = server.required_qualified_name("APPROVED_VIEW")
    denied_schema, denied_table = server.required_qualified_name("DENIED_BASE_TABLE")

    # Explicit acquisition proves the workload credential chain without
    # exposing the token. EntraConnection independently obtains credentials
    # for each new connection.
    server.CREDENTIAL.get_token("https://ossrdbms-aad.database.windows.net/.default")
    print("ENTRA_TOKEN_ACQUISITION_OK")

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            if cur.fetchone() != (1,):
                raise RuntimeError("SELECT 1 returned an unexpected result")
            print("POSTGRES_TLS_SELECT_ONE_OK")

            cur.execute(
                sql.SQL("SELECT count(*) FROM {}.{}").format(
                    sql.Identifier(approved_schema), sql.Identifier(approved_view)
                )
            )
            cur.fetchone()
            print("APPROVED_VIEW_SELECT_OK")

            cur.execute(
                "SELECT has_table_privilege(current_user, %s, 'SELECT')",
                (f"{denied_schema}.{denied_table}",),
            )
            if cur.fetchone() != (False,):
                raise PermissionError("database role can SELECT the denied base table")
            print("BASE_TABLE_SELECT_DENIED_OK")

            cur.execute(
                "SELECT has_table_privilege(current_user, %s, 'INSERT,UPDATE,DELETE')",
                (f"{approved_schema}.{approved_view}",),
            )
            if cur.fetchone() != (False,):
                raise PermissionError("database role has write privileges on the approved view")
            print("APPROVED_VIEW_WRITE_DENIED_OK")

    # A second independently authenticated connection is the bounded refresh
    # gate supported by this no-pool adapter.
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            if cur.fetchone() != (1,):
                raise RuntimeError("fresh-connection SELECT 1 failed")
    print("FRESH_ENTRA_CONNECTION_OK")
    print("FASTMCP_ENTRA_DATABASE_GATES_PASS")


if __name__ == "__main__":
    main()
