# Kagent Triage V2 Work-Agent Bundles

Purpose: each folder is a self-contained handoff package for one Kagent triage
v2 capability. Copy a folder into the work-agent context, start at its
`FRONT-SHEET.md`, run its verifier, and then implement or prove the equivalent
capability in the approved work environment.

These bundles are public-safe. They use placeholders for environment-specific
values and must not contain secrets, private hostnames, private IPs, tenant IDs,
subscription IDs, or real tokens.

## Bundle Map

| Bundle | Capability | Primary outcome |
|---|---|---|
| `sre-grafana-mcp-observability/` | Grafana MCP observability | SRE asks a kagent front door to build/verify dashboards, alerts, logs, metrics, and GitOps observability changes |
| `kagent-triage-v2-kb-gitlab-mcp/` | KB + doc2vec/querydoc + GitLab MCP | Agent updates KB docs through GitLab MCP, reindexes querydoc, and proves cited retrieval |
| `gitlab-mcp-gitops-pr/` | GitLab MCP GitOps PRs | Agent creates a branch, updates code/YAML/docs, opens an MR, and leaves it for human review |
| `chaos-reliability-remediation/` | Chaos and remediation proof | SRE requests controlled lower-env chaos, triage, gated remediation, recovery proof, and report |
| `a2a-smart-triage-workflows/` | Agent-to-agent workflows | Coordinator fans out to specialists, preserves context, and produces one synthesized incident answer |
| `memory-mcp-shared-context/` | Memory MCP and shared context | Agents seed, recall, and curate cross-session memory safely |
| `lifecycle-evaluation-review-manager/` | Eval, scorecards, review manager | Runs are scored, hard failures are enforced, and below-threshold cases route to review |
| `byo-kagent-onboarding/` | Bring Your Own Agent | Teams onboard read-only and bounded remediation agents with ToolGrants and policy checks |
| `hitl-remediation-approval/` | Human-in-the-loop remediation | Non-read-only actions suspend, require approval, and resume with recorded identity |
| `aks-fleet-reporting-day2/` | AKS fleet reporting and day-2 ops | Platform gets repeatable fleet inventory, health, dashboards, and day-to-day reporting |

## Recommended Work Order

1. `sre-grafana-mcp-observability/`
2. `kagent-triage-v2-kb-gitlab-mcp/`
3. `gitlab-mcp-gitops-pr/`
4. `a2a-smart-triage-workflows/`
5. `chaos-reliability-remediation/`
6. `lifecycle-evaluation-review-manager/`
7. `hitl-remediation-approval/`
8. `memory-mcp-shared-context/`
9. `byo-kagent-onboarding/`
10. `aks-fleet-reporting-day2/`

## Local Verification

Run all bundle verifiers:

```bash
bash scripts/verify-all-bundles.sh
```

Or run a single bundle verifier from inside that bundle:

```bash
bash scripts/verify-bundle.sh
```

Static verification proves the handoff package is internally consistent. It
does not prove live work-lab GitLab, Grafana, querydoc, kagent, Argo, chaos,
memory, or cluster behavior.
