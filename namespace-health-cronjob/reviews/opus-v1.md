# Review: Namespace health job, PLAN.md Revision 1

**Reviewer:** Claude Opus 5.5 (`claude-opus-5-5`).
**Scope:** This review covers only the supplied plan text. I did not inspect any repository, cluster, Kafka or Argo deployment, and I ran no tests. The input ended with the orchestration Python script; I treated it as non-plan material and did not run it.

## 1. Verdict: REVISE BEFORE BUILD (narrow)

The architecture is the right size. However, two contract gaps let a real outage or a log-only fault produce no outbound signal, and slot identity has collision paths. Revision 2 can fix these in the plan text without a redesign.

## 2. Is one stateless scheduled job appropriate?

Yes. A CronJob that reads the API, applies deterministic rules and publishes one Kafka record is close to minimal. The receiver's ConfigMap receipts are the only retained state. It can be smaller still without losing state, Event or application-log detection:

- **Defer the Loki adapter entirely.** Its backend is unverified. The sampled log path must stand alone.
- **Drop PVC and CronJob reads.** No rule uses them, and ownership resolves through Job and ReplicaSet ownerReferences.
- **Remove request concurrency (4 → 1).** About 30 calls fit easily inside a 120 s deadline. Sequential reads make budget and deadline accounting simple.
- **Sample logs per workload, not per Pod.** Read one application container per workload per run. In the 100-Pod pilot this likely covers every workload within 24 reads. Rotation is then only needed for replicas and overflow, and overflow is reported as deferred.

## 3. Findings

**P0-1: Silent outage path** (§4 rules table; §4 "If a duration cannot be established").
- **Scenario:** StatefulSets and DaemonSets do not reliably expose an `Available` condition with a `lastTransitionTime`. A StatefulSet can sit at zero ready replicas for hours without "continuous unavailability" being established. Rules 100 and 90 then do not qualify. The best outcome is `unknown`, which is local-only, so nothing reaches Kafka.
- **Correction:**
  - Name the timestamp source for each rule:
    - Deployment `Available` `lastTransitionTime`;
    - Pod `Ready` and `PodScheduled` condition transitions;
    - container `state.waiting` plus `lastState.terminated.finishedAt`.
  - When current impact exists but its duration cannot be established, and the controller is older than the grace period, qualify at 90 with `duration: unknown`. Never drop it.
  - Make `unknown` visible outside the job (see P1-1).
- **Test:** A StatefulSet with a bad image and a DaemonSet each stay at zero ready for 15 minutes. Both must appear in the report.

**P1-1: `unknown` and liveness are invisible** (§4 status values; §6 final paragraph).
- **Scenario:** Revoked `pods/log` access or partial API failure looks identical to a quiet hour. Liveness relies on an external monitor that the plan admits may not exist.
- **Correction:** Publish one small envelope every run with `status ∈ {investigate, no_breach_observed, unknown}`. The Sensor starts workflows only when `status == investigate`. A missing slot then becomes a single topic-freshness alert, at a cost of about 24 tiny records per day.
- **Test:** Revoke `pods/log`; an `unknown` record with a coverage reason arrives. Suspend the CronJob; the freshness alert fires within two hours.

**P1-2: Sampled-log bias and dormant rule** (§3 Logs; §4 log rule).
- **Scenario:**
  - Per documented API semantics (verify on the installed version), `sinceTime` plus `limitBytes` returns the oldest bytes in the window, while `tailLines` returns the newest.
  - A chatty container whose 128 KiB covers 90 seconds can never meet "spanning five minutes". High-volume applications can therefore never trigger the log rule.
  - A container with neither structured severity nor an approved pattern is effectively unmonitored, yet it would still be labelled "sampled".
- **Correction:**
  - Declare the read mode.
  - Record the first and last inspected timestamp for each container.
  - If the inspected span is shorter than the required span and errors match, either qualify with lower-bound labelling or mark the container `sampled-insufficient`. Never mark it clean.
  - Mark containers without a matcher as `not-configured`.
  - Exclude declared sidecars, such as mesh proxies, so detection stays application-only.
- **Test:** A container emits 2 MB/min of info logs with one real error per second. The result is `investigate` or `sampled-insufficient`, never `no_breach_observed`.

**P1-3: Slot collisions** (§5 slot paragraph; §2 configurable schedule).
- **Scenario:**
  - `kubectl create job --from=cronjob/…` copies the template but has no scheduled-timestamp annotation. If the resolver falls back to the current hour, a manual run claims the real slot first. The scheduled report then becomes a "conflict".
  - A 30-minute schedule makes every second run a conflict.
- **Correction:**
  - Define `slot_id` as cluster plus scheduled timestamp at minute precision.
  - Use the annotation, or the controller's Job-name minute suffix as a tested fallback.
  - With neither, refuse to publish unless an explicit canary flag selects the canary topic.
  - Any daily cap is a separate receiver check.
- **Test:** A manual Job runs, then the scheduled Job runs in the same hour. The scheduled report is accepted and the manual one is never sent.

**P1-4: "Declared critical workload" has no source** (§4 rule 100).
- **Scenario:** No label, annotation or config defines "critical", so rule 100 cannot fire as designed.
- **Correction:** Define a controller label or an allowlist entry.
- **Test:** A labelled workload at zero available scores 100; an unlabelled one scores 90.

