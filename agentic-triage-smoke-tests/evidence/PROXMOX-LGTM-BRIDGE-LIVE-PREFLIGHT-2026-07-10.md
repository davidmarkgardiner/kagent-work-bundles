# Proxmox LGTM Bridge Live Preflight - 2026-07-10

## Verdict

```text
pass_with_remaining_periodic-rule-and-trace-gaps
```

The first preflight failed while the cluster was booting. Later retests proved
both Kubernetes events and application logs through Loki and Grafana alerting
into the smart-triage workflow. The sections below preserve the initial failure
and subsequent fixes rather than hiding the recovery history.

## Intended Test

Validate the bridge design from `LGTM-EVIDENCE-BRIDGE-GAP.md`:

```text
pod log marker -> Loki -> Grafana LogQL alert -> webhook/EventSource or Vector/Kafka -> triage
Kubernetes event -> Loki -> Grafana LogQL alert -> webhook/EventSource or Vector/Kafka -> triage
```

## Live Preflight Checks Run

The active Kubernetes context was the existing Proxmox dev cluster.

Checked:

- monitoring namespace pod/service readiness;
- Loki, Loki gateway, Grafana, Prometheus, and Alertmanager service endpoints;
- Argo Events smart-triage EventSource and Vector webhook services;
- recent Kubernetes events in the monitoring and Argo Events namespaces;
- short readiness wait for Loki/Grafana components.

## Findings

The following services had no ready endpoints during the preflight:

```text
loki
loki-gateway
kube-prom-grafana
kube-prom-kube-prometheus-alertmanager
kube-prom-kube-prometheus-prometheus
```

The smart-triage direct EventSource service also had no ready endpoint during
the check. The Vector webhook normalizer service did expose endpoints, but that
is not enough to prove the Loki/Grafana alert path.

Recent cluster events showed storage/control-plane instability symptoms,
including monitoring pods stuck around volume mount failures and readiness
failures. During the readiness wait, Loki did not become Ready and the
Kubernetes API became unreachable from the client.

## Result

No smoke pod was created and no Grafana/Loki alert was installed. This was
intentional: creating smoke resources while Loki, Grafana, Prometheus,
Alertmanager, and the triage EventSource were not exposing endpoints would not
produce a meaningful end-to-end result.

## What This Proves

This proves only the live preflight status:

```text
LGTM bridge live test attempted
LGTM/triage alert path not runnable
reason: observability/control-plane endpoints unavailable
```

It does not prove or disprove the bridge design.

## Required Recovery Before Retest

Before rerunning the log/event bridge smoke:

1. Restore Kubernetes API stability.
2. Restore storage/CSI health for stateful monitoring workloads.
3. Confirm Loki and Loki gateway expose ready endpoints.
4. Confirm Grafana exposes a ready endpoint.
5. Confirm Prometheus and Alertmanager expose ready endpoints if the selected
   alert route depends on them.
6. Confirm the smart-triage EventSource or Vector/Kafka route exposes ready
   endpoints.
7. Then run the two acceptance tests from `LGTM-EVIDENCE-BRIDGE-GAP.md`:
   - pod log error marker to Loki LogQL alert;
   - Kubernetes warning event to Loki LogQL alert.

## Retest After Proxmox Boot Completed

After the Proxmox host and Kubernetes nodes finished booting, the preflight was
rerun.

### Recovery Status

The Kubernetes API was reachable again and all nodes were `Ready`.

The LGTM services exposed ready endpoints:

```text
loki
loki-gateway
kube-prom-grafana
kube-prom-kube-prometheus-alertmanager
kube-prom-kube-prometheus-prometheus
```

The smart-triage EventSource and Vector webhook normalizer services also
exposed endpoints.

### Smoke IDs

```text
run_id=bridge-20260710102007
namespace=agentic-triage-event-smoke
log_pod=log-bridge-bridge-20260710102007
event_pod=event-bridge-bridge-20260710102007
```

The temporary smoke pods were deleted after the test.

### Kubernetes Event Bridge Result

```text
status=proven_to_loki
```

A safe unschedulable pod produced a real Kubernetes event:

```text
reason=FailedScheduling
type=Warning
object=pod/event-bridge-bridge-20260710102007
```

The event appeared in Loki via the Alloy Kubernetes events source. The Loki
stream labels included:

```text
cluster={{CLUSTER_NAME}}
namespace=agentic-triage-event-smoke
event_reason=FailedScheduling
event_type=Warning
job=kubernetes-events
payload_type=kubernetes-event
pipeline=alloy-k8s-events-kafka-loki
service_name=kubernetes-events
source=alloy
```

