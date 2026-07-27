# Findings and fixes — homelab verification run, 2026-07-24

Cluster: `red` (kind, `homelab-control-plane`), context `red`.
Kafka: real Confluent Cloud, bootstrap and topic intentionally redacted.
GitLab: real `gitlab.com` project, identifier intentionally redacted.

Everything below was **reproduced live before it was fixed**, and the fix was
then **re-verified live**. Where a finding is a documentation/packaging problem
rather than a runtime defect it says so.

---

## Summary

| ID | Severity | What | Status |
|----|----------|------|--------|
| F0 | **High** (packaging) | The nominated replication set mixes two generations and ships the *older* Vector and Argo configs | Fixed — bundle now ships the newer set |
| F1 | **High** (correctness) | Agent failure was undetectable: tickets shipped with a blank analysis and every step reported green | Fixed + verified |
| F2 | **Medium** (correctness) | A concurrently-running claimant was mistaken for a dead one; only a downstream GitLab search prevented a second ticket | Fixed + verified |
| F3 | **Medium** (correctness) | A duplicate with no recorded ticket id skipped the append step *silently*, discarding the later signal's evidence | Fixed + verified |
| F4 | Low (hardening) | Event filter matched on `reason` alone; a `Normal` event sharing a reason string would have been triaged as an incident | Fixed |
| F5 | Low (operability) | No liveness/readiness probes on Alloy or Vector; a wedged collector looks healthy | Fixed |
| F6 | Info (scope) | Collection is scoped to one namespace; the dominant Warning event on this cluster is excluded | Documented, deliberate |
| F7 | Info (behaviour) | GitLab fingerprint reuse outlives the 24h claim TTL | Documented |
| F8 | Info (cosmetic) | The redaction scrub over-redacts ordinary English words in the agent's prose | Documented, deliberately not weakened |

---

## F0 — The nominated replication set ships the older configs

**What was asked for**, as the "home-proven replication set":

```
reference-config/01-alloy.yaml
applied-config/02-vector-with-metrics.yaml
applied-config/03-argo-augmented.yaml
applied-config/04-workflow-concurrency.yaml
```

**What is actually in those files.** `applied-config/` is dated *earlier* than
`reference-config/`, despite the name. `reference-config/03-argo.yaml` says so in
its own header — "CANONICAL COPY - synced from the live `red` cluster on
2026-07-21". Diffing them:

`applied-config/02-vector-with-metrics.yaml` is missing, versus `reference-config/02-vector.yaml`:

- **the reach-back fields** `node`, `object_kind`, `event_count`,
  `reporting_component` — the exact locators a management-cluster agent needs
  because it cannot inspect the worker;
- **the container rescue** that pulls the container name out of an event's `msg`
  text (`Back-off restarting failed container <name> …`), because the flattened
  k8s-event body has no `container` field;
- **the burst-control `delivery_key`.** This is the big one. The older file keys
  event delivery on `dedupe_key + reason + evidence_text`. A crashloop's evidence
  text embeds a volatile `count` and `eventRV`, so **every repeat mints a new
  delivery_key**, defeats the dedupe transform, and spawns a fresh Argo workflow
  per repeat. The newer file keys events on `dedupe_key + reason` only.

`applied-config/03-argo-augmented.yaml` is a strict subset of
`reference-config/03-argo.yaml`, missing the reach-back enrichment, the
severity/emoji header, the copy-paste `kubectl` reach-back block, and the
management-cluster framing in the agent prompt.

The one thing `applied-config/` adds that is worth keeping is the Vector
`internal_metrics` + `prometheus_exporter` sink, which is what makes filter drops
*metered* instead of silent.

**Fix.** `config/` in this bundle is `reference-config` + the metrics exporter +
the F1–F5 fixes. There is now one set, not four.

