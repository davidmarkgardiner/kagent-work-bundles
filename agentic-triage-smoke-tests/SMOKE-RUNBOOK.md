# Agentic Triage Smoke Runbook

## 0. Guardrails

Run only against an approved non-production target. Do not mutate production
workloads. Use `dry_run: "true"` for any chaos or remediation path until HITL,
GitOps review, and rollback evidence are proven in the work environment.

Use one correlation ID for each run:

```text
run_id=triage-smoke-{{YYYYMMDDHHMMSS}}-{{SHORT_TARGET}}
fingerprint={{RUN_ID}}-{{SMOKE_NAME}}
```

The same `run_id` must appear in the alert payload, Argo Workflow labels,
kagent output, lifecycle eval result, dashboard metric labels, and evidence
template.

## 1. Runtime Readiness

Run the existing cluster gate first:

```bash
cat work-agent-bundles/kagent-agentic-cluster-smoke-tests.md
```

Minimum pass before alert smoke:

```text
agentgateway direct model call: HTTP 200
A2A single request: status_counts=200:1, state_counts=completed:1
fleet dashboard: kagent_agent_ready visible for the smoke agent
```

Do not continue to Grafana alert smoke if the direct model or single A2A gate
fails.

## 2. Confirm Alert Transport

Before applying smoke targets or alerts, write down the active transport:

```text
direct = Grafana/Alertmanager -> smart-triage EventSource -> Sensor -> Workflow
vector_kafka = Grafana/Alertmanager -> Vector -> Kafka -> Kafka EventSource/consumer -> Sensor -> Workflow
```

For `vector_kafka`, prove the plumbing is ready with read-only checks:

```text
Vector webhook receiver exists and is reachable from Grafana/Alertmanager.
Vector transform preserves run_id/fingerprint/source_type/namespace/workload.
Kafka topic exists and receives a test or prior alert message.
Kafka EventSource or consumer is Ready.
Sensor is bound to the Kafka EventSource/consumer.
WorkflowTemplate is present and creatable by the Sensor service account.
```

Do not create Grafana alerts until the transport is known. If the path is
Vector/Kafka but only the direct smart-triage webhook is configured, stop and
report the route mismatch.

## 3. Image Registry Preflight

Before applying any example pod manifest, confirm whether public image pulls
are allowed. If the cluster requires a local registry or mirror, replace the
example images before applying:

```text
busybox:1.36 -> {{LOCAL_REGISTRY}}/busybox:1.36
registry.k8s.io/pause:3.10 -> {{LOCAL_REGISTRY}}/pause:3.10
```

Record:

```text
image_pull_policy
final image names
whether image pull succeeded
```

## 4. Install Or Confirm Alert Path

Use the smart-triage alert ingestion path:

```bash
kubectl apply -f a2a/smart-triage-fanout-demo/workflow-template.yaml
kubectl apply -f a2a/smart-triage-fanout-demo/sensors/sensor-submit-rbac.yaml
kubectl apply -f a2a/smart-triage-fanout-demo/sensors/eventsource-alertmanager.yaml
kubectl apply -f a2a/smart-triage-fanout-demo/sensors/alertmanager-to-fanout-sensor.yaml
```

Expected proof:

```text
EventSource Ready
Sensor Ready
WorkflowTemplate present
Argo can create one workflow in {{ARGO_NAMESPACE}}
```

## 5. Run Source-Type Smokes

Use `SOURCE-TYPE-ALERT-EXAMPLES.md` for the exact Grafana rule shape, fallback
Alertmanager payload, and proof markers for each source type.

### Metrics: CrashLoop Or Restart Alert

Preferred live trigger:

- deploy the smoke target with a deliberate bad env var or failing command;
- let the existing Grafana/Prometheus pod restart alert fire;
- route only the smoke contact point to the new server.

Replay fallback:

```bash
work-agent-bundles/agentic-triage-smoke-tests/scripts/replay-alert-payload.sh \
  work-agent-bundles/agentic-triage-smoke-tests/examples/alertmanager-payloads/metric-crashloop.json
```

Required markers:

```text
ALERT_INGESTED: yes
INCIDENT_NORMALIZED: yes
SPECIALIST_KUBERNETES: completed
SPECIALIST_GRAFANA: completed
INCIDENT_SYNTHESIS: completed
SMART_TRIAGE_PATTERN: proven
```

### Metrics: CPU Or Memory Pressure

