# Critique-review prompt — worker→management triage enrichment (2026-07-21)

Hand this whole file to an independent reviewer (codex-rescue / kimi / a fresh
agent). It is self-contained: context, what changed, evidence, and the exact
open questions to attack. Be adversarial — the goal is to find what is wrong or
unproven before this is replicated onto office worker clusters.

---

## System under review

A parallel, additive, **read-only** incident-triage path:

```
worker cluster:  pod → Alloy (logs + k8s events) → Vector → Kafka (Confluent)
management side: Kafka → Argo Events → read-only kagent agent → GitLab ticket
```

The agent runs on the **management** cluster and (in the real topology) has **no
live kubectl access** to the worker where the incident happened. Therefore the
envelope must be self-sufficient: it must carry every field the agent needs to
diagnose, and every locator a human needs to reach back to the worker.

Files (all uncommitted; their live-application status and ticket claims below
are evidence supplied by the implementing agent and must be checked, not
assumed):
- `reference-config/01-alloy.yaml`  (+23 lines)
- `reference-config/02-vector.yaml` (+54 lines)
- `reference-config/03-argo.yaml`   (rewritten: synced live→repo + enriched)
- `evidence/ALLOY-EVENT-RAW-CAPTURE-2026-07-21.md` (new)
- `PAYLOAD-FIELD-PROOF.md`, `PHASE-3-argo-gitlab-ticket-backend.md` (docs)

## What changed and why

1. **Container on events was never real.** `loki.source.kubernetes_events`
   (`log_format="json"`) emits a *flattened* event with no `involvedObject` and
   no `container` field — proven by a raw `vector tap` (see the evidence file).
   The prior repo claim that "Vector dropped container" was based on a
   hand-written fixture, not captured output. Fix: container is parsed from
   `event.msg` in Vector (mirrors the existing `.pod = event.name` rescue).
2. **Alloy event extraction made honest.** `pod` now comes from the real
   top-level `name`; dead `involvedObject.*` expressions removed; `node` added
   to the log path (`__meta_kubernetes_pod_node_name`).
3. **Reach-back fields added** to envelope + ticket: `node` (event: `sourcehost`;
   log: Alloy label), `object_kind`, `event_count`, `reporting_component`.
4. **Burst control.** A crashloop fires the same reason repeatedly with volatile
   `count`/`resourceVersion` in the evidence; hashing evidence minted a new
   `delivery_key` per repeat → a workflow per event. Event `delivery_key` now
   keys on pod+reason so identical repeats collapse; a different later reason
   still passes and correlates on `dedupe_key`.
5. **Ticket rendering + prompt.** Summary header, reach-back kubectl block,
   evidence labelled "Event message" vs "Log error message", management-aware
   agent prompt. Live WorkflowTemplate synced into the repo (killed a drift
   where the repo lagged the on-cluster logic).

## Evidence (live proof on `red`, 2026-07-21)

| Claim | Evidence |
|---|---|
| Flattened event shape | raw pre-VRL capture in `evidence/ALLOY-EVENT-RAW-CAPTURE-2026-07-21.md`: top-level `name`/`kind`/`msg`, no `involvedObject` or container field |
| Container on event path populates | claimed by ticket #508 (`Container the-failing-container`); reviewer should inspect the ticket/body or retained payload |
| All fields on both paths | claimed `vector tap normalize` capture: event carries node/object_kind/event_count/reporting_component; log carries the real error text + service |
| Node on both paths | claimed by #510/#511/#512 (`Node homelab-control-plane`) |
| Burst control | claimed crashloop 4× BackOff → 1 event workflow (was ~13 pre-fix) |
| Redaction holds in final ticket | claimed by #511/#512: `password=`/`token=` → `[REDACTED]`; this is not proof for structured, multiline, encoded, or agent-rediscovered secrets |
| Both signals → one ticket | claimed by #511/#512: log body + correlated BackOff event note, same fingerprint |
| Full validation ticket | claimed by #512 (pod, cluster, node, container, log error message, event message, reach-back kubectl) |
| Alloy/Vector stable | claimed both deployments `restarts=0` after all reloads; no HA/restart/replay proof yet |

## Open items — SORTED by severity (attack these)

**P1 — blocks clean fleet replication**
- `cluster` is hardcoded `"red"` in `01-alloy.yaml` static labels (and Vector's
  `?? "red"` fallback). On a management cluster receiving from N workers, every
  ticket would say `red`. Each worker must stamp its own cluster identity
  (env/downward-API/GitOps overlay). Is a hardcoded fallback dangerous (silent
  mislabel) vs. failing closed? Should the fallback be `"unknown"` and the
  record quarantined if cluster is unset?
