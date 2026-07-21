# Worksheet — Vector/Kafka → Argo → Agents → GitLab

Working sheet for the next block of work. Ordered. Do not skip a gate.

Proven so far: Alloy → Vector → Kafka → Argo, payload arrives in the pod.
Not proven: anything downstream of that pod.

---

## Gate order — corrected

The numbering below is historical. **Gate 1 must run before Gate 0.** P0-2 is a
correlation proof, and correlation keys on `dedupe_key`, which keys on `.cluster`
— which is `""` until Gate 1 is fixed. You cannot prove "exactly one ticket
across clusters" while two clusters hash to the same key. Re-proving P0-2 first
would prove it on a broken key and produce a green marker that means nothing.

Real order:

```
Decide idempotency store  →  Gate 1 (cluster identity)  →  Gate 0 (re-prove P0s)
  →  Gate 2 (payload contract)  →  Gate 3 (topic)  →  Gate 4 (routing)
  →  Gate 6 (evals)  →  Gate 5 (HITL, scoped to writes)  →  Gate 7 (fleet)
```

---

## Gate 0 — re-prove the P0 defects (BLOCKS EVERYTHING)

Source: `next-phase-end-to-end/KNOWN-DEFECTS-AND-REPROVE.md`

Both defects are patched in `reference-config/` but were never re-run. The
`VERIFICATION-2026-07-13.md` PASS predates the stress test that failed the
security gate — it is not current evidence.

- [ ] **P0-1 redaction** — synthetic secret-shaped strings (password, token,
      api-key, Authorization/Bearer, structured JSON, multiline, base64) reach
      neither Kafka, agent prompt, workflow logs, nor GitLab. Unprovable
      redaction ⇒ quarantine, not ship.

### P0-1 is NOT fixed — verified, not assumed

Tested against Vector 0.44.0 using the exact `redact()` filters from
`reference-config/02-vector.yaml`:

| Input | Output |
|---|---|
| `password=hunter2` | `[REDACTED]` ✅ |
| `Authorization: Bearer abc123xyz` | `[REDACTED]` ✅ |
| `api_key: sk-live-9999` | `[REDACTED]` ✅ |
| `{"password": "hunter2"}` | `{"password": "hunter2"}` ❌ **LEAKS** |
| `{"token":"eyJhbGciOi"}` | `{"token":"eyJhbGciOi"}` ❌ **LEAKS** |

**Cause:** the filter is `(password|token|…)\s*[=:]\s*[^\s,;]+`. JSON quotes the
key — `"password":` — so a `"` sits between the keyword and the colon and
`\s*[=:]` never matches. Every filter in the list shares this hole.

**Why it matters:** Kubernetes container logs are predominantly structured JSON,
and `KNOWN-DEFECTS-AND-REPROVE.md` names "structured JSON" explicitly in the
P0-1 re-prove list. The config marked "fix applied" does not cover the case the
gate requires. This is a live plaintext-secret path to Kafka and GitLab.

- [ ] Extend filters to cover quoted-key JSON (`"key"\s*:\s*"[^"]*"`), and
      re-test every shape in the table above plus multiline and base64.
- [ ] Do not rely on regex alone for the envelope. `redact()` guards the
      free-text `representative_log_lines` only — the allow-listed envelope is
      the actual control. Keep both; prove both.
- [ ] **P0-2 correlation** — `Failed → ErrImagePull → BackOff` and
      `log-then-BackOff` each yield exactly ONE ticket carrying BOTH log and
      event evidence. Later `BackOff` appends; does not open ticket #2; is not
      dropped.
- [ ] Markers set: `REDACTION_REPROVEN_NO_SECRET_LEAK: yes`,
      `CORRELATION_REPROVEN_LATER_BACKOFF_APPENDS: yes`

Never use a real credential. Synthetic only.

---

## Gate 1 — cluster identity + the dead `??` fallbacks

`reference-config/02-vector.yaml:22`

```coffee
.cluster = to_string(.attributes.cluster) ?? "red"
```