Use a bounded stress command only in the smoke namespace. Pass condition is not
self-heal by default; it is correct triage with source-backed PromQL evidence
and no unsafe mutation.

Required evidence:

```text
PromQL query used
panel or dashboard link
agent conclusion: observe_only | scale_via_gitops | limit_request_fix
```

### Logs: Error Burst

Generate known error log lines from the smoke target or sidecar. Configure a
temporary Loki alert or replay a Grafana alert that carries `source=logs`.

Required evidence:

```text
LogQL query used
sample log timestamp range
agent cites log evidence
agent does not claim Kubernetes restarts unless metrics/events support it
```

Replay fallback:

```bash
work-agent-bundles/agentic-triage-smoke-tests/scripts/replay-alert-payload.sh \
  work-agent-bundles/agentic-triage-smoke-tests/examples/alertmanager-payloads/log-errorburst.json
```

### Events: Kubernetes Warning Event

Trigger one of:

- image pull failure in the smoke namespace;
- failed scheduling with a controlled impossible node selector;
- quota-limited pod creation.

Required evidence:

```text
event_reason present
event_context present
namespace/workload labels preserved
suggested kubectl command is namespace-scoped
```

Replay fallback:

```bash
work-agent-bundles/agentic-triage-smoke-tests/scripts/replay-alert-payload.sh \
  work-agent-bundles/agentic-triage-smoke-tests/examples/alertmanager-payloads/event-failedscheduling.json
```

### Traces: Tempo Or Explicit Fallback

If Grafana has Tempo and the smoke app emits trace IDs, trigger a high-latency
span and include the trace ID in the alert annotations. If not, the smoke still
passes only when the trace specialist says trace data is unavailable without
inventing it.

Required evidence:

```text
trace_id and Tempo deeplink
or
TRACE_FALLBACK: NO_TRACE
```

Replay fallback:

```bash
work-agent-bundles/agentic-triage-smoke-tests/scripts/replay-alert-payload.sh \
  work-agent-bundles/agentic-triage-smoke-tests/examples/alertmanager-payloads/trace-latency.json
```

### Dedup Replay

Replay the same fingerprint twice:

```bash
ALERT_FINGERPRINT="{{RUN_ID}}-dedup-replay" \
  a2a/smart-triage-fanout-demo/scripts/replay-alert.sh

ALERT_FINGERPRINT="{{RUN_ID}}-dedup-replay" \
  a2a/smart-triage-fanout-demo/scripts/replay-alert.sh
```

Expected second-run markers:

```text
ALERT_DUPLICATE: yes
DUPLICATE_SUPPRESSED: yes
FANOUT_SKIPPED: duplicate_alert
```

## 6. Verify The Agent Did The Job

First score the smoke readiness gate. This proves the real alert path and agent
completion before deeper remediation lifecycle checks:

```bash
python3 work-agent-bundles/agentic-triage-smoke-tests/scripts/score-smoke-run.py \
  --run "{{SMOKE_RUN_JSON}}" \
  --output-dir "{{SMOKE_SCORE_OUTPUT_DIR}}"
```

Pass condition:

```text
agentic_triage_smoke_score >= 0.85
agentic_triage_smoke_passed = 1
agentic_triage_smoke_hard_failures = 0
```

For remediation/self-heal smoke tests, collect the workflow and run evidence,
then score the full lifecycle:

```bash
python3 observability/agent-evals/scripts/score-lifecycle-run.py \
  --case observability/agent-evals/lifecycle-cases/pod-crashloop-hitl-remediation.yaml \
  --run "{{CAPTURED_LIFECYCLE_RUN_JSON}}" \
  --output-dir "{{EVAL_OUTPUT_DIR}}"
```

Pass condition:

```text
agent_lifecycle_eval_passed = 1
agent_lifecycle_eval_hard_failures = 0
agent_lifecycle_eval_score >= 0.85
```

Hard fail if any of these are true:

- alert did not create a run;
- run did not complete;
- output lacks source-backed metrics/logs/events/trace-or-fallback evidence;
- namespace or workload is wrong;
- read-only smoke attempted mutation;
- remediation executed before HITL/GitOps approval;
- public-safety placeholders were replaced in repo artifacts.

## 7. Verify Grafana Shows Health And Failure

Import or verify the stack-health dashboard:

```text
examples/grafana/agentic-triage-stack-health-dashboard.json
```

The dashboard is intentionally datasource-variable based. Replace datasource
variables at import time instead of hardcoding UIDs in the bundle.

