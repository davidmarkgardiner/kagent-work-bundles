# Policy Governance Safety Work-Agent Bundle

Purpose: prove the Kagent triage v2 platform has enforceable safety controls
around agent permissions, ToolGrants, chaos targets, GitLab write access, and
public-safe outputs.

## One-Line Ask

Audit the work Kagent platform governance path, prove dangerous tools and
production chaos are blocked, verify ToolGrants are scoped, and return a
sanitized policy report that stakeholders can understand.

## Start Here

1. `FRONT-SHEET.md`
2. `WORK-AGENT-START-PROMPT.md`
3. `CHECKLIST.md`
4. `requests/policy-governance-request.yaml`
5. `prompts/01-run-policy-governance-audit.md`
6. `payload/REFERENCE.md`
7. `evidence/EVIDENCE-TEMPLATE.md`

## Required Markers

```text
POLICY_BASELINE_COLLECTED: yes
TOOLGRANTS_AUDITED: yes
FORBIDDEN_TOOLS_BLOCKED: yes
PROD_CHAOS_BLOCKED: yes
GITLAB_WRITE_BOUNDARY_VERIFIED: yes
MEMORY_WRITE_BOUNDARY_VERIFIED: yes
SECRET_LEAK_SCAN_PASSED: yes
POLICY_REPORT_CREATED: yes
OUTPUT_SANITIZED: yes
```

## Definition Of Done

- kagent Agents and ToolGrants are inventoried.
- General triage/front-door agents do not have delete, exec, broad apply, or
  broad GitLab write tools.
- Remediation agents are bounded by namespace, approval route, and workflow or
  GitOps execution.
- Production chaos is blocked by schema, policy, or runtime guard.
- GitLab write access is isolated to a GitOps/documentation specialist with
  scoped project credentials.
- Memory writes are curator-mediated or otherwise restricted.
- Public-safety scan catches secrets, private IPs, internal endpoints, and
  tenant/subscription identifiers in reusable artifacts.
- A short policy report is produced with pass/block/gap status and owners.
