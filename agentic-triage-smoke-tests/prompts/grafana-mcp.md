# Tier 2 Grafana MCP and AKS MCP Triage POC

## Verified Status

The metadata-only investigation described below was live-tested on 2026-07-10.
A dedicated kagent Agent used Grafana MCP to query Loki and read-only AKS MCP to
query compact pod state, exact pod events, and bounded container logs. The
final investigation subscore was 7/7.

Reusable assets:

```text
../examples/kagent/tier-two-mcp-triage-agent.yaml
../examples/kagent/aks-mcp-readonly-values.yaml
../examples/kagent/grafana-mcp-host-validation-values.yaml
../evidence/PROXMOX-TIER-TWO-MCP-TRIAGE-2026-07-10.md
```

The automatic handoff is also proven in
`../evidence/PROXMOX-TIER-TWO-KAFKA-E2E-2026-07-10.md`:

```text
Grafana -> Vector webhook -> Kafka -> Argo EventSource/Sensor
-> Tier 2 Workflow -> kagent -> Grafana MCP + AKS MCP -> 7/7
```

Use the dedicated periodic WorkflowTemplate rather than launching the full
specialist fan-out and HITL workflow for every health check.

The objective is **not** to build a production system, but to answer one question:

> **Can an AI triage agent investigate a Kubernetes alert using MCP tools instead of requiring Alertmanager to carry logs and events?**

---

````markdown
# AI Incident Triage POC (Alertmanager → Kafka → MCP Investigation)

## Objective

Prove that Alertmanager only needs to send lightweight alert metadata.

Instead of enriching alerts before Kafka, the AI triage agent will use MCP servers to investigate the incident on demand.

This validates an "agentic observability" architecture.

---

# High Level Architecture

                    ┌─────────────┐
                    │ Kubernetes  │
                    └──────┬──────┘
                           │
             Logs          │ Metrics
                           │
                    ┌──────▼──────┐
                    │ Grafana      │
                    │ LGTM Stack   │
                    │              │
                    │ Loki         │
                    │ Mimir        │
                    │ Tempo        │
                    └──────┬───────┘
                           │
                      Alert Rules
                           │
                    ┌──────▼──────┐
                    │Alertmanager │
                    └──────┬──────┘
                           │ Webhook
                           ▼
                        Vector
                           │
                           ▼
                        Kafka
                           │
                           ▼
                AI Triage Agent
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
         ▼                 ▼                 ▼
     Grafana MCP      Kubernetes MCP     Git MCP
         │
         ▼
    Loki / Metrics / Tempo

---

# Goal

When an alert fires:

DO NOT embed:

- logs
- Kubernetes events
- traces

Instead send only enough metadata for the AI agent to investigate.

Example payload:

```json
{
  "alert": "CrashLoopBackOff",
  "cluster": "homelab",
  "namespace": "demo",
  "pod": "demo-api-7b56d",
  "container": "api",
  "severity": "critical",
  "timestamp": "..."
}
```

---

# Success Criteria

The AI agent should be able to answer:

- Why did the alert fire?
- What logs caused it?
- Were there Kubernetes Events?
- Was there a deployment?
- Is this a known issue?
- What is the likely root cause?
- What remediation should be performed?

WITHOUT receiving any log lines inside the Alertmanager payload.

---

# Environment

Local Kubernetes Cluster

Examples:

- k3d
- kind
- k3s
- MicroK8s

Required components:

- Grafana
- Loki
- Mimir or Prometheus
- Tempo (optional)
- Alertmanager
- Vector
- Kafka
- AI Agent

---

# Step 1

Deploy LGTM.

Verify:

✓ Logs visible in Loki

✓ Metrics visible

✓ Alertmanager operational

---

# Step 2

Deploy a sample application.

Requirements:

- emits logs
- exposes metrics

Examples:

- nginx
- podinfo
- demo Go app

---

# Step 3

Create a failure.

Examples:

CrashLoopBackOff

OOMKilled

ImagePullBackOff

HTTP 500

Failed Readiness Probe

CPU saturation

Memory exhaustion

---

# Step 4

Create Loki alert.

Example:

More than N ERROR logs over five minutes.

Alert payload should only include:

- cluster
- namespace
- pod
- deployment
- container

No log messages.

---

# Step 5

Alertmanager

Configure webhook receiver.

Send alerts to Vector.

---

# Step 6

Vector

Receive webhook.

Forward JSON to Kafka unchanged.

No enrichment.

---

# Step 7

Kafka

Verify message arrives.

Expected message should remain lightweight.

---

# Step 8

AI Triage Agent

Consume Kafka message.

This is where investigation begins.

Agent receives:

Cluster

Namespace

Pod

Container

Timestamp

Alert Name

Severity

Nothing else.

---

# Step 9

Agent Investigation

The agent should call MCP tools.

Example reasoning flow:

1.

Get pod details.

2.

Query Loki:

Logs for:

cluster=X

namespace=Y

pod=Z

Previous 15 minutes.

3.

Query Kubernetes Events.

4.

Query Metrics.

CPU

Memory

Restarts

5.

Query Tempo.

If trace IDs exist.

6.

Determine root cause.

---

# Example Investigation

Alert:

CrashLoopBackOff

↓

Get pod

↓

Get Events

↓

Found:

OOMKilled

↓

Get logs

↓

Found:

Java heap exhausted

↓

Metrics:

Memory reached limit

↓

Conclusion:

Application exceeded memory limit after deployment.

Recommended action:

Increase memory limit or investigate memory leak.

---

# Expected Final Output

The agent should produce something similar to:

Summary

The pod entered CrashLoopBackOff after exceeding its memory limit.

Evidence

• Kubernetes Event:
  OOMKilled

• Restart Count:
  12

• Memory reached 512Mi limit

• Last logs:

java.lang.OutOfMemoryError

Recommendation

Increase memory request/limit or investigate recent deployment.

Confidence

96%

---

# Things To Validate

Can the agent retrieve logs using only metadata?

Can the agent retrieve Kubernetes Events?

Can the agent correlate logs and Events?

Can the agent investigate without embedded logs?

How long does the investigation take?

How many MCP calls are required?

---

# Stretch Goals

Add Tempo lookup.

Add GitHub lookup.

Determine last deployment.

Determine commit SHA.

Determine ArgoCD sync.

Determine node health.

Generate RCA automatically.

Suggest remediation.

Automatically open GitHub issue.

Automatically create Jira ticket.

Automatically restart workload (optional).

---

# Success Definition

This POC is successful if:

✓ Alertmanager sends only metadata.

✓ Kafka messages remain small.

✓ AI agent retrieves all required evidence through MCP.

✓ Root cause can be determined without log enrichment.

✓ The architecture demonstrates that Alertmanager does not need to transport logs or Kubernetes events.
````

I think this is a strong direction because it shifts the responsibility for gathering evidence from the alerting pipeline to the investigator. In effect, the alert becomes a **case file identifier**, and the AI agent behaves like an SRE: it uses the identifiers in the alert to fetch the relevant logs, Kubernetes events, metrics, traces, deployment history, and any other evidence it needs before producing a diagnosis. That separation keeps the observability pipeline simple while making the investigation logic far more flexible and extensible.
