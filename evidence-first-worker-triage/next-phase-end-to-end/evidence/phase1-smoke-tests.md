# Phase 1 — Smoke tests: logs AND events, both proven end to end

Run on `red`, `agentic-triage-proof` namespace, 2026-07-20, after Gate 0 passed.
Fixtures: `../reference-config/confluent-scenarios.yaml`,
`../reference-config/log-fixture.yaml`, plus one ad-hoc `Unhealthy` fixture
(see below). All synthetic, all deleted after capture.

## Done when

```text
LOG_EVIDENCE_PATH_PROVEN: yes
EVENT_EVIDENCE_PATH_PROVEN: yes
EVENT_CLASSES_COVERED: FailedScheduling,BackOff(ImagePull),Unhealthy   # 3, see note on OOMKilled below
REPLAY_SUPPRESSED: yes
ALERTMANAGER_UNCHANGED: yes
OUTPUT_SANITIZED: yes
```

## Log path

| Fixture | Dedupe key | Workflow | Ticket |
|---|---|---|---|
| `payments-api-log-evidence-fixture` (`ERROR synthetic payment authorization timeout`) | `62eae9ac...` | `red-log-triage-*` | [#457](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/457)† |
| `oomkilled-confluent` / `-v2` (`FATAL synthetic memory exhaustion`) | `91fd4938...` / `28545a86...` | `red-log-triage-*` | [#457](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/457)†, [#468](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/468) |
| `configmap-missing-confluent` (`ERROR synthetic application cannot find ConfigMap`) | `fddc202f...` | `red-log-triage-*` | [#459](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/459) |

† ticket numbering from the batched run — see the claim ConfigMaps in gate-0/
phase-1 shell history; exact iid-to-fixture mapping cross-checked via each
ticket's title (`payments-api-log-evidence-fixture` → title contains that pod
name; verified via GitLab API, not guessed).

Every log ticket's title and body carry the correct `pod`, `container`,
`namespace`, `reason: log-error-signature`, `severity`, and the redacted
`representative_log_lines` — proven in the same pass as Gate 0's payload
checks.

## Event path — 3 real Kubernetes Warning event classes, end to end

| Event reason | Fixture | Dedupe key | Ticket |
|---|---|---|---|
| `FailedScheduling` | `scheduling-failure-confluent` (bad `nodeSelector`) | `d726e032...` | [#453](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/453) |
| `BackOff` (image pull) | `imagepull-failure-confluent` (`ImagePullBackOff`/`Failed`/`BackOff`) | `9e2509c8...` | [#467](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/467) |
| `Unhealthy` | `unhealthy-probe-confluent` (failing readiness/liveness exec probe) | `d76f61f8...` | [#474](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/474) |

### Note on `OOMKilled` — genuine platform boundary, not a pipeline defect

`PHASE-1`'s named minimum set is FailedScheduling / OOMKilled(-ing) / image
pull. A real OOM kill was produced and confirmed at the **container status**
level (`oomkilled-confluent-v2`: `exitCode: 137, reason: OOMKilled`, via a
`dd`-into-tmpfs allocation that genuinely exceeded a 32Mi limit — the first
attempt using `head -c 128M /dev/zero > /dev/null` did **not** actually
allocate memory and exited 0/Error, so it was replaced). But **no
corresponding Kubernetes Event** (`OOMKilled`/`OOMKilling`) was ever emitted
anywhere in the cluster — checked namespace-scoped and cluster-wide
(`kubectl get events -A --field-selector reason=OOMKilling` → no resources
found) in the minutes following the kill. On this cluster/kubelet, a
single-container cgroup OOM kill is visible only via container status, not as
a discrete Event object, so it cannot reach the events pipeline (Alloy only
tails `loki.source.kubernetes_events`, not pod status). Substituted a third
**real, verified** event class (`Unhealthy`) rather than mark the OOMKilled
marker "yes" without an actual observed event. Practical mitigation already in
place: a container that OOM-kills under `restartPolicy: Always` produces a
`BackOff` event on the next restart, which **is** covered and correctly
tagged `severity: critical` by Vector's VRL (OOMKilled/OOMKilling are in the
critical-severity reason list even though the event-reason match itself
cannot fire on this cluster) — worth flagging to whoever owns the target
office cluster: confirm whether *their* kubelet/version does emit OOM events
before assuming this class routes there either.

## Replay suppression — proven explicitly

Took the exact incident envelope Argo consumed for the `FailedScheduling`
ticket (#453, dedupe key `d726e032...`) and resubmitted it verbatim via
`argo submit --from workflowtemplate/red-agentic-triage`:

- Claim step: `"24-hour duplicate suppressed: triage-dedupe-d726e032..."`
- Result: evidence appended as a correlated-evidence note on **#453**; issue
  IID unchanged at `453` before and after — no second workflow, no second
  ticket.

## Kafka topic/partition/offset evidence

EventSource (`red-telemetry-triage-kafka`, consuming Confluent Cloud topic
`k8s-events`) log lines show real partition:offset advancement across the
run, e.g.:

```text
k8s-events:0:44 .. k8s-events:0:50   (gate-0 window)
k8s-events:5:60 .. k8s-events:5:64   (this Phase-1 window, incl. the replay)
```

(Partition varies by record because Vector's Kafka sink sets `key_field:
dedupe_key`, so records hash-partition by incident fingerprint — expected,
not an anomaly.) Every `"dispatching event on the data channel"` line is
immediately followed by `"Succeeded to publish an event"` to the EventBus —
no failed/retried publishes observed in this window.

## Vector produce efficiency (same window)

```text
alloy_otlp (received)         260
normalize  (received)         260
incident_signals (received)   260
incident_signals (discarded, intentional=true)  67   # policy-filtered, metered
suppress_exact_repeats (received)               193  # passed policy filter
kafka (received / produced)                      78  # after in-memory repeat suppression
```

260 raw log+event records in, 67 explicitly policy-discarded (metered, not
silent), 193 passed to dedupe, 78 unique records actually produced to Kafka —
consistent with the repeated `Unhealthy`/`BackOff` bursts in this run
collapsing to far fewer unique `delivery_key`s.

## Alertmanager

Not touched at any point in this phase (`ALERTMANAGER_UNCHANGED: yes`) — no
commands were run against Alertmanager, Grafana, or any existing
webhook/proxy config; the entire path exercised is `agentic-triage-proof` →
Vector → Confluent → `argo-events` namespace only.