> Also worth knowing: the parent bundle contains a **third, parallel** design
> under `kustomize/` and `templates/` on schema `observability.triage.v3` with
> different field names (`incident_fingerprint`, `workload`, `evidence.summary`).
> It is internally consistent but **wire-incompatible** with the v2 Sensors —
> a v3 producer feeding v2 Sensors matches nothing. Do not mix the two tracks.

---

## F1 — Agent failure was undetectable (highest-value finding)

**Symptom.** GitLab issue #513 was created by a workflow that reported
`Succeeded` at every step, with the section `### Read-only kagent triage
(includes confidence)` **completely empty**. The Argo output parameter was
`diagnosis` = `""` (0 bytes).

**Why nothing caught it.** Three independent failure modes, none checked:

1. kagent reports A2A application errors with **HTTP 200**, inside
   `result.history[].metadata.kagent_error_code`. The config only ever inspected
   `result.artifacts[]`, which is absent on error.
2. The extraction was `jq -r '[…] | join("\n")' > /tmp/diagnosis.txt`. `jq -r`
   **always** writes a trailing newline, so on an empty match the file is 1 byte.
3. The guard was `test -s /tmp/diagnosis.txt` — true for a 1-byte file. **The
   guard could never fail.** Argo then strips the trailing whitespace when
   capturing the parameter, and the empty string is what reaches the ticket.

The trigger on the homelab was real and mundane: the model behind
`default-model-config` (`kimi-for-coding`) had exhausted its billing quota —

```
Error code: 403 - {'error': {'message': "You've reached your usage limit for this
billing cycle…", 'type': 'access_terminated_error'}}
```

At work the equivalents are a provider outage, an expired key, a rate limit, or a
model rename. In every case the old behaviour is the same: **a steady stream of
confident-looking tickets with no analysis in them, and a green pipeline.**

**Fix** (`config/03-argo.yaml`, `diagnose-readonly`):

- check the HTTP code, then `result.status.state`, then
  `kagent_error_code`, in that order;
- extract from `artifacts`, falling back to the last non-user `history` message
  (some runtimes answer without emitting an artifact) — reached only when there
  is no error code, so an error string can never be smuggled in as a diagnosis;
- a **real** guard: `tr -d '[:space:]'` before testing for emptiness;
- 3 bounded attempts with backoff;
- on exhaustion, emit an **honest degraded ticket**: a `⚠️ Agent diagnosis
  unavailable` banner naming the exact failure, an `Agent analysis | UNAVAILABLE`
  row in the contract table, and the label **`triage-agent-unavailable`** so the
  degraded set is queryable:
  `GET /projects/:id/issues?labels=triage-agent-unavailable&state=opened`.

The evidence package and reach-back commands are the primary value of the ticket;
the analysis is enrichment. Losing the enrichment must never look like having it.

**Verified.** Issue #515, filed while the quota was still exhausted:

```
labels: automated-triage, triage-agent-unavailable, triage-fingerprint-18698a197ff39e68
| Agent analysis | UNAVAILABLE |
Last failure: `agent error API_ERROR: Error code: 403 - … usage limit …`
```

and the workflow log:

```
agent attempt 1/3 returned an application error -> API_ERROR
agent attempt 2/3 returned an application error -> API_ERROR
agent attempt 3/3 returned an application error -> API_ERROR
agent unavailable after 3 attempts -> … (emitting degraded ticket)
GitLab issue created (agent_status=unavailable): …/work_items/515
```

`scripts/verify.sh` check 5 fails on this condition too, so it is caught before a
smoke test rather than after.

---

## F2 — A live sibling claimant was treated as a dead one

**Symptom.** A pod's error **log** and its **BackOff event** share a `dedupe_key`
(both key on `cluster:namespace:pod`) and arrive within ~1 second. Observed live:
the claim ConfigMap `triage-dedupe-24f96739…` went to `state: claimed-retry`
while the first workflow was still running.

