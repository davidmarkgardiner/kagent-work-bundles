---
name: grafana-incident-evidence-pack
description: Build SRE-ready Grafana evidence packs from alert labels, using agent home dashboards for context and incident-specific dashboards for ticket handoff.
---

# Grafana Incident Evidence Pack

Use this skill when an alert, operator question, or agent verdict needs a
focused dashboard and evidence bundle for an SRE. The goal is not to link a
generic dashboard. The goal is to show the exact pod, workload, service,
cluster, logs, metrics, and recovery signal behind the incident.

## Inputs

Start from the alert or event payload. Preserve the raw payload in the issue or
workflow artifact.

Required labels when available:

- `cluster`
- `environment`
- `namespace`
- `pod`
- `container`
- `workload`
- `service`
- `node`
- `alertname`
- `startsAt` / `endsAt`

If the alert is missing one of the labels needed by the selected dashboard, say
that explicitly and fall back to exact PromQL, LogQL, and Kubernetes queries.

## Registry

Use `observability/grafana/dashboard-registry.yaml` as the routing table:

1. Select the agent entry by `agent` or incident domain.
2. Use the agent home dashboard for domain context.
3. Use an evidence dashboard for the SRE ticket.
4. Set every dashboard variable from alert labels.
5. Record missing labels as telemetry debt.

## Workflow

### 1. Scope The Incident

Answer these before remediation:

- Is this one pod, one workload, one namespace, one cluster, or fleet-wide?
- Did it start after a rollout, chaos run, node event, certificate renewal, DNS
  sync, model backend change, or gateway change?
- Is observability itself healthy enough to trust the dashboard?

Fleet scope PromQL examples:

```promql
count by (cluster) (ALERTS{alertname="{{ALERT_NAME}}",alertstate="firing"})
count by (cluster, namespace) (kube_pod_container_status_restarts_total{namespace="{{NAMESPACE}}"} > 0)
count by (cluster, namespace, pod) (kube_pod_status_phase{phase=~"Pending|Failed|Unknown"})
```

### 2. Pick The Dashboard

Use an incident dashboard when the payload identifies a concrete failing object:

- crashing pod: `k8s-pod-crash-evidence`
- service latency: `service-latency-evidence`
- multi-cluster spread: `fleet-scope-evidence`

Use the agent home dashboard only as context:

- cert-manager agent home dashboard for certificate and ACME health
- external-dns agent home dashboard for DNS sync and provider errors
- chaos-triage agent home dashboard for Litmus, Argo, and kagent flow health
- platform-sre agent home dashboards for kagent, agentgateway, and fleet state

### 3. Query Metrics

For a crashing pod, gather at least:

```promql
sum by (cluster, namespace, pod, container) (
  increase(kube_pod_container_status_restarts_total{
    cluster=~"{{CLUSTER_NAME}}",
    namespace="{{NAMESPACE}}",
    pod=~"{{POD}}",
    container=~"{{CONTAINER}}"
  }[{{WINDOW}}])
)

max by (cluster, namespace, pod) (
  kube_pod_status_ready{
    cluster=~"{{CLUSTER_NAME}}",
    namespace="{{NAMESPACE}}",
    pod=~"{{POD}}",
    condition="true"
  }
)

kube_pod_container_status_last_terminated_reason{
  cluster=~"{{CLUSTER_NAME}}",
  namespace="{{NAMESPACE}}",
  pod=~"{{POD}}",
  container=~"{{CONTAINER}}"
}
```

### 4. Query Logs

Use narrow LogQL first:

```logql
{cluster=~"{{CLUSTER_NAME}}", namespace="{{NAMESPACE}}", pod=~"{{POD}}", container=~"{{CONTAINER}}"}
  |~ "panic|fatal|error|exception|oom|killed|back-off|timeout|denied"
```

Then add Kubernetes event logs if collected:

```logql
{cluster=~"{{CLUSTER_NAME}}", namespace="{{NAMESPACE}}"}
  |~ "{{POD}}|BackOff|Killing|Unhealthy|Failed|Started|Pulled|Created"
```

### 5. Build Links

Use Grafana MCP when available:

- `list_datasources`
- `query_prometheus`
- `query_loki_logs`
- `search_dashboards`
- `get_dashboard_panel_queries`
- `generate_deeplink`

Produce:

- focused evidence dashboard link with variables set
- Explore PromQL link
- Explore LogQL link
- source alert or panel link

Do not mutate dashboards from the default triage path. Dashboard writes require
a separate approved workflow and service account.

### 6. Present The SRE Evidence Pack

Return this shape:

```markdown
## Incident
Alert, cluster, namespace, pod/workload, time window.

## Scope
Single pod / workload / cluster / fleet-wide, with evidence.

## Dashboard
Focused evidence dashboard URL and the agent home dashboard URL.

## Metrics
Exact PromQL, short result summary, and why each query matters.

## Logs
Exact LogQL, short result summary, and representative error pattern.

## Kubernetes
Pod state, events, owner deployment or ReplicaSet, and recent rollout state.

## Verdict
One sentence with confidence and uncertainty.

## Decision
observe_only, human_review, or safe_auto_remediate.

## Verification
Same dashboard and queries after remediation, proving recovery or suggesting the next bounded check.
```

## Learning Loop

At closeout, create a follow-up item when evidence was missing or stale:

- missing dashboard variable
- dashboard panel had no data
- labels differed between metrics and logs
- panel query was too broad
- no event/log collection for the affected namespace
- remediation verification lacked a clean recovery signal

The agent may draft the proposed dashboard or registry change, but should not
apply it directly unless running in an approved dashboard-maintenance workflow.
