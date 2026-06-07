# Policy Governance Safety

## TL;DR

Audits the safety controls around agents, tools, chaos, GitLab writes, memory
writes, and public-safe output before the platform is treated as production
ready.

## What This Feature Does

- Inventories agents, ToolGrants, and MCP tool lists.
- Blocks dangerous front-door tools.
- Verifies production chaos is denied.
- Verifies GitLab write access is scoped.
- Verifies memory writes are curated.
- Produces a sanitized governance report.

## Evidence To Produce

- Agent and ToolGrant inventory.
- Forbidden-tool audit result.
- Production-chaos denial proof.
- GitLab write boundary proof.
- Memory write boundary proof.
- Secret/public-safety scan result.

## How To Run

1. Run `bash scripts/verify-bundle.sh`.
2. Use `WORK-AGENT-START-PROMPT.md`.
3. Fill in `requests/policy-governance-request.yaml`.
4. Capture evidence with `evidence/EVIDENCE-TEMPLATE.md`.

## Definition Of Done

Actual discovered tools, not labels or descriptions, prove that general agents
cannot mutate broadly and specialist write paths are gated and scoped.
