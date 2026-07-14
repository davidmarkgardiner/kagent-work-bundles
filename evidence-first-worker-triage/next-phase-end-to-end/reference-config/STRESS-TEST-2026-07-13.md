# Red-cluster controlled stress test: 2026-07-13

## Decision

**Do not sign off the worker-to-management pattern for handover yet.** The
transport and read-only triage path work, but this exercise found a critical
evidence-redaction failure and an event-correlation/suppression defect. Both
must be corrected and re-proven before any office or fleet replication.

This is a controlled proof run on the `red` context. All test strings,
workloads, and GitLab tickets are synthetic; no real credential was used.

## What was exercised

Five disposable pods were created in `agentic-triage-proof` and removed after
the observation window.

| Scenario | Intended signal | Observed result |
|---|---|---|
| `payments-timeout-log-stress` | One synthetic `ERROR` log | Passed end-to-end: Kafka, Argo, read-only kagent, GitLab [#433](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/433). |
| `auth-redaction-log-stress` | One synthetic `FATAL` log with fake secret-shaped values | Reached GitLab [#434](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/434), but the fake values remained plaintext. **Failed security gate.** |
| `inventory-crashloop-stress` | Pod log plus Kubernetes `BackOff` | Kafka/EventSource received the data, but no `BackOff` workflow was created. The log candidate occupied the worker cache key first. |
| `imagepull-backoff-stress` | `Failed`, `ErrImagePull`, then `BackOff` Kubernetes events | Kafka/EventSource received `Failed`; no `BackOff` workflow was created. The broad filter admitted the earlier `Failed` record and local suppression discarded the later actionable `BackOff`. |
| `failed-scheduling-control-stress` | `FailedScheduling` warning | Kafka/EventSource received it, but the event Sensor correctly did not create a workflow because its current policy selects only `BackOff`. This is a deliberate coverage gap, not a pass. |

All five fixtures were deleted at the end of the run.

## Evidence chain observed

- The Kafka topic contained the structured `observability.triage.v2` records
  for all tested signal families.
- The Argo Kafka EventSource logged successful EventBus publication for the
  records.
- The two log workflows completed successfully, including their claim,
  read-only agent, and GitLab steps.
- Two durable ConfigMap claim records were created for the successful log
  fingerprints. This proves the current proof implementation claims a key,
  not that it has production-safe recovery semantics.
- GitLab tickets preserved original incident data and a useful read-only agent
  diagnosis. They also preserved the raw `message` field, which independently
  confirms that redacting only the representative evidence field would be
  insufficient.

## Findings requiring correction

### P0 — evidence redaction failed before Kafka and GitLab

The ticket for the redaction fixture contained the fake password, token, and
Bearer value in both `evidence.representative_log_lines` and raw `message`.
No production-shaped secret may be used in further tests until this is fixed.

Required gate: redact or remove raw evidence before Kafka egress; test
password, token, API-key, Authorization/Bearer, structured JSON, multiline,
and encoded variants; reject/quarantine a record when redaction cannot be
proved. The ticket writer must receive an allow-listed rendered evidence view,
not the full envelope.

### P0 — local dedupe destroys event correlation

The current worker key is effectively `cluster:namespace:service:pod` and the
Vector `dedupe` transform lets only the first matching candidate through. It
does not include a normalised failure signature and cannot merge evidence.
For the image-pull case, `Failed` arrived before `BackOff`; for the crashloop
case, the log arrived before `BackOff`. The required `BackOff` record was
therefore never available to the event Sensor.

Required gate: derive a fingerprint from stable workload identity and a
normalised signature; correlate/merge log and event evidence or forward both
to management for durable correlation. Do not let a broad early signal block a
more actionable later signal.

### P1 — event policy is too narrow and inconsistent

Vector's broad text filter admits `Failed` and `FailedScheduling`, while the
Argo event Sensor accepts only `BackOff`. This produces unnecessary queue and
EventBus work, then silently drops useful classes such as image pulls and
scheduling failures.

Required gate: define a versioned severity/reason policy once, apply it before
the worker queue, and route supported event families deliberately. Unsupported
signals must be counted as policy drops, not appear as ambiguous near-misses.

### P1 — ticket contract is over-broad and missing useful fields

The successful tickets demonstrate agent evidence delivery, but they embed the
entire raw envelope in a JSON code block. They also show `service` as empty for
the new fixtures. The triage diagnosis is useful, but ticket consumers should
not need to parse raw JSON to find priority, workload, signature, lifecycle,
or the safe evidence summary.

Required gate: create a rendered, allow-listed ticket contract with incident
fingerprint, cluster/environment, workload/pod/container, signal reason and
severity, first/last seen/count, source references, redacted evidence, agent
summary, confidence, runbook links, and idempotency/ticket state. Keep the
full raw envelope only in a protected, policy-approved evidence store if it is
needed at all.

## Other gaps still open

This run reinforces the pre-existing design gates: durable claim states must
recover from agent/ticket failure; the ticket writer needs an idempotency key;
unknown schemas need a DLQ/quarantine path; Vector needs persistent buffering,
Kafka acknowledgements, HA, and backpressure metrics; and agent prompts must
be treated as untrusted data. The ConfigMap claim and in-memory worker cache
remain proof-only components.

## Retest exit criteria

Before handover, rerun equivalent fixtures and prove all of the following:

1. No secret-shaped value reaches Kafka, an agent prompt, workflow logs, or
   GitLab.
2. A crashloop/image-pull sequence yields exactly one correlated, actionable
   ticket in the configured window, containing both log and event evidence.
3. Each supported event family routes according to an explicit policy; a
   rejected family has a visible drop/quarantine metric.
4. Tickets contain the rendered safe contract, not a raw payload, and have
   complete workload/service metadata.
5. Replay, concurrent delivery, agent failure, and GitLab post-create retry
   tests do not lose evidence or create duplicate tickets.

## Remediation status — same day

The red proof was updated after this exercise to build an allow-listed envelope
after redaction, omit raw OTLP `message`/`attributes`, use a safe GitLab ticket
summary, and scrub the agent diagnosis before it is written to GitLab. Exact
repeat suppression now keys on correlation key, reason, and redacted evidence,
so repeated log tailing is reduced without suppressing a different later event.
The event policy now explicitly includes `BackOff`, `Failed`,
`FailedScheduling`, `OOMKilled`, and `Unhealthy`.

The first regression pass also established two further constraints: a
read-only agent may rediscover sensitive-looking content through a Kubernetes
tool call, so ticket output needs a second scrub; and Kubernetes events do not
reliably carry the log's service label, so proof correlation cannot depend on
that label. The updated configuration addresses both at the proof boundary.
One final end-to-end regression is still required before changing the verdict:
prove the new ticket contains no secret-shaped value and that a later `BackOff`
is appended to the original incident rather than opening a second ticket.
