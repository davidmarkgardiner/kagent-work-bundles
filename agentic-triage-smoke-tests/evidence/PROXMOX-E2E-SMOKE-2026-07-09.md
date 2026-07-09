# Proxmox End-To-End Smoke Evidence - 2026-07-09

## Verdict

`red`

The real Grafana alert path worked end to end through alert delivery and Argo
workflow creation, but the agentic triage workflow failed because the model
backend behind agentgateway returned `502 ollama upstream failed`.

## Runtime

| Field | Value |
|---|---|
| Cluster context | `{{CLUSTER_NAME}}` |
| Smoke namespace | `agentic-triage-smoke` |
| Smoke workload | `podinfo-smoke-crashloop` |
| Run ID | `triage-smoke-20260709083506-crashloop` |
| Grafana rule UID | `ats-083737` |
| Workflow | `smart-triage-alert-7cw9c` |

## Failure Scenario

Created a dedicated smoke namespace and a crash-looping workload from:

```text
work-agent-bundles/agentic-triage-smoke-tests/examples/k8s/crashloop-smoke-target.yaml
```

Observed proof:

```text
podinfo-smoke-crashloop ... 0/1 Error
AGENTIC_TRIAGE_SMOKE_ERROR run_id=triage-smoke-20260709083506-crashloop failure=crashloop
Kubernetes event reason: BackOff
```

Prometheus proof:

```text
kube_pod_container_status_terminated_reason{namespace="agentic-triage-smoke",reason="Error"} == 1
```

## Grafana Alert Setup

Created a temporary Grafana webhook contact point:

```text
agentic-triage-smart-triage-webhook
```

The contact point posted to the smart-triage Argo Events EventSource:

```text
http://{{SMART_TRIAGE_EVENTSOURCE_SERVICE}}.{{ARGO_EVENTS_NAMESPACE}}.svc.cluster.local:12000/alerts
```

Created a temporary Grafana alert rule:

```text
title: Agentic Triage Smoke CrashLoop triage-smoke-20260709083506-crashloop
datasource: prometheus
query: kube_pod_container_status_terminated_reason{namespace="agentic-triage-smoke",reason="Error"}
receiver: agentic-triage-smart-triage-webhook
```

Grafana state proof:

```text
state: Alerting
value: 1
labels:
  cluster: {{CLUSTER_NAME}}
  namespace: agentic-triage-smoke
  workload: podinfo-smoke-crashloop
  pod: podinfo-smoke-crashloop-...
  container: podinfo-smoke
  reason: Error
  run_id: triage-smoke-20260709083506-crashloop
```

## Webhook And Argo Evidence

EventSource log:

```text
a request received, processing it...
endpoint="/alerts"
Succeeded to publish an event
successfully dispatched the request to the event bus
```

Sensor log:

```text
creating the object...
Successfully processed trigger 'smart-triage-fanout-workflow'
triggeredBy=["alertmanager-alert"]
```

Workflow created:

```text
smart-triage-alert-7cw9c
```

Normalize step proof:

```text
SMART_TRIAGE_FANOUT: started
ALERT_INGESTED: yes
ALERT_SOURCE: alertmanager
INCIDENT_NORMALIZED: yes
ALERT_DUPLICATE: no
ALERT_NAME: Agentic Triage Smoke CrashLoop triage-smoke-20260709083506-crashloop
CLUSTER: {{CLUSTER_NAME}}
NAMESPACE: agentic-triage-smoke
WORKLOAD: podinfo-smoke-crashloop
POD: podinfo-smoke-crashloop-...
CONTAINER: podinfo-smoke
FINGERPRINT: 92e507f673a928b9
```

## Failure Found

All smart-triage specialist fan-out steps failed:

```text
A2A state: failed
Error code: 502 - {'error': {'message': 'ollama upstream failed', 'detail': '<urlopen error [Errno 111] Connection refused>'}}
```

Direct agentgateway probe confirmed the same failure:

```text
POST /qwen/v1/chat/completions
HTTP 502
ollama upstream failed
```

KubeAI model state:

```text
model/qwen3-14b status.replicas.ready: 0
model pod: Running, Ready=false
```

Earlier failed model pod admission reason:

```text
Allocate failed due to no healthy devices present; cannot allocate unhealthy devices nvidia.com/gpu
```

The failed model pod was deleted so KubeAI could recreate it. The replacement
pod started and began downloading the model, but did not become Ready during
the smoke window.

## Cleanup

Removed temporary resources created for this smoke:

```text
Grafana alert rule ats-083737: deleted
Grafana contact point agentic-triage-smart-triage-webhook: deleted
namespace agentic-triage-smoke: deleted
```

Left the recreated `qwen3-14b` model pod running so the platform can finish
model startup if the download succeeds.

## Evidence Files

Local evidence snapshot:

```text
/tmp/agentic-triage-smoke/
```

Important files:

```text
grafana-alert-state.json
eventsource.log
sensor.log
workflow-smart-triage-alert-7cw9c.yaml
workflow-smart-triage-alert-7cw9c.logs
proxmox-agent-gw-direct.meta
proxmox-agent-gw-direct.body
proxmox-agent-gw-direct-after-recreate.meta
proxmox-agent-gw-direct-after-recreate.body
```

## Next Gate

Do not run the full metrics/logs/events/traces matrix until:

```text
agentgateway direct model call: HTTP 200
single A2A request: state_counts=completed:1
```

After the model is Ready, rerun with a fresh `run_id` so the smart-triage dedup
cache does not suppress the alert.
