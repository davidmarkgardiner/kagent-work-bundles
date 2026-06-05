# Shared Grafana Evidence Agent

Use a shared evidence agent instead of embedding dashboard logic into every
domain agent.

## Agent Split

```text
domain triage agent
  -> normalized incident payload plus Kubernetes/AKS observations
  -> grafana-evidence-agent
  -> SRE evidence pack and dashboard links
  -> HITL or remediation workflow
  -> grafana-evidence-agent verifies recovery
```

## Why This Is The Default

Domain agents should be good at their domains:

- `cert-manager-agent` understands certificates, issuers, orders, challenges,
  webhook failures, and renewal semantics.
- `external-dns-agent` understands DNS sync, provider errors, hosted zones, and
  stale records.
- `chaos-triage-agent` understands Litmus results, expected blast radius, and
  controlled remediation.

They should not each carry a full copy of Grafana dashboard selection rules,
query conventions, label fallbacks, and dashboard maintenance behavior. That
would drift quickly.

`grafana-evidence-agent` owns:

- dashboard registry lookup
- Grafana MCP reads
- Prometheus/Mimir queries
- Loki queries
- focused dashboard links
- fleet-scope checks
- remediation verification evidence
- dashboard follow-up suggestions

## Contract

The domain agent sends a normalized payload:

```yaml
agent: cert-manager-agent
alertname: CertManagerCertificateExpiringSoon
cluster: "{{CLUSTER_NAME}}"
environment: "{{ENVIRONMENT}}"
namespace: cert-manager
pod: "{{POD_NAME_OR_UNKNOWN}}"
container: "{{CONTAINER_OR_UNKNOWN}}"
workload: "{{WORKLOAD_OR_UNKNOWN}}"
service: "{{SERVICE_OR_UNKNOWN}}"
node: "{{NODE_OR_UNKNOWN}}"
startsAt: "{{ALERT_START}}"
endsAt: "{{ALERT_END_OR_NOW}}"
suspectedFailureMode: certificate renewal failure
remediationAttempted: none
kubernetesEvidence:
  podStatus: "{{CALLER_OBSERVED_POD_STATUS_OR_UNKNOWN}}"
  recentEvents: "{{CALLER_OBSERVED_EVENTS_OR_UNKNOWN}}"
  logExcerpt: "{{CALLER_OBSERVED_LOG_EXCERPT_OR_UNKNOWN}}"
```

The evidence agent returns:

- focused evidence dashboard link
- agent home dashboard link
- PromQL and LogQL used
- metric and log result summaries
- caller-supplied Kubernetes state and events, plus any missing evidence needed
- fleet impact
- decision recommendation
- verification queries
- dashboard follow-up gaps

## Runtime Ownership

| Agent | Responsibility | Tooling |
| --- | --- | --- |
| Domain triage agent | Understand domain, form hypothesis, propose action. | Kubernetes/domain read tools, optional delegate to evidence agent. |
| `grafana-evidence-agent` | Prove or challenge the hypothesis with telemetry and focused dashboards. | Grafana MCP read tools only. |
| Dashboard maintainer workflow | Update dashboard JSON, registry, or queries after review. | Write-capable Grafana API/MCP account behind approval. |

## Safety

- Domain agents may delegate evidence gathering.
- The evidence agent does not mutate dashboards or Kubernetes resources.
- Dashboard writes happen after the incident through PR or approved workflow.
- If Grafana MCP, Loki, Mimir, or model backend is unhealthy, the evidence agent
  must say which path is degraded and return the best deterministic fallback.

## Repo Artifacts

- Agent manifest:
  `agents/grafana-evidence-agent/agent.yaml`
- Skill:
  `agents/skills/grafana-incident-evidence-pack/SKILL.md`
- Dashboard registry:
  `observability/grafana/dashboard-registry.yaml`
- First focused dashboard:
  `observability/grafana/dashboards/k8s-pod-crash-evidence.json`
- Grafana sidecar provisioning:
  `observability/grafana/kustomization.yaml`