The Loki event body preserved the useful reason and message fields:

```json
{
  "kind": "Pod",
  "name": "event-bridge-bridge-20260710102007",
  "reason": "FailedScheduling",
  "type": "Warning",
  "sourcecomponent": "default-scheduler",
  "msg": "0/3 nodes are available: one node had an untolerated control-plane taint and two nodes did not match the pod node selector. Preemption was not helpful."
}
```

This proves the key bridge requirement for Kubernetes events:

```text
event reason can be a Loki label
full event message can be retained in the event body
the triage path can receive or reconstruct reason/message evidence
```

### Pod Log Bridge Result

```text
status=not_proven_log_shipping_gap
```

The smoke pod emitted five expected log lines, confirmed with `kubectl logs`:

```text
AGENTIC_TRIAGE_SMOKE_ERROR run_id=bridge-20260710102007 smoke=log-errorburst failure=synthetic_error_burst seq=1
AGENTIC_TRIAGE_SMOKE_ERROR run_id=bridge-20260710102007 smoke=log-errorburst failure=synthetic_error_burst seq=2
AGENTIC_TRIAGE_SMOKE_ERROR run_id=bridge-20260710102007 smoke=log-errorburst failure=synthetic_error_burst seq=3
AGENTIC_TRIAGE_SMOKE_ERROR run_id=bridge-20260710102007 smoke=log-errorburst failure=synthetic_error_burst seq=4
AGENTIC_TRIAGE_SMOKE_ERROR run_id=bridge-20260710102007 smoke=log-errorburst failure=synthetic_error_burst seq=5
```

However, Loki did not return a non-event pod log stream for those lines:

```text
{namespace="agentic-triage-event-smoke", pod="log-bridge-bridge-20260710102007"} -> 0 streams
{namespace="agentic-triage-event-smoke", job!="kubernetes-events"} |= "AGENTIC_TRIAGE_SMOKE_ERROR" -> 0 streams
```

A broad run ID query did return Kubernetes event records for the pod lifecycle,
but those were event records, not the pod stdout logs.

This means the pod-log bridge remains blocked by log collection/shipping for the
smoke namespace. The pod generated the error evidence, but Promtail/Alloy did
not expose it in Loki as a queryable application log stream during the test
window.

### Retest Verdict

```text
events_to_loki=pass
event_reason_preserved=pass
event_message_preserved=pass
pod_logs_to_loki=fail
grafana_logql_alert_created=not_run
webhook_triage_delivery=not_run
```

The retry proves the evidence bridge design for Kubernetes events up to Loki.
It does not yet prove pod log errors or a full Grafana-alert-to-triage flow.

## Final Live Retest And Fixes

### Root Cause Of Missing Pod Logs

Promtail was healthy, but its final relabel rule only retained three platform
namespaces. The dedicated smoke namespace was intentionally dropped before
records could reach Loki.

The live allowlist was extended to include the smoke namespace. Static
low-cardinality labels were also added to application-log streams:

```text
cluster={{CLUSTER_NAME}}
source_type=logs
```

The equivalent sanitized Helm values are captured in
`examples/monitoring/promtail-smoke-namespace-values.yaml`.

### Continuous Source Run

The final source run used:

```text
run_id=bridge-20260710103503
namespace=agentic-triage-event-smoke
log_pod=log-bridge-bridge-20260710103503
event_pod=event-bridge-bridge-20260710103503
```

The application pod produced five structured error lines. Loki returned one
stream and all five lines with these useful dimensions:

```text
cluster={{CLUSTER_NAME}}
namespace=agentic-triage-event-smoke
pod=log-bridge-bridge-20260710103503
container=log-bridge-bridge-20260710103503
service_name=agentic-triage-log-smoke
node_name={{WORKER_NODE}}
source_type=logs
```

Parsing the log body with `| logfmt` added the alert dimensions:

```text
reason=CrashLoopBackOffSimulation
failure=synthetic_error_burst
run_id=bridge-20260710103503
```

The Kubernetes event from the same run reached Loki with:

```text
cluster={{CLUSTER_NAME}}
namespace=agentic-triage-event-smoke
pod=event-bridge-bridge-20260710103503
event_type=Warning
event_reason=FailedScheduling
event_message=the full scheduler failure message
```

### Grafana Alert Payload Proof

Two Grafana-managed LogQL alert rules evaluated successfully and fired through
the existing `smart-triage-webhook` contact point.

The log alert delivered:

