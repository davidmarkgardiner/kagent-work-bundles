# LGTM Query and Alert Example Sheets

## Purpose

These five handoff sheets turn the gaps in [LGTM Alert Coverage Baseline](LGTM-ALERT-COVERAGE-BASELINE.md) into focused implementation examples. They are not deployed rules or evidence of coverage. The LGTM team must validate each candidate against its installed data sources, labels, rule-provisioning model and Alertmanager routing.

An objective only counts as covered when it is defined, scoped, routed and proven, as specified by the baseline.

## The five sheets

1. [Metrics alerts](LGTM-METRICS-ALERT-EXAMPLES.md) — synthetic availability, service RED/SLO, workload, certificate, storage, Flux and observability metrics.
2. [Kubernetes events](LGTM-KUBERNETES-EVENT-ALERT-EXAMPLES.md) — Alloy event collection, Loki/LogQL alerting and the independent Vector/Kafka/Argo triage evidence path.
3. [Application and platform logs](LGTM-APPLICATION-LOG-ALERT-EXAMPLES.md) — reusable LogQL onboarding for applications, cert-manager, Kyverno, external-dns, ingress, Flux and CSI.
4. [Traces and network](LGTM-TRACE-NETWORK-ALERT-EXAMPLES.md) — trace-derived service/dependency objectives plus Cilium/Hubble flow, DNS, drop and policy evidence.
5. [Node auto-provisioning, scheduling and eviction](LGTM-NODE-AUTOPROVISIONING-SCHEDULING-EXAMPLES.md) — NAP/Karpenter, pending pods, events, evictions, Alloy evidence collection and distinct control-plane signal handling.

## Important boundary

The evidence-first pilot remains a read-only investigation path:

~~~text
Alloy -> Vector -> Kafka -> Argo -> triage
~~~

LGTM alerting is a separate notification path. Kubernetes event and application-log rules may run through Loki Ruler and Alertmanager while the same bounded signals are independently available to triage. Neither path should be made dependent on the other.

See [Teams LGTM Alert Coverage Evidence Request](TEAMS-LGTM-ALERT-COVERAGE-REQUEST.md) for the rule/target export needed before reporting measured coverage.
