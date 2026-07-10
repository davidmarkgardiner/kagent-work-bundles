# Agentic Triage Desired State

## Acceptance Rule

This document is the acceptance contract for the work agent. Select the test
profile before execution and compare the collected evidence against every gate
in that profile.

- `green`: every mandatory gate passes for one continuous `run_id`, the Tier 2
  workflow score is exactly `7/7`, no hard failure is present, and cleanup is
  complete.
- `amber`: all mandatory gates for the selected profile pass, but an explicitly
  optional capability is absent. Record the gap and owner. Amber is not full
  source coverage.
- `red`: any mandatory gate fails, evidence is missing, identities cannot be
  correlated, the score is below `7/7`, or cleanup is incomplete.

Do not combine evidence from different runs to make a gate pass. The proven
homelab evidence is a reference baseline, not evidence for a new environment.

## Test Profiles

| Profile | Purpose | Mandatory outcome |
|---|---|---|
| `tier-two-continuous` | Prove one real log or Kubernetes-event incident through the complete automated path | All gates `DS-01` through `DS-16`; exact `7/7` |
| `full-source-campaign` | Prove metrics, logs, events, traces or explicit trace fallback, dedup, and negative health behavior | `tier-two-continuous` plus the smoke matrix and Gate 1 in `SCORECARD.md` |
| `periodic-health` | Re-run a non-destructive canary and detect stale or failed triage | All gates `DS-01` through `DS-16`; interpret fault creation and cleanup as the controlled canary lifecycle |

The minimum acceptance profile for this handoff is `tier-two-continuous`.

## Desired Architecture

```text
approved non-production fault with unique run_id
  -> pod logs or Kubernetes events
  -> Loki
  -> scheduled Grafana LogQL alert rule
  -> Grafana contact point / Alertmanager webhook
  -> Vector receiver and normalization
  -> Kafka triage topic
  -> Argo EventSource and Sensor
  -> dedicated triage Workflow
  -> kagent Tier 2 agent
       -> Grafana MCP query against Loki
       -> read-only AKS MCP pod, event, and log queries
  -> correlated triage report
  -> deterministic 7/7 score
  -> Grafana health and freshness view
```

Every arrow is a test boundary. Evidence from the components on either side is
required; the existence of configuration alone does not prove delivery.

## Mandatory Gates

| Gate | Desired state | Minimum acceptable evidence |
|---|---|---|
| `DS-01` | The actual topology, namespaces, component names, topic, receiver path, registry policy, and selected profile are recorded with placeholders for sensitive values. | Sanitized run manifest and topology diagram. |
| `DS-02` | An approved non-production fault is created with a unique `run_id`, known expected symptom, bounded duration, and cleanup command. | Applied manifest, timestamps, target namespace/pod, expected reason or log marker. |
| `DS-03` | Loki contains the exact application log or Kubernetes event for that run. | Executed LogQL, time range, non-empty matching lines, labels, `run_id`, namespace, pod/workload, reason or message. |
| `DS-04` | Grafana evaluates the LogQL rule and sends a firing notification to the intended receiver. | Rule UID/name, healthy evaluation state, firing instance, contact point and notification-policy match, timestamp. |
| `DS-05` | Vector receives the webhook and preserves the incident join fields while normalizing it. | Sanitized before/after payload or logs containing `run_id`, fingerprint/event ID, source type, cluster, namespace, workload/pod, reason/message, and rule identity. Preserve image, container, and node when supplied; document their absence when not supplied. |
| `DS-06` | Kafka accepts the normalized incident on the intended topic. | Topic, partition, offset, timestamp, event ID or fingerprint, and `run_id`; no broker credentials. |
| `DS-07` | The EventSource consumes the record and the Sensor creates the expected dedicated Workflow. | EventSource/Sensor logs and created Workflow name tied to the same Kafka record and `run_id`. |
| `DS-08` | The Workflow validates and normalizes the alert without changing its identity or target. | Workflow parameters or node output showing the same `run_id`, cluster, namespace, pod/workload, source type, and fingerprint. |
| `DS-09` | The kagent task completes and invokes the four required investigations. | Completed task ID plus tool-call records for one Grafana Loki query and AKS pod state, events, and pod logs; all return `isError: false`. |
| `DS-10` | Grafana MCP returns incident-relevant Loki evidence rather than `NO_MATCH` or a transport error. | Tool request and non-empty result tied to the target and time window. |
| `DS-11` | Read-only AKS MCP confirms pod state, events, and logs for the target. | Three successful tool results showing current state, relevant event reason/message, and relevant container log/exit detail. |
| `DS-12` | The agent produces a correlated report without mutating the cluster. | Report includes run identity, cluster, namespace, pod/workload, source evidence, Kubernetes evidence, available image/container/node context, likely cause, confidence, recommended action, and limitations. |
| `DS-13` | The dedicated Workflow applies deterministic assertions and passes exactly `7/7`. | Score-node output and successful Workflow phase. A narrative agent confidence score is not a substitute. |
| `DS-14` | Tool access is least privilege. | `kubectl auth can-i` or equivalent proving pods/events/pods-log reads are allowed and Secrets, mutation verbs, exec, and port-forward are denied. |
| `DS-15` | Operators can see stack health and smoke freshness, and a failed/stale smoke produces an alert. | Grafana panel/query evidence for kagent, agentgateway/model requests, workflows, EventSource/Sensor, Vector/Kafka when used, last run, score, source coverage, and one negative state. |
| `DS-16` | Temporary workloads and alert rules are removed without damaging persistent routing. | Cleanup command output, namespace/pod absence, temporary-rule absence, and persistent receiver/Sensor readiness. |

