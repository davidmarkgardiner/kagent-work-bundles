# GitLab Ticket: Prove Memory MCP Shared Context

## Summary

Prove agents can seed, recall, and use shared memory safely in Kagent triage v2.

## Feature

The memory workflow should persist a safe context item, recall it in a later
agent/session, use it during triage, and prove memory writes are curated.

## Evidence Required

- Memory MCP server status and tools.
- Memory seed operation.
- Memory recall operation.
- Triage usage output.
- Curator path or dangerous-write denial.

## Acceptance Criteria

- `MEMORY_MCP_AVAILABLE: yes`
- `MEMORY_SEEDED: yes`
- `MEMORY_RECALLED: yes`
- `MEMORY_USED_IN_TRIAGE: yes`
- `CURATOR_PATH_DEFINED: yes`
- `DANGEROUS_MEMORY_WRITE_BLOCKED: yes`
- `OUTPUT_SANITIZED: yes`

## Notes

Do not expose memory write/delete tools to every front-door agent.
