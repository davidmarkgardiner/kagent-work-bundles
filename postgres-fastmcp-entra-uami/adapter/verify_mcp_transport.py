"""Verify the bounded result through the live Streamable HTTP MCP transport."""

import asyncio
import json
import os

from fastmcp import Client


async def verify() -> None:
    url = os.environ.get("MCP_TEST_URL", "http://fastmcp-budget:8000/mcp")
    async with Client(url) as client:
        result = await client.call_tool(
            "get_namespace_summary", {"namespace_name": "bulk-test"}
        )

    data = result.data
    if not isinstance(data, dict):
        raise TypeError("MCP structured result is not an object")
    if data.get("returned_rows") != 50:
        raise RuntimeError("MCP transport did not preserve the 50-row budget")
    if not data.get("truncated") or "row_limit" not in data.get(
        "truncation_reasons", []
    ):
        raise RuntimeError("MCP transport did not preserve truncation metadata")

    content = [
        item.model_dump(mode="json") if hasattr(item, "model_dump") else str(item)
        for item in result.content
    ]
    transport_shape = {
        "content": content,
        "structuredContent": result.structured_content,
    }
    transport_bytes = len(
        json.dumps(transport_shape, default=str, separators=(",", ":")).encode("utf-8")
    )
    if transport_bytes > 73_728:
        raise RuntimeError("MCP transport envelope exceeded the fail-closed ceiling")

    print("MCP_STREAMABLE_HTTP_CALL_OK")
    print(f"MCP_TRANSPORT_RETURNED_ROWS_OK count={data['returned_rows']}")
    print(f"MCP_TRANSPORT_ENVELOPE_BYTES_OK bytes={transport_bytes}")
    print("MCP_TRANSPORT_TOKEN_BURN_GUARD_PASS")


if __name__ == "__main__":
    asyncio.run(verify())