- The management WorkflowTemplate independently accepts only `cluster=red`
  (`validate-schema` in `03-argo.yaml`). That is a proof-cluster guard and must
  be removed or replaced for the work handover: **every worker cluster must be
  able to send its stamped logs and events to the central triage path; no valid
  record is rejected merely because its cluster name is new.** Review the
  replacement strictly for field integrity: require a non-empty cluster value,
  preserve it unchanged through Vector, Kafka, Argo, agent, and ticket, and
  prove two distinct worker-cluster names produce two correctly labelled,
  human-readable tickets. Invalid/malformed payload handling must be visible,
  but it must not become a hidden drop path for valid worker telemetry.
- Correlation is keyed only by `cluster:namespace:pod`. Two containers in one
  multi-container pod, or two independent reasons for the same pod inside 24h,
  share one claim/ticket. That can mix unrelated evidence and direct a human to
  the wrong container. Decide whether the incident identity needs container and
  a normalised failure signature, while retaining a deliberate parent-level
  correlation mechanism for log + event evidence.
- Vector's `dedupe` cache is process-local and LRU-count bounded. A Vector
  restart, reschedule, scale-out/HA replica, or Kafka replay loses suppression;
  records then reach Argo and can append many duplicate notes to the durable
  claim's ticket. Define which layer owns a time-bounded, durable delivery
  throttle and prove restart, replay, and concurrent-consumer behaviour.
- The current red cluster names, topic/consumer identity, and fixed
  WorkflowTemplate names are proof-environment values. Check that the handover
  makes cluster identity a required per-worker Alloy/GitOps value and gives the
  central path a clear, repeatable way to accept additional workers without
  changing the ticket contract or silently relabelling their evidence.

**P2 — correctness/robustness of the new logic**
- Container regex `[Cc]ontainer (\S+)` on `event.msg`: only crashloop-class msgs
  name the container. `Unhealthy`/probe and pod-scoped events stay blank
  (claimed acceptable). Any msg format where this mis-captures (e.g. captures a
  trailing token, or a msg containing "container" in prose)?
- Burst control keys event `delivery_key` on pod+reason. Does this wrongly
  suppress a *genuinely new* occurrence of the same reason after the incident
  was resolved and recurs within the dedupe cache window (10000 events, LRU, not
  time-bounded)? Is a time-bounded throttle safer?
- `event_count` taken from the event's `count` at capture time — is it
  meaningful downstream, or misleading (it is the count at that single sampled
  event, not a total)? Because duplicate BackOff records are currently dropped
  before Argo, the ticket will normally retain the *first* count, not a current
  cumulative count. Decide whether to update an aggregate on the existing
  incident, remove the field, or label it explicitly as `observed_event_count`.
- The event evidence renders the whole flattened JSON body, including volatile
  event/resource versions and the `count`. They are not needed for diagnosis,
  weaken stable evidence comparison, and may expose future unreviewed fields.
  Assess whether Vector should construct a small allow-listed event message
  (`reason`, `msg`, object identity, reporter) before Kafka rather than redact
  and forward the entire serialized event.

**P3 — reliability / semantics**
- Claim/iid race: when a pod emits both log and event, the event sometimes lands
  via the fingerprint-**reuse** path instead of the **append-correlated** path
  (the log workflow hadn't recorded its issue-iid yet). Both now render the same
  enriched table, but the wording differs and the code paths are redundant.
  Should these two paths be unified?
- Log-path minor amplification: identical restart log lines occasionally produce
  2 log workflows (burst fix was event-only). Worth extending to logs?
- Agent still attempts live `kubectl` inspection (works on `red` because
  co-located). On a real mgmt/worker split those calls fail. Prompt now warns
  it, but is a warning enough, or should the agent's tool access be scoped so it
  cannot attempt (and mislead with) live calls it can't fulfil?
- The one-pass redaction evidence is not a security sign-off. Review redaction
  at every boundary (Alloy/Vector payload, Kafka, Argo parameters and logs,
  agent request/response, GitLab issue/note, DLQ ConfigMap) for structured JSON,
  multiline values, URL/query credentials, base64/encoded values, and secrets
  the agent rediscovers. The DLQ currently preserves the envelope for replay;
  confirm its RBAC, retention, and redaction guarantees are appropriate.

## What to return

For each open item: is it a real defect, and if so what is the failure scenario
and the smallest safe fix? Flag anything in the changed configs that is unsafe,
unproven, or would break under fleet scale, HA, broker outage/replay, a
multi-container pod, or a management/worker access split. Distinguish:

- verified from a raw pre-Vector capture;
- verified only in a downstream ticket or workflow; and
- self-reported but not independently evidenced.

For every proposed fix, name the config owner/layer (Alloy, Vector, Kafka,
Argo, agent, GitLab, or GitOps overlay) and a concrete test that would prove
it. Keep the scope on: complete, accurate Alloy log/event evidence reaching the
central triage agent; correct correlation without losing a valid signal; and a
human-readable GitLab ticket that displays the exact worker, namespace, pod,
container when known, signal, and safe evidence. Rank findings by severity. If
something is fine, say so briefly — do not invent work.
