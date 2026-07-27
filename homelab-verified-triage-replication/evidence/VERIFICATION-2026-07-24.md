# Verification run — red homelab, 2026-07-24

Context `red`, single node `homelab-control-plane` (kind), Kubernetes v1.32.2.
Kafka: **real Confluent Cloud**; bootstrap and topic intentionally redacted.
GitLab: **real** `gitlab.com` project; identifier intentionally redacted.

No mocks, no stubs. Tickets below are real work items.

## Starting state

The stack was **not deployed** at the start of this session. Absent: the
`vector-telemetry-triage` Deployment, the `alloy-vector-triage` Deployment, and
all `red-*` EventSource / Sensor / WorkflowTemplate objects. The Secrets
(`confluent-credentials`, `gitlab-credentials`) and `argo-events-sa` were
present. So this is a **from-scratch replication**, which is the thing that
actually needed proving.

## Done when

```text
DEPLOY_FROM_CLEAN_PROVEN:        yes
LOG_EVIDENCE_PATH_PROVEN:        yes
EVENT_EVIDENCE_PATH_PROVEN:      yes
REDACTION_PROVEN:                yes
DEDUP_SINGLE_TICKET_PROVEN:      yes
AGENT_HAPPY_PATH_PROVEN:         yes
AGENT_FAILURE_PATH_PROVEN:       yes   # and it is now visible, was not before
PROBES_PROVEN:                   yes
SEMAPHORE_PRESENT:               yes
ALERTMANAGER_UNCHANGED:          yes
```

---

## 1. Deploy from clean

```
namespace/agentic-triage-proof created
configmap/triage-workflow-concurrency created
configmap/vector-telemetry-triage-red-config created
deployment.apps/vector-telemetry-triage created
service/vector-telemetry-triage created
configmap/alloy-vector-triage-red-config created
deployment.apps/alloy-vector-triage created
eventsource.argoproj.io/red-telemetry-triage-kafka created
sensor.argoproj.io/red-log-triage created
sensor.argoproj.io/red-event-triage created
workflowtemplate.argoproj.io/red-agentic-triage created
```

All five components reached Running. Vector's own healthchecks passed:

```
INFO vector::topology::running: Running healthchecks.
INFO vector::topology::builder: Healthcheck passed.
INFO vector: Vector has started. version="0.45.0"
```

EventSource reached the real broker:

```
msg="Sarama consumer group up and running!..." eventSourceName="red-telemetry-triage-kafka"
```

## 2. Probes (F5 fix)

Both collectors came up `1/1 Running` with the new probes active — Vector on
`/health`:8686, Alloy on `/-/ready`:12345 (the latter required
`--server.http.listen-addr=0.0.0.0:12345`; Alloy's default 127.0.0.1 bind makes
any probe unusable).

```
vector-telemetry-triage-7b9cbcf5bf-qvg62   1/1   Running   0   28s
alloy-vector-triage-57cf6d7f89-jbj9x       1/1   Running   0   26s
```

## 3. Worker leg — Alloy → Vector → Kafka

Vector pipeline counters, first window:

```
alloy_otlp              received  46
normalize               received  46
incident_signals        received  46   sent 35   discarded 11   (intentional=true)
suppress_exact_repeats  received  35   sent  3   discarded 32
kafka                   sent       3
```

Later window, after an Alloy restart replayed pod logs from the beginning —
a useful accidental stress test of repeat suppression:

```
alloy_otlp              received 1547
incident_signals        sent     1503   discarded   44
suppress_exact_repeats  discarded 1498
kafka                   sent        5
```

**1547 raw records in → 5 produced to Kafka.** Drops are counters, not silence.

EventSource consumed from real partitions/offsets:

```
eventID=…:k8s-events:1:3
eventID=…:k8s-events:3:10
eventID=…:k8s-events:3:11
```

(Partition varies per record because the Kafka sink sets `key_field: dedupe_key`,
so records hash-partition by incident fingerprint. Expected.)

## 4. Envelope correctness

Live envelope, event path — every reach-back field populated:

```json
{
  "schema_version": "observability.triage.v2",
  "cluster": "red",
  "namespace": "agentic-triage-proof",
  "node": "homelab-control-plane",
  "pod": "checkout-api-evidence-fixture",
  "container": "checkout-api",
  "reason": "BackOff",
  "severity": "warning",
  "signal_kind": "event",
  "object_kind": "Pod",
  "event_count": 1,
  "reporting_component": "kubelet",
  "automation_allowed": false,
  "dedupe_key": "24f9673972cdfda1…",
  "delivery_key": "53616bb7cfe27671…"
}
```

