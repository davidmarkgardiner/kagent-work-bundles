# Critique Feedback: Vector Routing Design

Review of the Vector-between-Kafka-and-Argo design against the inputs listed in
`CRITIQUE-PROMPT.md`. The spike works, but several headline claims in the README
are **not** present in the deployed manifests. The single most important finding
is that the production normalizer does not do what the design document says it
does.

---

## Top Risks (ordered by severity)

### 1. Deployed normalizer has no filter and no dedupe (CRITICAL)

`manifests/01-vector-alertmanager-normalizer.yaml` wires the Kafka sink directly
to the `normalize_alert` transform:

```text
sources.alertmanager_raw -> transforms.normalize_alert -> sinks.alertmanager_triage
```

There is **no `filter` transform and no `dedupe` transform** in the deployed
config. The filtering and deduplication that the README sells as the core value
(`README.md` lines 112-113, 143-144, 151-152, 198-200) exist **only** in
`tests/vector-example-test.yaml` (`accepted_events`, `suppress_duplicates`).

Consequence: in the real cluster, every record — including resolved alerts and
exact duplicates — is published to `alertmanager-events-triage`. The "noise
reduction before Argo" claim is false for the deployed artifact. Resolved-alert
suppression currently happens only because the Sensor in
`02-...yaml` filters `body.alertmanager.status == "firing"`, i.e. **after** the
event reaches the topic and EventBus, not before.

**Fix before any rollout:** port `accepted_events` and `suppress_duplicates`
into `01-...yaml` and prove parity with a test (see Missing Tests).

### 2. Two divergent copies of the VRL that drift silently (CRITICAL)

The normalization logic is duplicated in:

- `manifests/01-vector-alertmanager-normalizer.yaml` (deployed)
- `tests/vector-example-test.yaml` (tested)

They are already different (the test config has the filter+dedupe stages; the
deployed config does not; `reason` derivation differs at
`01` line 110 vs test line 47/87). The test suite therefore validates a config
that is **not the one running in the cluster**. The README explicitly calls the
examples "the acceptance test shape for the Vector layer" (line 146) — that claim
is not true while the configs differ.

**Fix:** single source of truth for the VRL. Either mount the same ConfigMap in
the test, or generate both from one fragment, plus a CI check that fails if they
diverge.

### 3. `automation_allowed` is granted from untrusted alert labels (CRITICAL — production safety)

`01-...yaml` lines 169-171:

```text
if .severity == "critical" && .environment == "prod" && .route_domain != "security" {
  .automation_allowed = true
}
```

`severity` and `environment` are read straight from alert payload labels
(lines 64, 68). Alert labels are **not a trust boundary** — any exporter, rule,
or actor that can fire an alert can set `severity=critical, environment=prod` and
flip on write-capable automation. There is:

- no allowlist of alert names/reasons that may ever be auto-remediated,
- no blocklist (Question 4 in the prompt has no implementation behind it),
- no separation between "this alert is critical" and "this alert is safe to act
  on automatically".

Critical severity and safe-to-automate are different axes and must not be
collapsed. **Fix:** default `automation_allowed=false` always; only set true for
an explicit, version-controlled allowlist of `(alert_name, namespace)` pairs that
have a vetted runbook. Keep the final write gate in Argo regardless (README line
410 already says this — good — but the Vector default must not be permissive).

### 4. Triage Sensor drops the normalized routing fields (HIGH)

`02-...yaml` lines 105-109 pass **only** `body.alertmanager` into the workflow:

```yaml
parameters:
  - src:
      dataKey: body.alertmanager
    dest: spec.arguments.parameters.0.value
```

So `target_agent`, `route_key`, `routing_reason`, `dedupe_key`,
`automation_allowed` are computed and then thrown away on the real path. The
entire "Argo reads `target_agent`/`route_key` directly" value proposition
(README lines 154, 306-309, 403) is realized only in the **route-verification**
Sensor (`03-...yaml`), not in the actual triage Sensor. The production workflow
still receives a raw-ish Alertmanager sub-object and must parse it.

