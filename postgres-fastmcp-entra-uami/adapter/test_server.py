"""Offline contract tests for the standalone FastMCP UAMI bundle."""

import os
import unittest
from unittest.mock import patch


os.environ.setdefault("POSTGRES_HOST", "postgres.example.invalid")
os.environ.setdefault("POSTGRES_DATABASE", "synthetic")
os.environ.setdefault("APPROVED_VIEW", "work_inventory.approved_namespaces")

import server  # noqa: E402  (environment is required at import time)
import verify_live  # noqa: E402


class ToolContractTests(unittest.TestCase):
    def test_only_the_approved_tools_are_registered(self) -> None:
        import asyncio

        tools = asyncio.run(server.mcp.get_tools())
        self.assertEqual(
            set(tools),
            {
                "get_inventory_data_product_details",
                "get_namespace_count",
                "get_namespace_summary",
            },
        )

    def test_namespace_count_uses_the_approved_view(self) -> None:
        with patch.object(server, "query", return_value=[{"namespace_count": 3}]) as query:
            result = server.get_namespace_count.fn()

        self.assertEqual(result, [{"namespace_count": 3}])
        (statement,) = query.call_args.args
        rendered = statement.as_string(None)
        self.assertIn("count(DISTINCT namespace_name)", rendered)
        self.assertIn('"work_inventory"."approved_namespaces"', rendered)

    def test_namespace_summary_binds_the_namespace_parameter(self) -> None:
        with patch.object(server, "query", return_value=[]) as query:
            server.get_namespace_summary.fn("payments")

        statement, params = query.call_args.args
        rendered = statement.as_string(None)
        self.assertIn('FROM "work_inventory"."approved_namespaces"', rendered)
        self.assertIn("WHERE namespace_name = %s", rendered)
        self.assertEqual(params, ("payments",))

    def test_live_verifier_accepts_only_qualified_identifiers(self) -> None:
        with patch.dict(os.environ, {"APPROVED_VIEW": "public.approved_inventory"}):
            self.assertEqual(
                server.required_qualified_name("APPROVED_VIEW"),
                ("public", "approved_inventory"),
            )

        for unsafe in ("approved_inventory", "public.inventory;DROP TABLE x", "Public.inventory"):
            with self.subTest(unsafe=unsafe), patch.dict(
                os.environ, {"APPROVED_VIEW": unsafe}
            ):
                with self.assertRaises(ValueError):
                    server.required_qualified_name("APPROVED_VIEW")


if __name__ == "__main__":
    unittest.main()