## Hard Failures

Any item below makes the selected run `red`:

- no real fault or controlled canary was executed;
- evidence comes from multiple `run_id` values or target identities diverge;
- Loki returns no relevant record, `NO_MATCH`, or an error;
- the Grafana rule does not evaluate healthy and fire to the intended receiver;
- Vector receipt, Kafka publication, or EventSource/Sensor consumption is
  inferred rather than evidenced;
- the wrong WorkflowTemplate runs or required parameters are missing;
- the kagent task does not reach a completed state;
- any required MCP call errors or returns evidence for another target;
- the deterministic score is below `7/7`;
- the agent or its tools mutate a workload;
- a secret, token, private endpoint, or credential appears in the bundle;
- temporary resources remain after the run.

## Required Evidence Package

The work agent must return a sanitized evidence directory containing:

1. Run manifest: profile, `run_id`, UTC start/end, target, expected symptom,
   component names, and cleanup status.
2. Topology diagram showing the actual deployed path.
3. Fault manifest and creation proof.
4. Loki query and matched log/event excerpts.
5. Grafana rule, evaluation, firing, contact point, and route evidence.
6. Vector input/output correlation and Kafka topic/partition/offset evidence.
7. EventSource, Sensor, Workflow, and score-node evidence.
8. kagent task and the four MCP call/result summaries.
9. Correlated triage report and deterministic score.
10. Least-privilege checks, dashboard/negative-health proof, and cleanup proof.
11. A completed desired-state comparison matrix and all deviations with owners.

Use `evidence/EVIDENCE-TEMPLATE.md` for the run narrative. Screenshots may
support evidence but must not replace query output, object status, or IDs needed
for programmatic correlation.

## Comparison Matrix

Complete this table in the final evidence report. `PASS` requires a direct
reference to evidence produced by the current run.

| Gate | Evidence file and identifier | Actual result | `PASS` / `FAIL` |
|---|---|---|---|
| `DS-01` | | | |
| `DS-02` | | | |
| `DS-03` | | | |
| `DS-04` | | | |
| `DS-05` | | | |
| `DS-06` | | | |
| `DS-07` | | | |
| `DS-08` | | | |
| `DS-09` | | | |
| `DS-10` | | | |
| `DS-11` | | | |
| `DS-12` | | | |
| `DS-13` | | | |
| `DS-14` | | | |
| `DS-15` | | | |
| `DS-16` | | | |

## Final Verdict Format

```text
VERDICT: green | amber | red
PROFILE: tier-two-continuous | full-source-campaign | periodic-health
RUN_ID: <unique run identifier>
SCORE: 7/7 | <actual score>
HARD_FAILURES: none | <gate IDs and failures>
DEVIATIONS: none | <gap, impact, owner, due date>
CLEANUP: complete | incomplete
NEXT_OWNER: none | <team or role>
```

## Explicitly Optional For The Tier 2 Profile

The following do not block `tier-two-continuous`, but must not be claimed as
complete without their own current-run evidence:

- a real Tempo trace alert and trace ID/deeplink;
- automated scheduling of fault and temporary-rule creation/removal;
- post-approval remediation and full HITL lifecycle scoring;
- alert-to-GitLab ticket creation or update;
- structured container-image enrichment when the image is absent from the
  firing webhook payload.

The reference baseline is
`evidence/PROXMOX-TIER-TWO-KAFKA-E2E-2026-07-10.md`. A work deployment must
generate its own evidence and cannot inherit that baseline's verdict.
