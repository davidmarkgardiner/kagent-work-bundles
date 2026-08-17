# Critique prompt — MCPg v0.7.1 work bundle

Review this bundle as a read-only reviewer. Do not deploy or infer live work
state. Classify each finding as **blocker**, **non-blocking hardening**, or
**unknown requiring validation**, citing the file and line.

Assess whether:

1. `mcpg-postgres-mcp.yaml` uses only MCPg environment variables, has no
   CrystalDBA CLI arguments, requires TLS, and keeps the database secret out of
   kagent.
2. The deployed initial capability is schema-only: `list_schemas`,
   `list_tables`, and `describe_table` appear identically in the Agent and
   Gateway policy.
3. The Gateway route uses Streamable HTTP `/mcp`, has fail-closed behaviour,
   and requires server-side CRD validation before work apply.
4. The direct probe is temporary and the NetworkPolicy provides a clear
   Gateway-only steady-state boundary after probe deletion.
5. The variable contract, secret delivery, private endpoint/TLS, reader-role,
   model-egress, UAMI/Entra, and work-image signing boundaries are stated
   honestly rather than claimed as proven.

Return GO, CONDITIONAL GO, or NO-GO with the smallest safe next action.