**P2-1: Score semantics** (§2; §4).
- **Scenario:** With the maximum-of-rules design the numbers are ordinal tiers, and a score of 60 can never qualify. Readers may still treat them as arithmetic scores.
- **Correction:** Rename the field `severity_tier`, or document that arithmetic on it is meaningless, and add `qualifying_rules[]`.
- **Test:** A namespace with only 60-tier evidence is not selected and lists that evidence as context.

**P2-2: The three-namespace cap is never exercised** (§3; §6).
- **Scenario:** With only three watched namespaces, nothing is ever deferred.
- **Correction:** Add fourth and fifth fixture namespaces.
- **Test:** See test 5 in section 6.

**P2-3: Namespace UID needs cluster-scoped RBAC** (§6).
- **Scenario:** A namespaced Role cannot `get` Namespace objects.
- **Correction:** Add a ClusterRole for `get namespaces` restricted with `resourceNames`.
- **Test:** The report carries the UID, and access to non-allowlisted namespaces is denied.

**P2-4: Event timestamp precedence** (§3 Events).
- **Correction:** Specify the order `series.lastObservedTime` → `eventTime` → `deprecatedLastTimestamp`. Note in coverage that the default 1-hour Event TTL bounds what history exists.
- **Test:** Repeated Event updates are reported once with the correct latest timestamp.

**P2-5: Argo Events delivery** (§5).
- **Scenario:** EventSource → EventBus → Sensor is at-least-once and can lose messages during an EventBus outage. A receipt therefore proves the report was first observed, not that observation was guaranteed.
- **Correction:** State this limit in the receiver contract.
- **Test:** Extend the §8 broker-outage test to include an EventBus outage.

## 4. Removable machinery and honest limits

**Remove from the pilot:**
- the Loki adapter;
- PVC and CronJob reads;
- request concurrency;
- the external-freshness dependency, once the P1-1 every-run record exists;
- any implied guarantee from producer idempotence. Keep the setting, but it provides nothing across Job restarts.

**Not honestly providable without retained state:**
- distinguishing new from ongoing problems;
- recovery or resolution events;
- two-observation confirmation;
- Event occurrence deltas;
- catch-up of lost hours;
- whole-window log counts without a log store.

Cross-hour investigation suppression is achievable later, and it belongs in the receiver, which already holds state.

## 5. Envelope fit and receiver change

One cluster envelope with up to three namespace findings fits the user's need. The namespace is the correct correlation unit, and 8 KiB is a sensible bound.

**Required receiver change:**
- a new EventSource on the dedicated topic, with its own consumer group and TLS/SASL;
- a new Sensor filtering on `schema == namespace-health.report.v1` and `status == investigate`;
- a receipt WorkflowTemplate that receives the body as a parameter;
- a receiver-namespace Role granting ConfigMap create, get, list and delete, with deletion restricted by label.

**Legacy v2 path:** The `observability.triage.v2` Sensor stays untouched and never subscribes to the new topic. Reusing the existing diagnosis workflow later requires a fan-out adapter. Each selected namespace needs its own claim keyed on `(cluster, namespace, sorted rule ids)` with a cooldown, taken before any model call. The v2 per-Pod claims do not transfer.

## 6. Home-lab falsification tests

1. A StatefulSet and a DaemonSet each stay at zero ready for 15 minutes, and both qualify (P0-1).
2. Ready Pods emit chatty info logs with real errors beyond the byte cap, and there are more workloads than the log budget allows. Each case yields `investigate` or `sampled-insufficient`, and worst-case rotation latency is measured.
3. Kill the publisher after broker acknowledgement but before exit. A retry with a changed body produces one receipt and a visible conflict. A manual Job in the same hour cannot claim the slot.
4. Revoke `pods/log`, then suspend the CronJob. An `unknown` record arrives, the freshness alert fires, and no clean verdict is produced.
5. Five namespaces qualify, with long names and hostile log text. Exactly three are selected, two are deferred, the payload is at most 8 KiB, and no raw text appears in Kafka.

**Workplace prerequisites:**
- Kubernetes version supporting the scheduled-timestamp annotation and CronJob `timeZone`;
- an Argo Events version with Kafka SASL/TLS support;
- the topic, ACLs and consumer group;
- NetworkPolicy egress to the brokers' advertised listeners;
- a critical-label convention;
- per-application log severity or patterns, plus the sidecar exclusion list;
- ClusterRole approval for namespace reads;
- an owner for the freshness alert;
- an approved base image pinned by digest.

## 7. Recommended build order

**Decide before code:**
- the every-run status envelope;
- slot = scheduled timestamp, and refusal for unscheduled runs;
- per-rule timestamp sources and unknown-duration behaviour;
- log read mode, matcher contract, sampling unit and sidecar exclusion;
- the critical-workload declaration;
- deferral of Loki.

**Then build in this order:**
1. Live preflight.
2. Pure rules with offline fixture objects, P0/P1 cases first.
3. Collector with enforced budgets.
4. Report-only run.
5. Kafka and receiver proof.
6. Real-schedule soak over at least three hourly transitions.
7. Workplace bundle.

Agreement with any other reviewer does not replace the live end-to-end evidence required in §8.