**Every `?? "default"` in this config is dead code for a missing field.**
Verified on Vector 0.44.0:

- `??` is VRL's **error**-coalescing operator. It fires when the left side
  *errors* — not when it is null or absent.
- A missing field reads as `null`; `to_string(null)` returns `""` **and
  succeeds**. So `??` never fires.
- `to_string()` is fallible, so `??` is still required to compile
  (error E103, "unhandled fallible assignment") — which is why the idiom looks
  correct and reviews clean. It compiles for one reason and reads as if it does
  something else.

Proven: with `attributes.cluster` absent, the join yields `":myns:mypod"` —
cluster is `""`, never `"red"`. Two clusters both missing identity produce a
byte-identical `dedupe_key` (`sha2("":kube-system:coredns-abc")` →
`092d508d…`), so distinct incidents on distinct clusters merge into one ticket.

The collision is real. My earlier description of it ("every cluster labels
itself red") was wrong — no cluster is ever mislabelled as the real `red`
cluster. Empty is the actual failure, and it is at least loudly broken rather
than plausibly wrong.

Same defect applies to `.namespace ?? "unknown"`, `.service ?? "unknown"`,
`.container ?? ""`, `observed_timestamp` — all silently `""` when the attribute
is missing, never the intended default. `.reason` is the exception: it tests
`event_reason == ""` explicitly, so it works. Note that Gate 4 routing keys on
`namespace` — an empty namespace silently takes the default-agent path.

- [ ] Replace the `??` default idiom with an explicit null/empty test, e.g.
      `x = to_string(.attributes.cluster) ?? ""` then
      `.cluster = if x == "" { <handle> } else { x }` — the pattern `.reason`
      already uses correctly.
- [ ] Cluster identity comes from a per-cluster value (Alloy external label /
      Vector env var / Helm value), not a literal default.
- [ ] Missing cluster identity ⇒ quarantine + visible metric. Never a default
      that happens to be a real cluster name.
- [ ] Prove: two clusters, same namespace + pod name, two distinct
      `dedupe_key`s, two tickets.
- [ ] Audit every `??` in the config for the same false-default assumption.

---

## Gate 2 — payload contract: envelope → workflow

The single biggest gap. Pick ONE adapter and write the contract down.

**What the workflow expects today** (`a2a/smart-triage-fanout-demo/workflow-template.yaml`,
`normalize-incident`, ~line 432):

```
$a.labels.alertname / severity / cluster / namespace / workload / pod /
container / event_type / event_reason / run_id
$a.annotations.event_message / log_reason / failure
```
Alertmanager webhook shape: `body.alerts[]` each with `labels{}` + `annotations{}`.

**What Vector emits today** (`reference-config/02-vector.yaml`, ~line 65):

```
{ cluster, namespace, pod, container, reason, severity, signal_kind,
  evidence{ representative_log_lines, event_summary, ... },
  dedupe_key, delivery_key }
```
Flat. No `alerts[]`. No `labels`/`annotations`.

### What actually happens — verified, and worse than "fields render unknown"

`workflow-template.yaml:370`

```sh
alert_count="$(jq '.alerts // [] | length' /tmp/alert-payload.json 2>/dev/null || echo 0)"
if [ "$alert_count" -gt 0 ]; then
```

The flat envelope has no `.alerts`, so `alert_count` is `0` and the whole branch
is **skipped**. The `$a.labels.*` jq never runs. The step takes the `else` branch
and emits `ALERT_INGESTED: no`.

**The dedup ConfigMap creation is inside that same `if` block** (lines 372–414).
So on the Vector path:

- dedup never executes;
- `/tmp/duplicate.txt` keeps its pre-set `"false"`;
- `when: duplicate == false` passes;
- **all 8 specialists fan out on every Kafka message, with zero idempotency.**

This is a CRITICAL correctness + cost defect, not a field-mapping bug. Every
"exactly one ticket" property is absent on this path by construction.

Choose:

- [ ] **Option A — adapt in Vector.** Emit an Alertmanager-shaped envelope so the
      existing workflow jq works untouched. Changes the component that already
      works, in one place per cluster × N worker clusters. Risk: `labels{}` /
      `annotations{}` are open maps by nature — nesting fields there invites
      re-introducing the raw passthrough the flat allow-list exists to prevent.
      The re-audit cost is real but smaller than first stated: the redacted
      `representative_log_lines` content does not change, only its nesting.
- [ ] **Option B — adapt in the workflow.** Branch `normalize-incident` on the
      existing `alert_source` param. Keeps the envelope flat and the allow-list
      intact; one place to change, not N. Risk: adds branching to the least-proven
      component in the system, and the dedup block must be restructured (it
      currently only exists inside the `alerts[]` path).
- [ ] **Option C — adapt in the Sensor (consider before choosing A or B).**
      The Sensor already maps `dataKey: body` → `alert_payload`. Argo Events
      supports payload transformation at the trigger. Reshape there and neither
      the fleet-wide Vector config nor the workflow jq is touched. Least blast
      radius; verify Argo Events' transform is expressive enough first.

**Unresolved — decide deliberately.** A second reviewer argued A over B on
"change the proven side, not the unproven side." That heuristic is weakened by
Gate 0: Vector's redaction is proven *broken*, so "proven" is doing little work
here. Against A: Vector is deployed on every worker cluster, so A is an N-cluster
change and B is a one-cluster change. Option C may dominate both.

Then:

- [ ] Write the contract as a file, both directions, field by field. It is the
      interface between two teams' configs — not tribal knowledge.
- [ ] Fixture test the adapter: real captured Kafka message in, asserted
      normalized fields out. Not a live-cluster eyeball.
- [ ] Prove `service` renders (it showed empty on some fixtures — open P1 in
      `PAYLOAD-FIELD-PROOF.md`).
- [ ] Ticket carries the **rendered safe contract**, not raw JSON envelope
      (open P1, same file).

---

## Gate 3 — separate topic + separate consumer path

Keep this flow off the LGTM topic. Right call.

- [ ] New topic, e.g. `worker.evidence.v1` (version it — the envelope will
      change).
- [ ] Own consumer group. Never share a group with the LGTM consumer.
- [ ] Own EventSource + Sensor. Copy `sensors/alertmanager-to-fanout-sensor.yaml`
      and change filter + trigger params; do not overload the existing one.
- [ ] DLQ / quarantine topic + a visible metric on drops. A silent near-miss is
      the failure mode you cannot debug later.
- [ ] Retention + data classification decided (open in `FRONT-SHEET.md`).
- [ ] Sensor `rateLimit` sized for fleet, not demo (currently `5/Minute`).

---

## Gate 4 — namespace → specialist routing (build it; it doesn't exist)

`next-phase-end-to-end/PHASE-6-namespace-by-namespace-specialist-routing.md`
says it outright: *"this does not exist yet, design it."*

Reality check on the old workflow: `smart-triage-fanout` **fans out to all 8
specialists unconditionally**. It is not a router. `03-argo.yaml` hardcodes a
single agent endpoint. There is no routing logic to lift and shift — it has to
be written.

- [ ] Pick the mechanism:
      - **Selector step in the workflow** — envelope `namespace` (or a mapped
        label) → agent URL via a lookup. One workflow, one lookup step.
        **Preferred** — one object to reason about.
      - **Per-namespace Sensor** — clearer isolation, many more objects.
- [ ] Map lives as **data** (ConfigMap), not hardcoded per copy.
- [ ] Unmapped namespace → generic `k8s-readonly-agent` fallback. Visible, never
      a silent fail.
- [ ] Every routed agent stays **read-only**. Specialist = deeper diagnosis, not
      write access. Auto-remediation is a separate scope decision.
- [ ] Decide fan-out vs route per signal: does one incident hit one specialist,
      or the commander fans out? The commander agent
      (`smart-triage-incident-commander`) already exists for the
      "don't know what this is" case you described — wire the fallback to it.

Onboard **one namespace at a time**:

| Namespace | Specialist | State | Failure modes tested | Ticket proof |
|---|---|---|---|---|
| external-dns | _(discover)_ | pending | | |
| kyverno | _(discover)_ | pending | | |

Do not start the next until the previous is green with evidence.

---

## Gate 5 — human in the loop

Existing pieces, already built, currently unwired to triage:
`a2a/kagent-hitl-skills-demo/` — suspend/resume, approval agent, callback
EventSource (`teams-hitl-callback-eventsource-svc.argo-events:12000`), mock bot.

- [ ] Decide where the gate sits: after diagnosis, before ticket? Or only in
      front of any future write action? (Read-only triage may not need a gate
      at all — a suspended workflow per incident is a fleet-scale liability.)
- [ ] Lift the suspend/approve pattern into the triage workflow.
- [ ] Approval callback path: GitLab → callback EventSource → resume. The demo
      uses a mock bot; the real path needs deciding.
- [ ] **Timeout behaviour.** A suspended workflow nobody approves must expire
      cleanly, not pin a slot forever. `activeDeadlineSeconds: 1200` today —
      too short for a human, so this needs its own number.
- [ ] Approver identity + audit: who approved, when, recorded where.

---

## Gate 6 — scoring / evaluation

`observability/agent-evals/` already has scoring scripts, lifecycle cases, a
fleet exporter and dashboards. The fanout template **already mounts them** via
the `agent-eval-runtime` ConfigMap (`score-lifecycle-run.py`,
`collect-lifecycle-evidence.py`, `summarize-agent-scores.py`).

- [ ] Confirm the ConfigMap `agent-eval-runtime-files` actually exists in the
      target cluster — the template mounts it unconditionally as a volume.
      **Correction:** this does *not* fail fast at pod-create as first stated
      here. The API accepts the pod; kubelet then retries the mount forever and
      the pod sits in `ContainerCreating` with `FailedMount` events. That is the
      worse failure mode — a silent slot-pinning hang, not a loud error. Mark it
      `optional: true` if the eval scripts are not required for triage to run,
      or pre-flight the ConfigMap's existence.
- [ ] Wire scoring into the Vector-fed path, not just the demo path.
- [ ] Decide online vs offline scoring split
      (`OFFLINE-ONLINE-EVALUATION-DESIGN.md` exists — read before re-deciding).
- [ ] Baseline the scores **before** fleet rollout. Without a baseline the
      Phase 7 fleet metrics have nothing to compare against.
- [ ] Access control on eval metrics (`EVAL-METRICS-ACCESS-CONTROL-DESIGN.md`
      exists, open).

---

## Gate 7 — fleet rollout (Alloy + Vector, all worker clusters)

Only after 0–6 are green.

- [ ] Alloy + Vector deploy together in one dedicated namespace per worker
      cluster. Note: `reference-config` currently uses `argo-events` — that is a
      management-side name. Pick the worker namespace deliberately.
- [ ] Per-cluster identity injected at deploy (see Gate 1).
- [ ] Golden-path template frozen from the demo namespace; per-app change is the
      **specialist agent only**, never the collection recipe.
- [ ] Watch during rollout — pause onboarding on any degradation:

| Metric | Baseline | Threshold |
|---|---|---|
| Kafka consumer lag | | |
| Consumer-group queue age | | |
| Workflow concurrency | | |
| DLQ / quarantine rate | | |
| Agent concurrency | | |
| Model / A2A circuit breaker trips | | |

- [ ] Rollback is one action: disable the producer/consumer route. Existing
      Alertmanager human paging stays untouched throughout.

---

## Open decisions — owner needed, not code

From `FRONT-SHEET.md`, still unresolved:

- [ ] **Durable TTL / idempotency store.** "Decision required." Everything
      idempotent depends on it. This is the one that blocks the most.
- [ ] **Data classification + retention** for evidence in Kafka and GitLab.
- [ ] **Office rollout** blocked pending owner acceptance of critique
      corrections.

---

## Found in review — not in the original plan

Severity-tagged. Each needs an owner or a gate.

- **CRITICAL — "append to existing ticket" is not implemented.** The workflow
  only creates or suppresses. There is no step that fetches an existing GitLab
  ticket and appends a later `BackOff`. P0-2's stated requirement ("the later
  BackOff appends to the original incident") has no implementation to re-prove.
  Gate 0 cannot pass until this is built.
- **CRITICAL — the ConfigMap dedup is not atomic and is truncated.**
  `dedup_key` is `sha256(...)` cut to **16 hex chars / 64 bits**
  (`workflow-template.yaml:373`). Birthday-bound collisions at fleet volume mean
  two *different* incidents silently share a ticket. The create-then-409 pattern
  also races: the 409 only helps *after* a collision. No TTL — ConfigMaps
  accumulate forever in `argo`.
- **HIGH — `delivery_key` includes the log text, so suppression rarely fires.**
  `delivery_key = sha2(dedupe_key : reason : representative_log_lines)`
  (`02-vector.yaml:63`). Log lines carry timestamps and variable text, so nearly
  every record hashes unique and `suppress_exact_repeats` only ever catches
  byte-identical lines. This is in direct tension with the P0-2 fix intent —
  the fix widened the key to stop over-suppression and overshot into
  under-suppression. Decide the correlation key deliberately; it is the crux of
  both P0-2 and the ticket noise budget.
- **HIGH — `suppress_exact_repeats` is per-pod, not shared.** 10,000-event cache
  local to each Vector pod. Multiple replicas do not share state; duplicates
  escape on restart and on rebalance.
- **HIGH — no Kafka producer reliability config.** Sink sets SASL/SSL only. No
  `acks`, no retries, no idempotent producer, no DLQ. Evidence can be lost
  silently — which breaks the "lose no evidence" clause in Gate 0's own
  re-prove list.
- **HIGH — malformed input is silently swallowed.** `parse_json(message) ?? {}`
  turns bad input into an empty event. No DLQ, no metric. Contradicts Gate 3's
  "visible drop metric" requirement.
- **HIGH — `parallelism: 4` against 8 unconditional specialists** creates
  head-of-line blocking inside every workflow, before any fleet load.
- **SECURITY HIGH — Kafka message keys are a durable leak surface.**
  `key_field` is `dedupe_key` / `delivery_key`, and `delivery_key` hashes
  `representative_log_lines`. If redaction misses (see Gate 0 — it does), the
  secret is hashed into a retained, compacted Kafka key. Hashing is not
  redaction: a low-entropy secret is brute-forceable from the digest.
- **SECURITY — redaction gaps beyond the JSON hole.** No coverage for base64
  blobs, JWTs, or PEM private keys. Gate 0's list says test them; the config
  does not implement them.
- **MEDIUM — `evidence.event_summary` is set to `.reason`, not a summary.**
  Cosmetic, but a sign the envelope is under-specified against its own contract.

---

## What you didn't mention that will bite

1. **Idempotency store is undecided** and every "exactly one ticket" claim in
   Gates 0/2/4 rests on it. Decide it before Gate 0, or Gate 0 proves nothing
   durable.
2. **Suspended workflows at fleet scale.** HITL on read-only triage may be
   solving a problem you don't have, while creating a real one — hundreds of
   pinned workflow slots waiting on humans who aren't watching. Gate the writes,
   not the reads.
3. **Envelope versioning.** The contract in Gate 2 will change. Version the
   topic and the envelope now, or you get a breaking change with a live fleet
   and no way to run both shapes.
4. **Ticket noise budget.** No stated cap on tickets/hour to GitLab. Fleet
   rollout with no ceiling is how the boards become unusable and people stop
   reading them — which kills the value you're trying to demonstrate.
5. **Agent cost/concurrency at fleet scale.** Fan-out to 8 specialists per
   incident × fleet volume. The circuit-breaker metric is in the table; the
   budget is not.
