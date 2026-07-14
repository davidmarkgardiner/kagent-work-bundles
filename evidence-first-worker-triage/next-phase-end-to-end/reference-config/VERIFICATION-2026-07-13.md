# Red-cluster proof: 2026-07-13

## Verdict

**PASS — Alloy → Vector → Redpanda → Argo → read-only kagent → GitLab.**

The proof was run on the `red` Kubernetes context without Grafana or Loki in
the trigger path.

## Evidence observed

| Gate | Evidence |
|---|---|
| Cluster | `red` API reachable; control-plane node Ready. |
| Alloy | Additive `alloy-vector-triage` collector Ready; restricted to `agentic-triage-proof`. |
| Vector | `vector-telemetry-triage` Ready with OTLP HTTP and Kafka sink. |
| Kafka | Local Redpanda topic `incident-triage-requests` created. |
| Event source | Argo Kafka consumer reported `Sarama consumer group up and running` and published records to the EventBus. |
| Fixture | A disposable `checkout-api-evidence-fixture` emitted a synthetic error and Kubernetes `BackOff` events. The fixture was deleted after the proof. |
| Log route | A synthetic `ERROR` line from `payments-api-log-evidence-fixture` produced `red-log-triage-9czb4`. Its captured evidence was retried after an image correction, reached `k8s-readonly-agent`, and created GitLab work item [#430](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/430). |
| Event route | A real Kubernetes `BackOff` from `checkout-api-evidence-fixture` produced `red-event-triage-dd86g`, reached the same agent, and created GitLab work item [#431](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/431). |
| Durable dedupe | `red-log-dedupe-proof-7p2vf` succeeded while both its agent and GitLab steps were `Skipped`; its 24-hour ConfigMap retains #430's URL. |

## Corrections captured during the proof

- Vector's OpenTelemetry source requires both HTTP and gRPC listener blocks.
- Alloy HCL object values require commas; compact semicolon syntax is invalid.
- Scanning every pod log stream exceeded the proof collector's memory limit.
  The proof is therefore namespace-scoped before broad rollout.
- Argo Events v1.9.6 connected to local Redpanda after using Kafka protocol
  version `2.0.0`; `2.5.0` failed with broker EOF.
- Separate Argo sensors route log-led and `BackOff` event-led evidence to the
  same workflow. Normal pod lifecycle events do not match either sensor.
- Vector reduces immediate duplicate records; Argo's atomic ConfigMap claim is
  the authoritative 24-hour agent/ticket dedupe boundary.

## Scope boundary

The proof uses the existing read-only kagent agent and makes no remediation.
Grafana/Loki remain optional mirrors and are not used to trigger or enrich the
two tickets above. The fixture namespace remains deliberately narrow pending a
GitOps-managed production rollout.

## Follow-up controlled stress test

The initial proof above remains valid only as a demonstration that two single
signals can traverse the path. The follow-up controlled stress test in
`STRESS-TEST-2026-07-13.md` found a plaintext redaction failure and a
local-suppression defect that blocks later actionable Kubernetes events. The
pattern is therefore **not ready for fleet handover** until those findings are
corrected and re-proven.