**Fix:** the real triage Sensor must pass the normalized top-level fields, the
same way `03-...yaml` does.

### 5. Dedupe is a 1000-event in-memory LRU with no time window and no durability (HIGH)

`tests/vector-example-test.yaml` lines 129-137: `num_events: 1000`, no TTL. This
is not a "short-window" suppressor as the README describes (lines 198, 152) — it
is a count-bounded cache. Failure modes:

- Vector restart (single replica, see #7) wipes the cache → duplicate flood on
  recovery / offset replay.
- High event volume evicts keys before the "window" anyone imagined expires.
- No notion of time at all, so behavior depends on throughput.

The README's own "Deduplication Position" section (lines 192-206) says Vector
must not be the only durable dedupe layer — agreed — but the manifests do not
implement the durable layer either. **Fix:** make the dedupe explicitly
time-bounded, document the window, and keep durable incident grouping downstream.

### 6. `dedupe_key` collisions and flap-evasion (HIGH)

`dedupe_key = cluster:namespace:service:alert_name:severity` (line 175).

- `cluster` defaults to `"unknown"` for Grafana (proven by the test assertion
  `unknown:payments:checkout-api:HighCPUUsage:warning`, test line 74). Two
  different physical clusters' Grafana alerts will share `cluster=unknown` and
  **dedupe against each other** — real alerts suppressed.
- `severity` is in the key, so an alert flapping warning→critical produces a new
  key and is **not** deduped — exactly when you most want suppression.

**Fix:** require a real `cluster`/`environment` for any record that is allowed to
automate; drop `severity` from the dedupe key (or justify it explicitly).

### 7. Single replica, no probes, SPOF (MEDIUM)

`01-...yaml`: `replicas: 1`, no `livenessProbe`/`readinessProbe` despite the API
on `:8686`. A hung Vector will not be restarted by Kubernetes and will silently
stop draining raw topics. No PDB, no HPA. **Fix:** add liveness/readiness probes
against `:8686`, document the at-least-once / restart story, and decide on a
durable-dedupe backend before relying on more than one replica.

### 8. No metrics emitted for the value story (MEDIUM)

Question 6 (audit dedupe) and Question 7 (prove MTTA/MTTR) have no
implementation. Vector exposes `internal_metrics` and
`component_discarded_events_total`, but nothing scrapes `:8686` and no baseline
"workflows before Vector" was captured. `route_key` is described as feeding
Grafana dashboards (line 332, 407) but no dashboard/recording-rule ships here.
**Fix:** add an `internal_metrics` source + Prometheus sink/scrape, emit a
"suppressed" counter keyed by `route_key`, and capture a pre-Vector workflow-count
baseline so the reduction is measurable.

### 9. Credential / ACL boundary is one principal for read+write (MEDIUM — security)

Vector uses a single `confluent-credentials` key/secret for both consuming the
raw topic and producing the triage topic (`01-...yaml` lines 224-233). Argo's
EventSource reuses the same secret (`02-...yaml` lines 33-38). No least-privilege
split. **Fix:** separate Confluent service accounts — Vector: read
`alertmanager-events`, write `*-triage`; Argo: read `*-triage` only. Credential
handling otherwise looks correct (secretKeyRef, no plaintext, sasl_ssl) and the
README's "don't commit rendered creds" warnings (lines 478-488) are good.

### 10. Replay/retention undefined (LOW-MEDIUM)

The "keep raw topics for replay" claim (lines 97-99, 114) has no topic retention
config in the manifests, and replay through the committed consumer group
`vector-alertmanager-normalizer` requires an offset reset that is not documented.
"Replay" is asserted, not demonstrated.

---

## Answers to the Prompt Questions

1. **Kafka-first default?** Yes — keep it. Raw capture before transform gives
   replay/audit/loose coupling. Direct-to-Vector only for low-criticality, as the
   README says. No change needed to the decision; do capture the replay procedure.
2. **One topic vs route topics?** Start with one normalized topic — correct call.
   But fix #4 first: today the single-topic path doesn't even forward
   `target_agent`, so the simplicity argument is moot until the contract is
   actually consumed.
3. **Is `service` a strong enough owner signal?** No. It is read from alert
   labels that default to `unknown` and are set by whoever wrote the rule. Back
   ownership with a maintained inventory (namespace→team map, Backstage/CMDB),
   and treat labels as a hint, not the source of truth. The `unknown` fallback to
   `sre-triage-agent` is sensible as a safety net.
4. **Which alerts blocked from automation?** Currently only the `security`
   domain is implicitly excluded; everything critical+prod is auto-allowed. This
   is backwards. Default-deny, allowlist explicitly (see #3).
5. **Vector down/restarted/misconfigured?** Raw Kafka buffers, so no alert loss —
   good. But dedupe cache resets (duplicate flood), no probes to catch a hang,
   and a misconfigured VRL silently changes routing. Add probes, durable dedupe,
   and config-parity tests.
6. **How to measure/audit dedupe?** Not currently possible — add internal
   metrics and a suppressed-events counter (see #8).
7. **Evidence for stakeholders?** Capture pre-Vector workflow counts as a
   baseline, emit `route_key`/suppressed metrics, and show before/after workflow
   churn and time-to-correct-agent. None of this baseline exists yet.

---

## Specific Changes Required Before Production

1. Merge `accepted_events` + `suppress_duplicates` into `01-...yaml`; delete the
   second VRL copy or generate both from one source. (#1, #2)
2. Default `automation_allowed=false`; gate true on an explicit allowlist. (#3)
3. Make the triage Sensor forward normalized top-level fields like `03-...yaml`
   does. (#4)
4. Time-bound the dedupe and document the window; keep durable grouping
   downstream. (#5)
5. Require real `cluster`/`environment` before automation; reconsider `severity`
   in `dedupe_key`. (#6)
6. Add liveness/readiness probes on `:8686`. (#7)
7. Add internal-metrics scrape + suppressed counter + baseline capture. (#8)
8. Split Confluent service accounts read vs write. (#9)
9. Document raw-topic retention and the replay/offset-reset procedure. (#10)
10. Disable the dual-Sensor steady state (README lines 258-268 already flag this).

---

## Missing Tests

- **Config-parity test:** assert deployed `01` VRL == tested VRL (currently they
  differ and nothing catches it).
- **Deployed-config test:** run the actual `01` ConfigMap through the example
  harness, not a hand-maintained copy.
- **Alertmanager resolved filtering:** `run-vector-example-tests.sh` only tests
  Grafana resolved (`.state=ok`, line 87). No test for Alertmanager
  `status=resolved`.
- **`automation_allowed` matrix:** prove it is false for critical+prod alerts
  that are not on the allowlist; prove security domain never auto-allows.
- **Dedupe-key collision test:** two clusters' Grafana alerts must NOT dedupe
  against each other; flapping severity must be handled deliberately.
- **Restart behavior:** duplicate suppression across a Vector restart (expected
  to fail today — that's the point).
- **CI wiring:** `run-vector-example-tests.sh` needs Docker and is not in CI; add
  it to the pipeline or it will rot.

---

## Go / No-Go

**Dev cluster: GO, conditional.** The spike is genuinely validated end-to-end and
Kafka-first is the right shape. Acceptable for dev provided #1, #2, #7 are done
first (otherwise the deployed config does not match the documented behavior and
dev "evidence" will mislead). Treat dev explicitly as the place to land the
filter+dedupe parity fix and probes.

**Production cluster: NO-GO** until at minimum #1–#6 and #9 are closed. The
blocking issues are: filter/dedupe not in the deployed config, `automation_allowed`
granted from untrusted labels, normalized routing fields discarded by the real
Sensor, non-durable dedupe with collision/flap bugs, and a shared read/write
Kafka principal. Each is a correctness or safety defect, not a polish item.
Re-review after the changes land with a fresh end-to-end run on the **deployed**
config.
