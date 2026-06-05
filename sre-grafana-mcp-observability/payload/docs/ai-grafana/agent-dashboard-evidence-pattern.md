# Agent Dashboards And Incident Evidence Packs

This pattern separates two related dashboard jobs and assigns them to a shared
evidence agent:

1. **Agent home dashboards** show domain health for the agent.
2. **Incident evidence dashboards** show the exact failure the SRE is being
   asked to review.

Do not use a broad platform dashboard as the primary ticket link unless its
variables are set to the affected alert labels.

## Why This Matters

An agent needs enough context to answer:

- Is this one pod, one workload, one cluster, or fleet-wide?
- Is the alert related to a known domain, such as cert-manager, external-dns,
  chaos testing, Agent Gateway, or a model backend?
- Is the remediation verified by the same metrics and logs used for diagnosis?

An SRE needs a narrower view:

- this pod is crashing
- this log line explains the crash
- this event shows the lifecycle failure
- this metric shows restart, downtime, or readiness
- this dashboard proves the fix worked

## Dashboard Types

### Agent Home Dashboard

Stable, long-lived, owned by the agent/domain team.

Examples:

- `cert-manager-agent`: certificate expiry, failed renewals, ACME challenges,
  issuer readiness, webhook health.
- `external-dns-agent`: desired vs actual records, provider API errors, sync
  duration, stale records, zone failures.
- `chaos-triage-agent`: Litmus results, Argo workflow state, kagent/A2A health,
  model backend health.
- `platform-sre-agent`: fleet alert spread, kagent health, Agent Gateway
  traffic, model backend status, workflow failure rates.

Use home dashboards for context, trend, and fleet blast-radius checks.

### Incident Evidence Dashboard

Short path from an alert to SRE decision. It is selected from the alert labels
and rendered with variables already set.

For a crashing pod, the evidence dashboard should show:

- cluster, namespace, pod, and container
- restart increase during the incident window
- readiness and uptime/downturn timeline
- last termination and current waiting reason
- previous/current logs around the failure window
- Kubernetes events for the affected pod
- node or resource pressure when relevant
- verification after remediation

The first concrete template is:

- `observability/grafana/dashboards/k8s-pod-crash-evidence.json`

## Registry

Agents should use:

- `observability/grafana/dashboard-registry.yaml`

The registry maps:

- agent name
- home dashboards
- evidence dashboards
- required variables
- useful signals
- learning queue labels

This lets the agent route a cert-manager alert to cert-manager context, while
still generating a focused incident dashboard when a specific pod, service, or
cluster is affected.

## Shared Evidence Agent

Domain agents should delegate dashboard evidence to
`grafana-evidence-agent`. The domain agent owns the hypothesis; the evidence
agent owns Grafana MCP queries, dashboard selection, fleet scope, and
verification.

```text
domain triage agent
  -> normalized incident payload
  -> grafana-evidence-agent
  -> focused dashboard, PromQL, LogQL, Kubernetes evidence, verification
```

See `shared-grafana-evidence-agent.md` for the handoff contract.

## Evidence Pack Flow

```text
alert payload
  -> extract labels and time window
  -> select agent/domain from dashboard registry
  -> inspect agent home dashboard for domain context
  -> select incident evidence dashboard
  -> set dashboard variables from alert labels
  -> query Prometheus/Mimir and Loki through Grafana MCP
  -> inspect Kubernetes state and events
  -> write SRE evidence pack
  -> after remediation, rerun the same dashboard and queries
```

## Ticket Contract

Every ticket update should contain:

```markdown
## Incident
Alert, cluster, namespace, pod/workload, and time window.

## Scope
Single pod / workload / cluster / fleet-wide, with evidence.

## Dashboard
Focused evidence dashboard link and agent home dashboard link.

## Metrics
Exact PromQL and summary.

## Logs
Exact LogQL and summary.

## Kubernetes
Pod state, deployment/ReplicaSet owner, events, and recent rollout state.

## Verdict
One sentence with confidence and uncertainty.

## Decision
observe_only, human_review, or safe_auto_remediate.

## Verification
Same dashboard and queries after remediation.
```

## Learning Loop

Agents should record dashboard gaps, but they should not silently rewrite
dashboards during incident triage.

Create a dashboard follow-up when:

- an alert is missing labels required by the evidence dashboard
- a panel returns no data for a known active incident
- metrics and logs use different label names
- the panel query is too broad for an SRE ticket
- the dashboard cannot prove remediation worked
- a new recurring incident type needs its own evidence dashboard

The default path is:

```text
incident closeout
  -> dashboard gap noted in evidence pack
  -> issue or PR drafted with query/dashboard change
  -> dashboard QA skill validates panels through Grafana MCP
  -> approved workflow publishes dashboard JSON
```

## Skills

Use:

- `agents/skills/grafana-incident-evidence-pack/SKILL.md`
- `agents/skills/grafana-chaos-incident-triage/SKILL.md`

The first skill handles generic dashboard routing and evidence pack generation.
The second skill handles the chaos/Litmus-specific path used by the iteration
review demo.