**Why.** `claim-24h-window` had two cases for "claim held, no `issue_iid`":
it assumed **dead claimant** and CAS-stole the claim, returning
`duplicate=false`. It had no way to tell that apart from **a sibling that is
still mid-flight and simply has not written its ticket id yet**. The second
workflow therefore proceeded all the way to `create-gitlab-issue`.

It did *not* produce a second ticket, but only because the fingerprint-label
search inside `create-gitlab-issue` found the first ticket and reused it. That
backstop only works once the first ticket exists — if the sibling is still inside
its (up to 240s) agent call, the search finds nothing and **two tickets are
created**. It also burns a full second agent call and workflow slot every time.

**Fix.** Claims now record `claimed_at`. In the held-but-unticketed case:

- claim age < `INFLIGHT_GRACE` (900s) → assume a live sibling; poll the claim for
  `issue_iid` every 15s for up to 180s. If it appears → `duplicate=true` with the
  id → append. If not → `duplicate=true` with an *empty* id, handed to the
  fingerprint-resolving append path (F3).
- claim age ≥ grace → genuinely abandoned; CAS-retry as before.
- a claim written before this fix has no `claimed_at` and is treated as old, so
  an in-place upgrade cannot deadlock.

**Verified.** Same two-signal scenario, post-fix:

```
Claim triage-dedupe-18698a19… is 1s old (< 900s): assuming a live sibling
workflow owns it; polling for its ticket id.
Sibling workflow published ticket 515 after 60s: appending instead of creating.
```