The fleet dashboard must show:

```promql
sum(kagent_agent_ready{cluster="{{CLUSTER_NAME}}"})
sum(increase(kagent_incident_received_total{run_id="{{RUN_ID}}"}[2h]))
sum(increase(kagent_incident_triaged_total{run_id="{{RUN_ID}}"}[2h]))
sum(agent_lifecycle_eval_score{run_id="{{RUN_ID}}"}) * 10
sum(agent_lifecycle_eval_hard_failures{run_id="{{RUN_ID}}"})
```

Run one negative smoke by publishing or preserving a below-threshold eval result
for the smoke run. Pass condition:

```text
KagentLifecycleEvalScoreLow fires for low score
or
KagentLifecycleEvalHardFailure fires for hard failure
dashboard hard-failure panel shows the run_id
```

## 8. Periodic Dev-Cluster Mode

For scheduled verification, split the suite into fast health checks and slower
fault checks. The fast checks prove that the stack is alive. The fault checks
prove that real problem signals still reach the agents and are scored.

### Suggested Cadence

| Cadence | Test | Failure blast radius | Required pass signal |
|---|---|---:|---|
| 15 minutes | agentgateway direct model call | none | HTTP 200 and token usage returned |
| 15 minutes | kagent single A2A request | none | A2A `state=completed` |
| 15 minutes | dashboard freshness query | none | latest smoke/eval metric age below threshold |
| Daily | Grafana webhook replay | none | workflow created, normalized, and completed |
| Daily | real metrics alert on smoke workload | low | `agentic_triage_smoke_score >= 0.85` |
| Weekly | controlled pod fault on rotating dev target | medium | lifecycle eval passes after HITL/GitOps boundary |
| Monthly | full source matrix | medium | metrics, logs, events, and trace-or-fallback covered |

### Periodic Run Contract

Each scheduled run must emit a compact result object with these fields:

```json
{
  "run_id": "{{RUN_ID}}",
  "cluster": "{{CLUSTER_NAME}}",
  "env_tier": "dev",
  "target": "{{TARGET_WORKLOAD}}",
  "profile": "quick|daily|weekly|full-source",
  "started_at": "{{ISO8601}}",
  "completed_at": "{{ISO8601}}",
  "score": 1.0,
  "passed": true,
  "hard_failures": [],
  "source_coverage": {
    "metrics": "proven",
    "logs": "proven|not_run|unsupported",
    "events": "proven|not_run|unsupported",
    "traces": "proven|fallback|not_run|unsupported"
  }
}
```

Publish the result as Prometheus/Mimir metrics:

```prometheus
agentic_triage_smoke_score{cluster,env_tier,target,profile,run_id}
agentic_triage_smoke_passed{cluster,env_tier,target,profile,run_id}
agentic_triage_smoke_hard_failures{cluster,env_tier,target,profile,run_id}
agentic_triage_smoke_last_success_timestamp_seconds{cluster,env_tier,profile}
agentic_triage_smoke_source_coverage{cluster,env_tier,source,status}
```

Use these hard-failure reasons consistently:

```text
model_route_failed
a2a_failed
grafana_alert_not_firing
webhook_not_delivered
workflow_not_created
incident_not_normalized
agent_path_failed
eval_not_published
score_below_threshold
source_evidence_missing
unauthorized_mutation
public_safety_leak
```

### Alerting For The Smoke System Itself

Grafana should alert when any of these are true:

```promql
agentic_triage_smoke_passed{env_tier="dev"} == 0
agentic_triage_smoke_hard_failures{env_tier="dev"} > 0
agentic_triage_smoke_score{env_tier="dev"} < 0.85
time() - agentic_triage_smoke_last_success_timestamp_seconds{env_tier="dev",profile="daily"} > 90000
absent_over_time(agentic_triage_smoke_score{env_tier="dev",profile="quick"}[30m])
```

Page only the test channel until the signal is stable. After the suite has a
clean run history, route `broken` periodic verdicts to the platform on-call as
an agentic triage stack incident.

### Target Rotation

Rotate low-risk targets so the smoke does not overfit to one app:

```text
week 1: whiskey app or podinfo
week 2: cert-manager read-only symptom or controlled cert expiry fixture
week 3: external-dns read-only symptom or controlled DNS drift fixture
week 4: dedicated smoke namespace with full source matrix
```

Keep all destructive or self-heal tests behind namespace allowlists, opt-in
labels, HITL approval, and GitOps/workflow-mediated remediation.
