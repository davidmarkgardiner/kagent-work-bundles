# Local Kubernetes token-budget test

This disposable test builds the FastMCP adapter, loads it into an explicitly
named local kind cluster, creates a synthetic TLS PostgreSQL fixture with 5,000
matching rows, executes the adapter's marker-only result-budget verifier, and
calls the same tool over the live Streamable HTTP MCP transport. It refuses
non-kind contexts and an existing `fastmcp-budget-test` namespace.
The test also builds the token-efficient skill image and verifies that its
instructions, legacy SQL policy, and policy cases are present in the image.

```sh
work-agent-bundles/postgres-fastmcp-entra-uami/tests/local-k8s/run.sh kind-homelab
```

The namespace is deleted on exit. Set `KEEP_LOCAL_K8S_TEST=true` only when the
synthetic resources need to remain for debugging. No database rows, generated
passwords, certificate private keys, tokens, or connection strings are printed
or written to the repository.

Pass markers are:

```text
POSTGRES_BUDGET_FIXTURE_5000_ROWS_OK
POSTGRES_TOKEN_EFFICIENT_SKILL_IMAGE_OK
MCP_RESULT_ROW_BUDGET_OK
MCP_RESULT_BYTE_BUDGET_OK
MCP_LARGE_RESULT_TRUNCATION_OK
MCP_TOKEN_BURN_GUARD_PASS
MCP_STREAMABLE_HTTP_CALL_OK
MCP_TRANSPORT_RETURNED_ROWS_OK count=50
MCP_TRANSPORT_ENVELOPE_BYTES_OK bytes=<bounded-size>
MCP_TRANSPORT_TOKEN_BURN_GUARD_PASS
```
