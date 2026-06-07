# GitLab Ticket: Onboard A Team-Owned kagent

## Summary

Onboard one team-owned kagent through the BYO process and prove its tool access
is scoped safely.

## Feature

The BYO workflow should create or verify a read-only triage agent for a target
team/application, prove allowed tools work, and prove dangerous tools are absent
or denied.

## Evidence Required

- Team/application request.
- Agent manifest or rendered config.
- ToolGrant and MCP tool list.
- Read-only triage proof.
- Dangerous-tool denial proof.
- Remediation boundary if applicable.

## Acceptance Criteria

- `BYO_REQUEST_ACCEPTED: yes`
- `AGENT_RENDERED: yes`
- `TOOLGRANT_SCOPED: yes`
- `READ_ONLY_TRIAGE_PROVEN: yes`
- `DANGEROUS_TOOLS_ABSENT: yes`
- `POLICY_DENIAL_TESTED: yes`
- `OUTPUT_SANITIZED: yes`

## Notes

Start read-only. Do not expose apply, delete, exec, broad GitLab write, or
memory mutation tools to the default front-door agent.