```text
alertname=AgenticTriagePodLogErrorLokiSmoke
cluster={{CLUSTER_NAME}}
namespace=agentic-triage-event-smoke
pod=<log smoke pod>
container=<log smoke container>
service_name=agentic-triage-log-smoke
node_name={{WORKER_NODE}}
reason=CrashLoopBackOffSimulation
failure=synthetic_error_burst
run_id=<smoke run id>
evidence_query=<ready-to-run Loki query for the pod error lines>
```

The event alert delivered:

```text
alertname=AgenticTriageEventFailedSchedulingLokiSmoke
cluster={{CLUSTER_NAME}}
namespace=agentic-triage-event-smoke
pod=<event smoke pod>
event_type=Warning
event_reason=FailedScheduling
event_message=<full scheduler failure message>
run_id=<smoke run id>
evidence_query=<ready-to-run Loki query for the event>
```

The Argo EventSource logged successful request dispatch, the Sensor processed
both triggers, and the resulting workflow arguments retained the complete
Grafana webhook payloads.

### Downstream Failures Found And Fixed

The first log-triggered fan-out failed because the policy specialist was
`OOMKilled` at a `256Mi` limit. Its live capacity was raised, and the durable
Agent baseline was changed to:

```text
requests: cpu=1m memory=128Mi
limits:   cpu=250m memory=512Mi
```

The retry then completed the policy specialist without a restart.

Output review found two semantic defects:

1. Normalization dropped `service_name`, `node_name`, reason, failure, event
   message, run ID, and evidence query.
2. Demo specialist prompts forced unrelated `checkout-api` and
   `demo-payments` output even when a real alert payload was supplied.

The WorkflowTemplate and Agent contracts were updated so the normalized alert
is authoritative and every available evidence field is preserved.

A final grouped Grafana webhook exposed another bug: a resolved alert appeared
before the new firing alert in the `alerts` array. Fingerprinting and
normalization now select the first alert whose status is `firing`, falling back
to the first array item only when no firing item exists.

### Corrected Semantic Proof

The corrected workflow selected the new firing log alert and normalized:

```text
SOURCE_TYPE: logs
CLUSTER: {{CLUSTER_NAME}}
NAMESPACE: agentic-triage-event-smoke
WORKLOAD: agentic-triage-log-smoke
POD: log-bridge-semantic-<run id>
CONTAINER: log-bridge-semantic-<run id>
SERVICE: agentic-triage-log-smoke
NODE: {{WORKER_NODE}}
LOG_REASON: CrashLoopBackOffSimulation
FAILURE: synthetic_error_burst
EVIDENCE_QUERY: <ready-to-run Loki query>
RUN_ID: semantic-<run id>
```

The Kubernetes specialist repeated the real alert name, namespace, pod,
container, reason, and failure. The Grafana specialist preserved cluster,
namespace, pod, source type, reason, failure, and the Loki evidence query. The
incident commander synthesized those same fields and reached the expected HITL
gate. No unrelated demo workload was substituted.

The corrected firing-alert selector was also evaluated against the preserved
event webhook payload and returned the real event alert, pod, event type,
`FailedScheduling` reason, full scheduler message, and evidence query.

The corrected log semantic proof submitted the exact captured grouped Grafana
webhook payload to the updated WorkflowTemplate because Grafana had already
delivered the original notification before the selector fix was applied. The
Grafana contact-point/EventSource/Sensor ingress and the corrected semantic
workflow are therefore both live-proven, but a single uninterrupted
post-selector-fix notification run remains a final regression check.

### Final Verdict

```text
events_to_loki=pass
event_reason_preserved=pass
event_message_preserved=pass
pod_logs_to_loki=pass
log_reason_and_failure_parsed=pass
grafana_logql_alerts_fired=pass
grafana_payload_context=pass
webhook_eventsource_delivery=pass
sensor_workflow_creation=pass
triage_normalization=pass
specialist_context_preservation=pass
incident_synthesis=pass
policy_specialist_capacity_retry=pass
```

This proves the direct Grafana contact-point to smart-triage webhook route. It
does not prove the optional Vector/Kafka route in this run. The temporary rules
were paused after proof to prevent repeat model use, and all temporary smoke
pods were deleted.

The remaining work is to convert the run-specific LogQL expressions into
parameterized periodic rules, publish pass/fail metrics to the stack-health
dashboard, and run a real Tempo trace alert rather than the existing explicit
trace fallback. The post-HITL lifecycle-eval arguments in the demo
WorkflowTemplate also still contain static demo workload values; they were not
exercised in this proof and must be parameterized from the normalized incident
before periodic scoring is considered source-accurate. The first periodic run
should also close the single uninterrupted post-fix notification check noted
above.