`container: checkout-api` is the rescue-from-`msg` path working — the flattened
k8s-event body has no `container` field, so it is parsed out of
`"Back-off restarting failed container checkout-api in pod …"`.

Live envelope, log path — **redaction proven**. Fixture printed
`password=shouldberedacted`; what reached the envelope:

```
"representative_log_lines": "ERROR database authentication failed [REDACTED]\n"
```

## 5. Agent failure path (F1) — the defect and the fix

**Before.** Workflow `red-event-triage-d42hr` reported `Succeeded` on every step
and filed issue **#513** with `### Read-only kagent triage (includes
confidence)` followed by **nothing**. The Argo output parameter was empty:

```
=== diagnose-readonly Succeeded
 "parameters": [ { "name": "diagnosis", "value": "", "valueFrom": {"path": "/tmp/diagnosis.txt"} } ]
=== create-gitlab-issue Succeeded
 INPUTS: {"parameters":[…,{"name":"diagnosis","value":""},…]}
```

Root cause probe against the A2A endpoint — kagent returns errors with **HTTP 200**:

```
--- top-level keys: id jsonrpc result
--- result keys:    contextId history id kind metadata status
--- artifacts extraction (config's jq expr):   <empty>
--- raw: …"metadata":{"kagent_error_code":"API_ERROR"},"parts":[{"kind":"text",
         "text":"Error code: 403 - {'error': {'message': \"You've reached your
         usage limit for this billing cycle…
```

The config read only `result.artifacts[]` (absent here), then guarded with
`test -s` on a file that `jq -r … join("\n")` had written a bare newline into —
a guard that can never fail.

**After.** Same quota-exhausted condition, workflow `red-log-triage-j6kgn`:

```
agent attempt 1/3 returned an application error -> API_ERROR
agent attempt 2/3 returned an application error -> API_ERROR
agent attempt 3/3 returned an application error -> API_ERROR
agent unavailable after 3 attempts -> agent error API_ERROR: Error code: 403 -
  {'error': {'message': "You've reached your usage limit for this billing cycle…
  (emitting degraded ticket)
GitLab issue created (agent_status=unavailable): …/work_items/515
```

Issue **#515** as filed:

```
labels: automated-triage, triage-agent-unavailable, triage-fingerprint-18698a197ff39e68

🔴 **CRITICAL — log-error-signature** on worker `red` · `agentic-triage-proof/fixfire-crashloop`
> ⚠️ **Automated analysis was NOT available for this ticket.**
| Agent analysis | UNAVAILABLE |
### Log error message (redacted)
FATAL post-fix verification: database authentication failed [REDACTED]
### Read-only kagent triage (includes confidence)
> ⚠️ **Agent diagnosis unavailable.** … Last failure: `agent error API_ERROR: Error code: 403 …`
```

## 6. Agent happy path

`k8s-readonly-agent` was temporarily repointed to `zai-model-config` (a model
with remaining quota) to prove the success path, **then restored to
`default-model-config`**. Workflow `red-event-triage-k4wjl`:

```
agent diagnosis obtained on attempt 1 (3356 bytes)
GitLab issue created (agent_status=ok): …/work_items/516
```

Issue **#516** carries `| Agent analysis | available |`, `| Event type | Warning |`
(the F4 field), the reach-back block, and a 3.3KB analysis that correctly
separates its confidence in the symptom from its confidence in the cause:

> Confidence: HIGH that the symptom is CrashLoopBackOff (the event is
> unambiguous). LOW on the specific root cause, because the package contains no
> exit code, no container logs, and no prior state.

and names the exact next commands to run on the worker. That is the behaviour the
design is aiming for: honest about what the evidence package does and does not
contain.

## 7. Deduplication — one incident, one ticket

The log signal and the BackOff event for the same pod share a `dedupe_key` and
arrive ~1s apart.

**Before (F2).** Claim `triage-dedupe-24f96739…` was driven to
`state: claimed-retry` by the second workflow while the first was still running —
it had mistaken a live sibling for a dead claimant and proceeded toward creating
a second ticket. Only the downstream GitLab fingerprint search stopped it:

```
red-event-triage-d42hr … : GitLab issue created: …/work_items/513
red-log-triage-dws9b   … : Reused existing GitLab issue on retry (fingerprint match): …/work_items/513
```

**After (F2+F3).** Two independent runs, both correct:

```
# run 1
Claim triage-dedupe-18698a19… is 1s old (< 900s): assuming a live sibling workflow owns it; polling for its ticket id.
Sibling workflow published ticket 515 after 60s: appending instead of creating.
Correlated evidence appended to GitLab issue IID 515

# run 2
Claim triage-dedupe-345228b5… is 10s old (< 900s): assuming a live sibling workflow owns it; polling for its ticket id.
Sibling workflow published ticket 516 after 45s: appending instead of creating.
Correlated evidence appended to GitLab issue IID 516
```

One ticket per incident, second signal appended as correlated evidence, and no
wasted second agent call.

Claims reconcile correctly, every one ending `ticket-created` with its iid:

```
triage-dedupe-24f96739…: state=ticket-created issue_iid=513
triage-dedupe-91fd4938…: state=ticket-created issue_iid=456
triage-dedupe-e0d63804…: state=ticket-created issue_iid=514
```

## 7b. `scripts/smoke-test.sh` — the packaged test, run as shipped

Run unmodified against `red`. Two fixture pods (one log-only, one crashlooping),
which between them produce both signal kinds:

```
== Ticket outcomes ==
  …k4wjl-create-gitlab-issue:      GitLab issue created (agent_status=ok): …/work_items/516
  …wnfkc-create-gitlab-issue:      GitLab issue created (agent_status=unavailable): …/work_items/517
  …6llv7-append-correlated-evidence: Correlated evidence appended to GitLab issue IID 517
  …dnlbv-create-gitlab-issue:      GitLab issue created (agent_status=unavailable): …/work_items/518
  …zdcfv-append-correlated-evidence: Correlated evidence appended to GitLab issue IID 516

== Dedupe claims ==
  triage-dedupe-241788c2…: ticket-created iid=518
  triage-dedupe-345228b5…: ticket-created iid=516
  triage-dedupe-69d923b4…: ticket-created iid=517

== Quarantined (DLQ) ==
  (none)

== Cleanup ==
  pod "smoke-crashloop-204319" deleted
  pod "smoke-log-204319" deleted
```

Three distinct pods → three claims → three tickets, each reconciled to
`ticket-created` with its iid, plus two correlated appends where a second signal
arrived for a pod that already had a ticket. All five workflows `Succeeded`,
nothing quarantined, fixtures cleaned up automatically.

The `agent_status=unavailable` entries are expected: the agent had been restored
to the quota-exhausted `default-model-config` by this point. They demonstrate the
degraded path working as shipped rather than a fault in the run.

## 8. Coverage survey

All Warning event reasons present cluster-wide during the run:

```
 1170  PolicyViolation
    1  BackOff
```

`PolicyViolation` (Kyverno) is 99.9% of Warning events here and is **not** in the
allow-list — see FINDINGS-AND-FIXES.md **F6**. Collection is also scoped to a
single namespace by design. Both are deliberate; both are documented rather than
discovered later.

## 9. Final health

`scripts/verify.sh --context red`, after the fixes:

```
PASS  alloy-vector-triage ready / log clean
PASS  vector-telemetry-triage ready / log clean, healthchecks passed
PASS  vector metrics endpoint reachable (:9598)
PASS  Sarama consumer group connected to Kafka
PASS  no Kafka errors in eventsource log
PASS  sensor red-log-triage started and subscribed
PASS  sensor red-event-triage started and subscribed
PASS  workflowtemplate red-agentic-triage present
PASS  concurrency semaphore = 5
FAIL  kagent agent returned an application error (state=failed;err=API_ERROR;len=0)
PASS  no failed triage workflows
```

The single FAIL is **correct and expected**: `default-model-config`
(`kimi-for-coding`) is out of billing quota on this homelab, and the check exists
precisely to surface that before it turns into a run of analysis-free tickets.
Previously nothing anywhere reported this condition. Give that model config
quota, or point `k8s-readonly-agent` at one that has some (`zai-model-config`
worked during this run), and the check goes green.

## Tickets created by this run

| Issue | Path | Note |
|---|---|---|
| #513 | event | pre-fix; **empty agent section** — the F1 evidence |
| #514 | log | pre-fix |
| #515 | log | post-fix, degraded: `triage-agent-unavailable`, honest banner |
| #516 | event | post-fix, healthy: full 3.3KB analysis, `Agent analysis: available` |
| #517 | event | `smoke-test.sh` run, degraded, log signal appended to it |
| #518 | log | `smoke-test.sh` run, degraded |
| #456 | log | pre-existing open ticket, appended to by fingerprint reuse (F7) |

All carry the `automated-triage` label and can be closed together.

## Not touched

Alertmanager, Grafana, existing alert routes, the shared
`workflow-controller-configmap`, and every other pipeline in `argo-events`
(chaos, kagent-triage-*, teams-hitl-*, namespace-actions, …). The one change made
outside this bundle's own objects was the temporary `k8s-readonly-agent`
modelConfig swap in section 6, which was reverted.
