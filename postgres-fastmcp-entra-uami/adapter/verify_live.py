"""Fail-closed live gates for either FastMCP authentication mode.

Run this inside the adapter Pod. It prints markers only, never tokens, rows,
connection strings, database identities, or environment-specific identifiers.
"""

from psycopg import sql

import server


def main() -> None:
    approved_schema, approved_view = server.required_qualified_name("APPROVED_VIEW")
    denied_schema, denied_table = server.required_qualified_name("DENIED_BASE_TABLE")

    if server.AUTH_MODE == "entra":
        # Prove the workload credential chain without exposing the token.
        server.CREDENTIAL.get_token(
            "https://ossrdbms-aad.database.windows.net/.default"
        )
        print("ENTRA_TOKEN_ACQUISITION_OK")
    else:
        print("PASSWORD_SECRET_CONFIGURATION_OK")

    with server.connect() as conn:
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

    # A second independently authenticated connection proves the no-pool
    # adapter can reconnect with the selected authentication mode.
    with server.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            if cur.fetchone() != (1,):
                raise RuntimeError("fresh-connection SELECT 1 failed")
    print("FRESH_POSTGRES_CONNECTION_OK")
    print("FASTMCP_DATABASE_GATES_PASS")


if __name__ == "__main__":
    main()
