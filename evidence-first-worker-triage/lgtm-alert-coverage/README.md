# LGTM Alert Coverage

## Purpose

This folder is the alert-coverage handoff for the LGTM team. It states what the
current alert set does and does not evidence, asks for the inventory needed to
measure coverage honestly, and gives worked implementation examples for the
gaps.

Nothing here is a deployed rule or evidence of coverage. Every query is a
**candidate** the LGTM team must validate against its installed data sources,
label model, rule-provisioning path and Alertmanager routing.

An objective only counts as covered when it is **defined, scoped, routed and
proven**, as specified by [the baseline](BASELINE.md).

## Read in this order

1. [Alert coverage baseline](BASELINE.md) — the asserted current-alert
   inventory, the gap model per operational domain, and the four-gate coverage
   calculation that replaces a single misleading rule count.
2. [Teams evidence request](TEAMS-EVIDENCE-REQUEST.md) — the concise ask for
   the rule/target export needed before anyone reports a coverage percentage.
3. The five example sheets below — one per telemetry class, to be worked
   through as the gaps are closed.

## The five example sheets

1. [Metrics](EXAMPLES-METRICS.md) — synthetic availability, service RED/SLO, workload, certificate, storage, Flux and observability metrics.
2. [Kubernetes events](EXAMPLES-KUBERNETES-EVENTS.md) — Alloy event collection, Loki/LogQL alerting and the independent Vector/Kafka/Argo triage evidence path.
3. [Application and platform logs](EXAMPLES-APPLICATION-LOGS.md) — reusable LogQL onboarding for applications, cert-manager, Kyverno, external-dns, ingress, Flux and CSI.
4. [Traces and network](EXAMPLES-TRACES-AND-NETWORK.md) — trace-derived service/dependency objectives plus Cilium/Hubble flow, DNS, drop and policy evidence.
5. [Node auto-provisioning, scheduling and eviction](EXAMPLES-NODE-AUTOPROVISIONING.md) — NAP/Karpenter, pending pods, events, evictions, Alloy evidence collection and distinct control-plane signal handling.

## Two paths, deliberately independent

The evidence-first pilot remains a read-only investigation path. LGTM alerting
is a separate notification path:

~~~text
Alloy -> Loki -> Loki Ruler -> Alertmanager -> human page      (notification)
Alloy -> Vector -> Kafka -> Argo -> read-only triage           (investigation)
~~~

Kubernetes event and application-log rules may run through Loki Ruler and
Alertmanager while the same bounded signals are independently available to
triage. **Neither path should be made dependent on the other.** That
independence is the point: if one is degraded, the other still works.

### Which path carries which signal

Prefer LGTM where it already carries the signal efficiently. Do not block the
triage pilot waiting for it.

| Situation | Path | Why |
|---|---|---|
| LGTM already collects the signal, retains it queryably, and it can be read out within the triage latency and payload budget | **LGTM first** | No second collection path, no duplicate cost, one retention/redaction model to govern. |
| The signal is not collected today, or is not retrievable within the triage budget, or adding it would make triage depend on LGTM availability | **Vector -> Kafka direct** | The bundle is already bounded and redacted at the worker; Kafka is an existing dependency, not a new broker. |
| The signal is needed by both a human page and an agent triage run | **Both, independently** | Alloy fans out at the worker: one collection, two consumers, no coupling. |

This is a per-signal-class decision, not one decision for the whole estate.
Record the choice and its reason for each class in the coverage inventory, so a
later reader can see why a class took the path it did.

Prerequisite for the LGTM-first option: the rule/target export in
[TEAMS-EVIDENCE-REQUEST.md](TEAMS-EVIDENCE-REQUEST.md). Until that lands we
cannot distinguish "LGTM already has this signal" from "LGTM has a rule named
for it", and that difference is the whole question.

## Using the example sheets

Every sheet follows the same contract:

- `{{PLACEHOLDER}}` values are **not** literal — replace them after checking the
  live label model in Explore.
- Metric and label names are the common shapes for the standard exporters, not
  version-independent facts. Validate each one before deploying.
- A rule that silently never fires is worse than no rule: it produces false
  confidence in coverage. Prove each candidate against both a real failure and
  a normal period before counting it.
- Record all four gates — defined, scoped, routed, proven — in the coverage
  inventory for every objective.
