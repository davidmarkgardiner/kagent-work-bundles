# PostgreSQL MCP token-efficiency GEEKOM POC — 2026-09-08

## Result

**PASS** for the scoped adapter, skill-image package, TLS PostgreSQL fixture,
and Streamable HTTP MCP transport on the one-node `kind-homelab` cluster.

This was a disposable synthetic test. It did not use a workplace database,
workplace credentials, private endpoints, Agent Gateway, kagent A2A, or a paid
model call.

## Test shape

```text
5,000 synthetic matching rows
  -> approved PostgreSQL view over TLS
  -> password-mode FastMCP test Pod
  -> fetch at most 51 rows
  -> return 50 rows plus truncation metadata
  -> Streamable HTTP MCP client
```

The separately packaged `postgres-token-efficient-query` skill image was built
and its `SKILL.md`, legacy SQL policy, and SQL policy cases were verified inside
the image. The skill was not attached to a model-backed Agent in this test.

## Receipts

```text
POSTGRES_TOKEN_EFFICIENT_SKILL_IMAGE_OK
POSTGRES_BUDGET_FIXTURE_5000_ROWS_OK
MCP_RESULT_ROW_BUDGET_OK count=50
MCP_RESULT_BYTE_BUDGET_OK bytes=12440
MCP_LARGE_RESULT_TRUNCATION_OK
MCP_TOKEN_BURN_GUARD_PASS
MCP_STREAMABLE_HTTP_CALL_OK
MCP_TRANSPORT_RETURNED_ROWS_OK count=50
MCP_TRANSPORT_ENVELOPE_BYTES_OK bytes=24963
MCP_TRANSPORT_TOKEN_BURN_GUARD_PASS
```

The transport envelope was larger than the adapter data because FastMCP
returned text content and structured content. It remained bounded at 24,963
bytes for this fixture rather than returning all 5,000 rows.

FastMCP emitted upstream Authlib deprecation warnings during the verifier calls;
they did not fail the request or affect the result contract. Review them when
refreshing dependencies rather than changing dependency versions as part of
the workplace token-efficiency rollout.

## Cleanup

```text
TEST_NAMESPACE_REMOVED_OK
TEST_IMAGES_REMOVED_OK
REMOTE_TEMP_REMOVED_OK
```

No test namespace, generated credential, certificate, temporary source copy,
or test image was retained on the GEEKOM. The ordinary Docker build cache was
not pruned.

## Remaining workplace gates

- Inspect the actual installed MCP, Gateway, Agent, authentication mode, and
  rollback digest.
- Measure sanitized before/after model input tokens through the real Agent
  Gateway and kagent A2A path.
- Attach the skill by approved internal immutable image digest and verify the
  installed kagent skill schema/runtime.
- If a legacy SQL-text tool exists, implement AST enforcement and pass the
  packaged SQL policy cases. Typed FastMCP requires no SQL-text tool.
- Stop before production promotion pending explicit workplace approval.
