"""Standard-library tests for the MCP model-context response budget."""

import json
import os
import unittest
from unittest.mock import patch

from result_budget import ResultBudget, bounded_result, budget_from_env


class ResultBudgetTests(unittest.TestCase):
    def test_thousands_of_rows_are_capped_and_marked(self) -> None:
        budget = ResultBudget(max_rows=50, max_response_bytes=32_768, max_cell_chars=512)
        result = bounded_result(
            ["id", "name"],
            ((number, f"namespace-{number}") for number in range(5_000)),
            budget,
        )

        self.assertEqual(result["returned_rows"], 50)
        self.assertTrue(result["truncated"])
        self.assertIn("row_limit", result["truncation_reasons"])
        self.assertLessEqual(len(json.dumps(result).encode("utf-8")), 32_768)

    def test_byte_limit_removes_rows_until_payload_fits(self) -> None:
        budget = ResultBudget(max_rows=50, max_response_bytes=4_096, max_cell_chars=2_048)
        result = bounded_result(
            ["id", "description"],
            ((number, "x" * 2_000) for number in range(3)),
            budget,
        )

        self.assertTrue(result["truncated"])
        self.assertIn("byte_limit", result["truncation_reasons"])
        self.assertLessEqual(len(json.dumps(result).encode("utf-8")), 4_096)

    def test_large_cells_and_binary_values_are_not_returned_whole(self) -> None:
        budget = ResultBudget(max_rows=10, max_response_bytes=4_096, max_cell_chars=64)
        result = bounded_result(
            ["text", "blob"],
            [("sensitive" * 100, b"raw-binary")],
            budget,
        )

        self.assertIn("cell_limit", result["truncation_reasons"])
        self.assertLessEqual(len(result["rows"][0]["text"]), 65)
        self.assertEqual(result["rows"][0]["blob"], "<binary omitted>")

    def test_environment_values_cannot_raise_hard_ceilings(self) -> None:
        with patch.dict(os.environ, {"MCP_MAX_ROWS": "101"}):
            with self.assertRaises(ValueError):
                budget_from_env()

        with patch.dict(os.environ, {"MCP_MAX_RESPONSE_BYTES": "65537"}):
            with self.assertRaises(ValueError):
                budget_from_env()


if __name__ == "__main__":
    unittest.main()
