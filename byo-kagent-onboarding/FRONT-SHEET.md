# Bring Your Own Kagent Onboarding Work-Agent Bundle

Purpose: let a team bring a read-only triage agent, and optionally a bounded
remediation agent, onto the platform with ToolGrants, policy checks, and demo
evidence.

## One-Line Ask

Onboard one team-owned agent through the BYO process, prove allowed tools work,
prove dangerous tools are absent or denied, and return an SRE/team demo report.

## Start Here

1. `FRONT-SHEET.md`
2. `WORK-AGENT-START-PROMPT.md`
3. `CHECKLIST.md`
4. `requests/byo-kagent-request.yaml`
5. `prompts/01-onboard-readonly-team-agent.md`
6. `payload/REFERENCE.md`
7. `evidence/EVIDENCE-TEMPLATE.md`

Static verification proves this bundle is internally consistent. It does not
prove live BYO kagent, ToolGrant, policy, namespace, or demo behavior.

## Required Markers

```text
BYO_REQUEST_ACCEPTED: yes
AGENT_RENDERED: yes
TOOLGRANT_SCOPED: yes
READ_ONLY_TRIAGE_PROVEN: yes
DANGEROUS_TOOLS_ABSENT: yes
POLICY_DENIAL_TESTED: yes
OUTPUT_SANITIZED: yes
```
