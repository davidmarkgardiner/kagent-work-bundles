# Kagent Triage V2 Work-Agent Bundles

Purpose: each folder is a self-contained handoff package for one Kagent triage
v2 capability. Copy a folder into the work-agent context, start at its
`FRONT-SHEET.md`, run its verifier, and then implement or prove the equivalent
capability in the approved work environment.

These bundles are public-safe. They use placeholders for environment-specific
values and must not contain secrets, private hostnames, private IPs, tenant IDs,
subscription IDs, or real tokens.

Before live implementation, fill in
[`SHARED-VARIABLES.md`](SHARED-VARIABLES.md) inside the approved work context.
That sheet lists the common namespaces, MCP server names, datasource UIDs,
GitLab project values, approval routes, and demo targets needed across bundles.

## Bundle Map

Each bundle now has the same human handover layer:

```text
README.md        - TL;DR, what the feature does, evidence, run path
GITLAB-TICKET.md - copyable GitLab issue for the work team
VISUAL.html      - lightweight stakeholder/SRE workflow visual
```

| Bundle | Capability | Primary outcome |
|---|---|---|
| `team-handover-pack/` | Human handover, tickets, Teams messages, game-day planning | Provides GitLab ticket templates, Teams messages, game-day plan, and an HTML presentation for SRE/stakeholder handover |
| `runtime-model-gateway-readiness/` | Runtime, model, Agent Gateway, A2A, and MCP preflight | Proves model backend, Agent Gateway, A2A, and required MCP servers are live before downstream demos |
| `sre-grafana-mcp-observability/` | Grafana MCP observability | SRE asks a kagent front door to build/verify dashboards, alerts, logs, metrics, and GitOps observability changes |
| `grafana-kafka-alert-verification/` | Grafana Alerting to Kafka verification | Proves real Grafana alert firing, consumes the Confluent Kafka record, captures payload shape, and records the schema validation decision |
| `agentic-triage-smoke-tests/` | Agentic triage smoke tests | Proves metrics, logs, events, traces or trace fallback, agent correctness, and Grafana health after a new install |
| `sre-adoption-feedback-loop/` | SRE adoption and feedback loop | SRE onboards one app, uses/reviews the workflow, captures feedback, routes improvements, and reports adoption |
| `kagent-triage-v2-kb-gitlab-mcp/` | KB + doc2vec/querydoc + GitLab MCP | Agent updates KB docs through GitLab MCP, reindexes querydoc, and proves cited retrieval |
| `gitlab-mcp-gitops-pr/` | GitLab MCP GitOps PRs | Agent creates a branch, updates code/YAML/docs, opens an MR, and leaves it for human review |
| `chaos-reliability-remediation/` | Chaos and remediation proof | SRE requests controlled lower-env chaos, triage, gated remediation, recovery proof, and report |
| `a2a-smart-triage-workflows/` | Agent-to-agent workflows | Coordinator fans out to specialists, preserves context, and produces one synthesized incident answer |
| `memory-mcp-shared-context/` | Memory MCP and shared context | Agents seed, recall, and curate cross-session memory safely |
| `lifecycle-evaluation-review-manager/` | Eval, scorecards, review manager | Runs are scored, hard failures are enforced, and below-threshold cases route to review |
| `byo-kagent-onboarding/` | Bring Your Own Agent | Teams onboard read-only and bounded remediation agents with ToolGrants and policy checks |
| `hitl-remediation-approval/` | Human-in-the-loop remediation | Non-read-only actions suspend, require approval, and resume with recorded identity |
| `policy-governance-safety/` | Policy and governance safety | Audits ToolGrants, dangerous tools, production-chaos blocks, GitLab write boundaries, memory write boundaries, and public-safe output |
| `incident-evidence-trace-log-metrics/` | Trace, log, and metric evidence packs | Builds source-backed incident evidence from Grafana MCP metrics, logs, traces or trace fallback, dashboards, and triage synthesis |
| `aks-fleet-reporting-day2/` | AKS fleet reporting and day-2 ops | Platform gets repeatable fleet inventory, health, dashboards, and day-to-day reporting |

## Recommended Work Order

1. `team-handover-pack/`
2. `runtime-model-gateway-readiness/` - stop here and fix blockers before live fanout, chaos, GitOps PR, or SRE demo sessions
3. `sre-grafana-mcp-observability/`
4. `grafana-kafka-alert-verification/`
5. `agentic-triage-smoke-tests/`
6. `sre-adoption-feedback-loop/`
7. `kagent-triage-v2-kb-gitlab-mcp/`
8. `gitlab-mcp-gitops-pr/`
9. `a2a-smart-triage-workflows/`
10. `chaos-reliability-remediation/`
11. `lifecycle-evaluation-review-manager/`
12. `hitl-remediation-approval/`
13. `policy-governance-safety/`
14. `incident-evidence-trace-log-metrics/`
15. `memory-mcp-shared-context/`
16. `byo-kagent-onboarding/`
17. `aks-fleet-reporting-day2/`

## Future Bundle Ideas

These are useful concepts to preserve, but they are not yet dedicated
`work-agent-bundles/` folders. Treat them as backlog candidates, not verified
handoff packages.

| Idea | Why it matters | Likely source material |
|---|---|---|
| Alert ingestion and dedup | Proves Alertmanager or Grafana alert ingestion through Argo Events into smart triage, including duplicate suppression and replay safety. | `a2a/smart-triage-fanout-demo/sensors/`, `SMART-TRIAGE-FANOUT-LIVE-EVIDENCE.md` |
| AKS-MCP and Kubernetes day-to-day operations | Separates normal cluster/workload debugging through AKS-MCP or Kubernetes tools from fleet reporting and chaos workflows. | `platform/aks-mcp/`, `agents/kagent-triage/` |
| Deployment-state and GitOps context | Maps workload to Helm/Flux/GitLab release context, recent MRs, rollout history, and safe rollback or config PR proposals. | `a2a/smart-triage-fanout-demo/mapping/`, GitLab MCP bundles |
| Agentgateway/model capacity and failover | Covers Qwen capacity sweeps, workflow-level rate limiting, retry/failover policy, and model saturation alerting. | `platform/agentgateway/work-qwen-primary-gpt4-failover-handoff/` |
| Ticket/report closure workflow | Updates GitLab/Jira/issues with evidence, attaches eval output, and blocks closure when lifecycle score or hard gates fail. | GitLab MCP bundle, lifecycle evaluation bundle |
| Fleet scheduling and randomized game-day selection | Chooses a bounded set of clusters/apps under policy and runs controlled reliability checks with auditable selection. | `agents/skills/fleet-selector/`, `chaos/reliability/` |

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

## Peer Review

Before giving the bundle set to a work-side implementation agent, hand
[`PEER-REVIEW-PROMPT.md`](PEER-REVIEW-PROMPT.md) to a separate review agent.
That reviewer should check handover clarity, required variables, token
efficiency, safety boundaries, and missing concepts without claiming live proof.
