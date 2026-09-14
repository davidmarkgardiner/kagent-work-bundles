"""Marker-only in-cluster verification of the MCP result budget."""

import json

import server


def main() -> None:
    result = server.get_namespace_summary.fn("bulk-test")
    encoded_size = len(json.dumps(result, default=str).encode("utf-8"))
    if result["returned_rows"] > server.RESULT_BUDGET.max_rows:
        raise RuntimeError("row budget was exceeded")
    if encoded_size > server.RESULT_BUDGET.max_response_bytes:
        raise RuntimeError("byte budget was exceeded")
    if not result["truncated"] or "row_limit" not in result["truncation_reasons"]:
        raise RuntimeError("large result was not marked as truncated")
    print(f"MCP_RESULT_ROW_BUDGET_OK count={result['returned_rows']}")
    print(f"MCP_RESULT_BYTE_BUDGET_OK bytes={encoded_size}")
    print("MCP_LARGE_RESULT_TRUNCATION_OK")
    print("MCP_TOKEN_BURN_GUARD_PASS")


if __name__ == "__main__":
    main()