One ticket (#515), one correlated append. No second agent call.

---

## F3 — Silent evidence loss on a duplicate with no recorded ticket id

**Symptom.** `append-correlated-evidence` was gated on:

```yaml
when: "… .duplicate}} == true && '{{… .issue-iid}}' != ''"
```

A duplicate whose claim carried no `issue_iid` matched neither branch — not
create, not append — so the later signal's evidence was **discarded with the
workflow still reporting `Succeeded`**. F2's fix makes this state reachable by
design (the deliberate "sibling has not published yet" hand-off), so it had to be
closed at the same time.

**Fix.** Append now runs for **every** duplicate. If it is handed an empty id it
resolves the ticket itself by `triage-fingerprint-<16>` label, retrying 6 × 20s
while the sibling finishes. If it still cannot find one it **exits 1** — a Failed
workflow you can see, rather than silence.

---

## F4 — Event filter ignored Normal vs Warning

Vector's `incident_signals` matched events on `reason` alone. The envelope did
not carry the event `type` at all, so a `Normal` event that happened to use a
reason string in the allow-list would have been triaged as an incident. (The v3
track under `kustomize/` does check this; the proven v2 track did not.)

**Fix.** `.event_type` is extracted from the event body, carried in the envelope,
rendered in the ticket, and the filter's event branch now requires
`.event_type == "Warning" || .event_type == ""`. The empty case is accepted
deliberately so an event source that does not surface `type` degrades to the old
reason-only behaviour instead of silently dropping every event.

---

## F5 — No probes on the collectors

Neither Alloy nor Vector had a readiness or liveness probe, so a wedged collector
stays `Running` and `Ready` while delivering nothing — the failure mode that is
hardest to notice, because the tickets simply stop.

**Fix.** Vector probes `/health` on its API port 8686. Alloy probes `/-/ready` on
12345 — which also required adding `--server.http.listen-addr=0.0.0.0:12345`,
since Alloy's default bind is `127.0.0.1` and kubelet cannot reach it. Both
verified passing on red.

---

## F6 — Signal coverage is narrower than it looks (deliberate, but know it)

Two separate limits:

**Namespace scope.** `01-alloy.yaml` collects from exactly one namespace
(`agentic-triage-proof`) — both the pod-log relabel `keep` rule and
`loki.source.kubernetes_events namespaces = [...]`. Nothing outside it is seen.
That is right for a pilot and wrong for a fleet. `## Fleet scope` at the bottom of
`01-alloy.yaml` says precisely what to change.

**Reason allow-list vs what this cluster actually emits.** Surveyed live:

| count | reason |
|---|---|
| 1170 | `PolicyViolation` |
| 1 | `BackOff` |

`PolicyViolation` (Kyverno) is **99.9% of all Warning events on this cluster** and
is **not** in the allow-list. Excluding it is almost certainly correct — a policy
violation is a governance finding, not a workload incident, and admitting it
would bury real incidents — but it should be a *decision*, not an accident. If
you want it, route it to a different topic and a different ticket template, not
into the incident path.

The allow-list itself is reasonable and matches the Sensor filter exactly (Vector
and Argo agree, which is worth keeping true if you edit either).

One genuine platform gap, carried over from the earlier proof and re-confirmed:
**a single-container cgroup OOM kill emits no `OOMKilled` Event on this kubelet**
— it is visible only in container status, which Alloy does not read. It is caught
indirectly, because a pod that OOMs under `restartPolicy: Always` produces a
`BackOff` event on the next restart. Check whether your work cluster's kubelet
behaves the same before assuming that class routes.

**Application logs** are covered and working: the log branch matches a broad
error-ish regex over the redacted message. At fleet scope that regex is broad
enough to match routine INFO lines containing the word "error" — tighten it
before widening namespace scope, or ticket volume will follow Kafka volume.

---

## F7 — Fingerprint reuse outlives the 24h claim

The claim ConfigMap expires after 24h, but `create-gitlab-issue` searches for any
**open** issue with the same `triage-fingerprint-*` label, with no age bound.
Observed live: a fresh signal appended to issue **#456**, opened during the
earlier proof run days before, because it was still open.

That is defensible — same fingerprint, still-open ticket, therefore still
unresolved — but it means a recurrence weeks later lands on a stale ticket rather
than opening a fresh one, and "First seen" on that ticket is not the first time
*this* occurrence happened. If you want a fresh ticket per TTL window, add a date
component to the fingerprint label. Left as-is deliberately; flagging it so it is
not a surprise at work.

---

## F8 — The redaction scrub over-redacts prose

Observed in the healthy ticket #516. The agent wrote "missing secret" as ordinary
prose; the ticket rendered:

> …(bad config, missing env var, failed readiness on a dependency, missing [REDACTED])

The scrub includes a bare-word rule —
`\b[\w-]*(?:password|passwd|pwd|token|secret|bearer|api[-_]?key)[\w-]*\b` —
which matches the English word "secret" with no value attached.

**Deliberately not fixed.** The three other rules (`key=value`, bearer, cookie)
are the real leak vectors; the bare-word rule is the belt-and-braces catch for a
credential that does not match a `key=value` shape. Weakening it to make prose
read better trades a security property for a cosmetic one, which is the wrong
direction by default.

If your reviewers find it too noisy, the narrow change is to apply the bare-word
rule only to `$i.evidence.representative_log_lines` (untrusted workload text) and
not to `$diagnosis` (text the agent generated). Note that the evidence has
*already* been redacted upstream in Vector before it ever reaches the ticket, so
this is defence-in-depth either way — make it a conscious decision, not a drift.

---

## Efficiency — measured, not asserted

Live Vector counters from the verification window:

```
alloy_otlp              received  46
normalize               received  46
incident_signals        received  46   passed 35   discarded 11  (intentional=true)
suppress_exact_repeats  received  35   passed  3   discarded 32
kafka                   produced   3
```

46 raw records in → **3** produced to Kafka. The policy filter drops 11 and is
*metered*; repeat suppression collapses 35 → 3. Both counters are exported on
`:9598` and printed by `scripts/verify.sh`, so "we are not spamming the system"
is a number you can read, not a claim.

Bounds in force downstream: Sensor `rateLimit` 5/minute per sensor, and a
WorkflowTemplate semaphore of 5 concurrent instances scoped to this template only
(it deliberately does not touch the shared cluster-wide
`workflow-controller-configmap`).
