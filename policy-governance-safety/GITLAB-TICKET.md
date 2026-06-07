# GitLab Ticket: Run Kagent Governance And Safety Audit

## Summary

Audit Kagent triage v2 governance boundaries and prove dangerous tools, unsafe
chaos, broad GitLab writes, and uncurated memory writes are blocked or gated.

## Feature

The governance workflow should inspect real agent/tool grants and policy
controls, then return a sanitized report with pass/block/gap status and owners.

## Evidence Required

- Agent and ToolGrant inventory.
- Discovered MCP tool audit.
- Forbidden-tool denial.
- Production-chaos denial.
- GitLab write boundary.
- Memory write boundary.
- Public-safety scan.

## Acceptance Criteria

- `POLICY_BASELINE_COLLECTED: yes`
- `TOOLGRANTS_AUDITED: yes`
- `FORBIDDEN_TOOLS_BLOCKED: yes`
- `PROD_CHAOS_BLOCKED: yes`
- `GITLAB_WRITE_BOUNDARY_VERIFIED: yes`
- `MEMORY_WRITE_BOUNDARY_VERIFIED: yes`
- `SECRET_LEAK_SCAN_PASSED: yes`
- `POLICY_REPORT_CREATED: yes`
- `OUTPUT_SANITIZED: yes`

## Notes

Do not trust "readonly" names. Audit the actual tools granted to each agent.
