# Phase 5 — Backend drills: DLQ, replay, concurrency, outage

Applied: `../applied-config/03-argo-augmented.yaml` (`validate-schema` step +
`process-incident` sub-template + `synchronization.semaphore`, this pass) —
a genuinely new backend feature, not previously present at proof level.

## DLQ / quarantine (DS-07) — built and proven this pass

`validate-schema` runs before the claim/agent/ticket chain and quarantines
any record failing schema/cluster/staleness checks, storing the **full
original envelope** (for replay) plus a reason, in a ConfigMap labeled
`triage-quarantine=true` (queryable, visible counter — not a silent drop).

| Test | Result |
|---|---|
| Bad `schema_version` (`v1` instead of `v2`) | Quarantined: `triage-dlq-red-agentic-triage-hwg4d`, reason `unsupported_schema_version:observability.triage.v1` |
| Stale `observed_timestamp` (~19.5 days old, > 86400s window) | Quarantined: `triage-dlq-red-agentic-triage-cfz4l`/`-rgsmk`, reason `stale_replay:1684582s_old` |
| Valid record, same run | Passed straight through — ticket [#484](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/484) |
| **Replay after fix**: took the quarantined `hwg4d` record's stored `incident.json` verbatim, corrected only `schema_version`, resubmitted | Ticket [#485](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/485) created — proves the quarantine store is genuinely replayable, not a dead end |
| Counter | `kubectl get cm -n argo-events -l triage-quarantine=true` — 4 records, each with a distinct, human-readable `reason` |

**A real bug was found and fixed while building this**: the first version of
`validate-schema` used `$$` for a unique DLQ record name, which rendered
literally as `$` instead of the shell PID (workflow `red-agentic-triage-zfldg`
failed: `metadata.name: Invalid value: "triage-dlq-...-$"`). Fixed by using
Argo's own `{{workflow.name}}` (already unique, already DNS-label-safe)
instead of shell-level uniqueness tricks.

**A second real bug was found and fixed**: chaining a per-step `when` that
references `claim-24h-window`'s outputs from `diagnose-readonly`/
`create-gitlab-issue`/`append-correlated-evidence` broke whenever
`claim-24h-window` itself was skipped (a quarantined record) — Argo tries to
resolve `{{steps.claim-24h-window.outputs...}}` textually before evaluating
the boolean expression, and a skipped step's outputs don't resolve, producing
a hard template error (`Invalid token: '{{'`), not a clean short-circuit.
Fixed by moving the claim→diagnose→create→append chain into its own
`process-incident` sub-template, gated as a single unit on
`validate-schema`'s output — internal references inside that sub-template are
only ever evaluated when the whole chain actually runs, so they always
resolve. Both bugs were caught by direct `argo submit` testing **before**
trusting live Sensor-triggered traffic to the new gate — confirmed after the
fix with both `argo submit` and a genuine Sensor-triggered fixture
(`phase5-live-sanity` → ticket [#486](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/486)).

```text
DLQ_QUARANTINE_PROVEN: yes
```

## Replay: in-window (no new ticket) and stale (quarantined) — both proven

- In-window replay: proven in `phase1-smoke-tests.md` (resubmitted the exact
  `FailedScheduling` envelope for ticket #453 — appended, no new ticket) and
  repeatedly in `phase0` (correlation drill: 4 appends, 1 ticket).
- Stale replay: proven above — a record whose `observed_timestamp` is older
  than the 24h claim window is quarantined, not processed as a fresh
  incident.

```text
REPLAY_IN_WINDOW_AND_STALE_PROVEN: yes
```

## Bounded workflow concurrency (DS-10) — built and proven this pass

Added a `synchronization.semaphore` on the WorkflowTemplate, backed by a
**dedicated** ConfigMap (`argo-events/triage-workflow-concurrency`,
key `red-agentic-triage: "5"`) — deliberately scoped to this WorkflowTemplate
only, not the shared cluster-wide `workflow-controller-configmap` that other
pipelines on this cluster (chaos, kagent-triage, cert-manager, etc.) also
depend on.

Drill: submitted 8 distinct synthetic incidents concurrently via 8
backgrounded `argo submit` calls. Observed:

```text
red-agentic-triage-zmfw9   Pending   Waiting for argo-events/ConfigMap/triage-workflow-concurrency/red-agentic-triage lock. Lock status: 0/5
red-agentic-triage-fd6ss   Pending   Waiting for argo-events/ConfigMap/triage-workflow-concurrency/red-agentic-triage lock. Lock status: 0/5
red-agentic-triage-l646z   Pending   Waiting for argo-events/ConfigMap/triage-workflow-concurrency/red-agentic-triage lock. Lock status: 0/5
# the other 5 Running concurrently
```

Concurrent `Running` count observed at exactly 5, never higher, across 16
consecutive polls during the burst. All 8 eventually drained through and
completed (`Succeeded`) with 8 distinct tickets (#487-494) — none lost, none
duplicated, just queued.

```text
WORKFLOW_CONCURRENCY_BOUNDED: yes
```

## Broker outage / drain + loss accounting (DS-13) — not tested, explicit gap

`red`'s Kafka target is a real, managed Confluent Cloud cluster (not a
self-hosted broker this session could safely stop/restart). Deliberately did
**not** attempt to simulate a broker outage against live external managed
infrastructure without an approved maintenance window/owner sign-off — that
is a real production dependency, not a disposable proof fixture, and taking
it down (even briefly) risks other tenants of the same Confluent Cloud
cluster. The closest available loss-accounting evidence from this session:
Vector's `kafka` sink exposes `vector_kafka_requests_total` /
`vector_kafka_responses_total` / `vector_component_discarded_events_total`
(see `phase2-vector-config.md`'s disk-buffer section) — none showed any
delivery failure in this session, but an actual outage/drain drill was not
performed. This needs its own approved exercise (with the Confluent Cloud
project owner) before `BROKER_OUTAGE_LOSS_ACCOUNTED` can honestly be `yes`.

```text
BROKER_OUTAGE_LOSS_ACCOUNTED: no   # not attempted against real managed infra without an approved maintenance window; escalate to the Confluent Cloud project owner for a scheduled drill
```

## Alertmanager

Unchanged throughout Phase 5 — no command in this phase touched
Alertmanager, Grafana, or any existing webhook/proxy path.

```text
ALERTMANAGER_UNCHANGED: yes
```
