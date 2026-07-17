# LGTM Alert Coverage Baseline

## Purpose

This is a **baseline assessment**, from the alert list supplied by the LGTM
team on 2026-07-16.  It answers two different questions that must not be
collapsed into one number:

1. Which failure modes have an alert named for them today?
2. What percentage of the platform is demonstrably covered by a correctly
   scoped, routed and tested alert?

The supplied list answers only part of the first question. It does **not**
include rule definitions, PromQL/LogQL, labels, target scope, severity,
notification route, silences, runbooks, firing history, or test evidence.
Accordingly, every status in this document is **asserted, not verified** until
that evidence is supplied. Do not report a production coverage percentage from
this document alone.

## Executive planning estimate — not a measured production score

Based only on the alert behaviour described so far, the estate has **partial
metric/state alerting**, not full actionable observability. The current alert
set is predominantly Kubernetes and Prometheus-style state/usage data: pod
status and controller desired-count metrics, node usage/free space and resource
quota metrics. A waiting reason, OOM or eviction can be exposed through that
metric/state path, but that is not evidence that the underlying log line or
Kubernetes event is captured, retained, correlated and delivered to an
investigator.

Use the following as a deliberately conservative planning baseline until the
rule and target inventories are measured:

| Coverage lens | Indicative current position | Why |
|---|---:|---|
| Telemetry modalities available to an alert/investigator | **~25%** | Metrics/state is partially represented; there is no evidence of logs, Kubernetes events or traces being connected to alert investigation. |
| AKS platform operational objectives | **~20–25%** | Basic node and generic workload symptoms exist; control plane, `kube-system`, network, storage, delivery and observability-plane objectives are not evidenced. |
| Shared platform applications (for example external-dns, cert-manager, ingress, Cilium/Hubble, CSI, Flux, Argo) | **~10–15%** | They may inherit generic pod/DaemonSet/node alerts, but there is no component-specific health, reconciliation, certificate, DNS, storage, network-flow/policy or service-level coverage evidenced. |
| Application-team services | **~10–15%** | Generic pod/Deployment/Quota symptoms may apply; no per-service availability, latency, error-rate, dependency, synthetic-journey or SLO-burn coverage is evidenced. |
| WHISKEYAPP platform-canary service | **0% evidenced** | WHISKEYAPP is deployed to each platform and should prove a workload can be served through ingress with HTTP 200, but it is not currently monitored. |
| Actionable incident evidence | **~10% or less** | The existing rules can page on symptoms, but no log/event/trace evidence package or correlation to the affected application is evidenced. |

These figures are an **investment-sizing estimate**, not an LGTM performance
score. Replace them with the measured formula in [Coverage scorecard to
produce](#coverage-scorecard-to-produce) once the inventory is available. If
the current rules already have scoped log, event or trace links, the score will
increase; if they are broadly scoped, untested or unrouted, it will decrease.

### The desired minimum per application

Every application — whether it is a customer workload or a platform service —
should have the following evidence chain, with ownership and a runbook:

```text
metrics:  availability, latency, errors, saturation and capacity/SLO burn
logs:     structured errors and relevant application/controller failures
events:   Kubernetes Warning events and reconciliation/admission failures
traces:   request and dependency path for network/latency/error investigation
```

For the AKS platform, apply the same chain to cluster services and add
control-plane, node, Cilium/Hubble, CSI, DNS, ingress, certificate, GitOps and
observability-pipeline objectives. A generic "pod not running" page is a
useful safety net; it must not be the primary health definition for a vital
service.

### Glaring gap: logs and Kubernetes events for every application

The current alert list does **not** evidence that all applications have their
logs and Kubernetes events collected, retained, queryable and correlated to the
alerting workflow. This is the principal gap to close. It applies equally to
application-team workloads and platform-owned applications such as
external-dns, cert-manager, ingress, CoreDNS, Cilium/Hubble, CSI, Flux, Argo,
kagent and agentgateway.

The objective is not to page on every log line or Normal event. For **every
deployed application**, the platform should be able to answer, during an
incident: what failed, where it ran, what Kubernetes reported, and which
application/owner is affected.

Minimum coverage standard per application:

| Evidence | Required capability |
|---|---|
| Logs | Collect structured container/controller logs; redact before transport; retain searchable error evidence with cluster, namespace, workload, pod/container and application/owner labels. |
| Kubernetes events | Collect and retain Warning events for the workload and its dependencies, including scheduling, image-pull, probe, mount/volume, eviction, network and reconciliation failures. |
| Correlation | Join the alert, logs and events using cluster, namespace, workload, pod/container and a bounded incident fingerprint; do not rely on a human to reconstruct the context manually. |
| Proof | Trigger one safe representative application failure and one Kubernetes-event failure per onboarding pattern; prove the evidence is queryable and reaches the intended incident workflow/owner. |
| Ownership | Record the application criticality, service owner, alert receiver and runbook. Generic platform alerts must not be the only ownership model. |

Measure this as a separate rollout metric:

```text
application log-and-event coverage % =
  applications with collected + queryable + correlated + proven logs/events
  / applications in the approved platform and application inventory
```

Publish it separately for platform applications and application-team services.
Do not count an application merely because its pods are scraped by generic
cluster metrics or because its namespace exists in the logging system.

### Immediate platform canary: WHISKEYAPP ingress HTTP 200

WHISKEYAPP is a platform-owned application deployed to each platform. It is the
minimum end-to-end canary: if WHISKEYAPP is Ready **and** an external request
through the configured ingress endpoint returns HTTP `200`, the platform can at
least schedule a workload, expose it through ingress, and serve a request. It
is currently an unmonitored gap.

Add a per-platform WHISKEYAPP health objective with these checks:

| Check | What it proves | Alert/evidence on failure |
|---|---|---|
| Deployment/Pod Ready | WHISKEYAPP can schedule and start. | WHISKEYAPP workload status, waiting reason, logs and Warning events. |
| Service endpoints ready | Traffic has a ready backend. | Service/EndpointSlice state and relevant pod events. |
| DNS, TLS and ingress path | The configured public/internal ingress route resolves and accepts the request. | DNS/TLS/ingress-controller evidence and Cilium/Hubble flow or policy evidence where relevant. |
| HTTP probe returns `200` | A request reaches WHISKEYAPP through ingress and is served successfully. | Probe result, response status/latency, ingress access/error logs and a bounded correlation ID. |

The monitor must run from the same approved network perspective as its users
(or explicitly report which perspective it represents). Page on sustained
failure or non-`200`, and include the platform/cluster, ingress route, probe
location and the four preceding evidence checks. This is a platform canary, not
an application SLO: a green WHISKEYAPP result does not prove that every core
application or dependency is healthy.

Track it separately:

```text
WHISKEYAPP platform-canary coverage % =
  platforms with deployed + ingress-200-monitored + failure-proven WHISKEYAPP
  / platforms where WHISKEYAPP is required
```

## Normalised current alert inventory

The following is the complete list received, with spelling normalised. It is
counted as 13 alert classes (not necessarily 13 individual rules):

| # | Alert class and declared behaviour | Primary layer | What remains to verify |
|---|---|---|---|
| 1 | Pod not running / container waiting. Captures the pod status and waiting reason, including `CrashLoopBackOff`, `ImagePullBackOff` and `ErrImagePull`. | workload | Which namespaces/workloads are selected; whether terminated, restart-rate and probe failures are also covered. |
| 2 | DaemonSet desired count not met. Fires when an expected DaemonSet pod is not scheduled. | workload or platform add-on | Which DaemonSets are in scope, and whether unavailable/not-ready pods are included as well as unscheduled pods. |
| 3 | At least two nodes not ready. | node | Time window, node-pool scope and whether a single critical node failure is intentionally excluded. |
| 4 | CPU saturation. Fires only when 20% of nodes are CPU-saturated; this is CPU **usage**, not memory. | node fleet | Saturation definition, time window, node-pool scope and whether individual critical nodes have a lower threshold. |
| 5 | High memory usage. | node | Threshold, duration, scope and distinction from the Kubernetes `MemoryPressure` node condition. |
| 6 | Low disk free space. | node | Free-space threshold, duration, filesystem scope and inode coverage. |
| 7 | Node unreachable. | node | Probe/source, relationship to the two-not-ready threshold, routing and recovery behaviour. |
| 8 | Deployment replica mismatch | workload | Covers one controller type only. |
| 9 | OOM kills. Fires at three OOM kills in one hour. | workload | Namespace/workload grouping, whether a single vital pod is excluded by aggregation, and alert routing. |
| 10 | High pod evictions. The current operational hypothesis is that this is mostly driven by memory pressure. | workload / node | Actual event/query condition, threshold, cause split and workload impact. Do not treat the suspected memory-pressure cause as proven. |
| 11 | 10% of pods pending for more than 10 minutes. | cluster scheduling | Target population, exclusions and individual critical-workload coverage. |
| 12 | Kubernetes quota fully used. Evaluates pod CPU and memory **limits** against quota. | namespace | Exact utilisation threshold; namespace scope; and whether requests, storage and object-count quotas are intentionally excluded. |
| 13 | Kubernetes quota exceeded. Evaluates pod CPU and memory **limits** against quota. | namespace | Exact trigger semantics, namespace scope, admission-event evidence and whether non-resource quotas are intentionally excluded. |

## What this baseline covers

On the evidence received, coverage is concentrated in node health, generic pod
scheduling/lifecycle, Deployment replicas and CPU/memory-limit quota. These
are necessary **infrastructure symptoms**, but they do not establish that a
vital platform component or business application is available to its users.

| Operational domain | Current status | What the list appears to cover | Material gaps to validate or add |
|---|---|---|---|
| Nodes and host capacity | Partial | Two-node readiness threshold, reachability, CPU usage, high memory usage and low disk free space | kubelet errors, PID pressure, filesystem/inode exhaustion, allocatable/capacity exhaustion, node condition duration, node-pool capacity and autoscaler failure. |
| Workload lifecycle and scheduling | Partial | waiting reason (including crash/image pull), OOM, eviction, pending, Deployment mismatch and DaemonSet desired count | restart-rate, mounts/volumes, probes, Job/CronJob, StatefulSet, DaemonSet availability, HPA, PDB, scheduling constraints and per-critical-workload alerts. |
| Kubernetes control plane | No evidence | None | API server availability/latency/errors, scheduler, controller-manager, etcd, admission/webhook failure, API error budget and audit/control-plane events. Managed AKS ownership must be identified for each signal. |
| `kube-system` | No evidence | DaemonSet rule could apply, but no scope proves it | CoreDNS, kube-proxy, Cilium agent/operator, CSI drivers, metrics-server, autoscaler, node-local DNS and any AKS-managed add-on health. |
| Certificate management | No evidence | None | cert-manager controller/webhook/cainjector availability, reconciliation errors, Certificate Ready=False, issuance/renewal failures, expiry windows, ACME/DNS/provider errors and expiring serving certificates. |
| Ingress, DNS and network | No evidence | None | ingress controller availability/error rate, TLS handshake/certificate expiry, CoreDNS latency/errors, Cilium agent/operator health, Hubble relay/UI health, dropped/denied flows, policy enforcement failures, service endpoint depletion, egress/DNS dependency failures. |
| Storage | No evidence | None | PVC pending/full, volume attach/mount errors, CSI controller/node health, storage latency/errors, snapshot/backup failures. |
| GitOps and delivery | No evidence | None | Flux source-controller, kustomize-controller, helm-controller and notification-controller health; source/Kustomization/HelmRelease reconciliation failure; suspended/stalled state; drift; failed rollout; image automation and webhook/notification delivery failures. |
| Observability pipeline | No evidence | None | Prometheus scrape/remote-write failure, Alertmanager delivery failure, Loki ingestion/query health, Grafana availability, missing targets and rule-evaluation errors. |
| kagent / Argo / agentgateway | No evidence | None | workflow failures/backlog, EventSource/Sensor health, agent/tool failure, gateway availability/latency/error rate, model/provider failures and queue/DLQ health. |
| Application availability and correctness | No evidence | None | Per-service availability/latency/error-rate/saturation, synthetic journeys, dependency failure, business-critical queues/jobs, data correctness and application-specific SLO burn alerts. |
| Security and policy | No evidence | None | certificate trust failures, failed policy/admission decisions, unusual authz/authn failures, runtime security events and secret/config availability. |

## Why a single percentage is unsafe today

`13 alert classes` is an inventory count; it is not coverage. For example, a
Deployment replica mismatch rule could be scoped only to application namespaces,
exclude `kube-system`, have no Teams receiver, be permanently silenced, or have
never been tested. Each case is materially different operational coverage even
though the rule exists.

Use the following four gates for every required control objective:

```text
defined   = an enabled rule has an unambiguous expression and threshold
scoped    = it selects every intended cluster, namespace and component
routed    = correct severity, owner, receiver and runbook are attached
proven    = a controlled failure has fired and reached the intended receiver
```

An objective counts as **covered** only when all four gates are true. A rule is
not coverage if it is merely present in source control.

## Coverage scorecard to produce

Build a versioned `alert-coverage.yaml` inventory with one row per required
objective, target and environment. Calculate coverage only from that inventory:

```text
coverage % = 100 * count(objectives where defined && scoped && routed && proven)
                    / count(required objectives)
```

Publish four companion percentages so gaps cannot be hidden:

```text
rule-definition coverage  = defined / required
scope coverage            = defined-and-scoped / required
delivery coverage         = defined-and-scoped-and-routed / required
proven operational cover  = defined-and-scoped-and-routed-and-proven / required
```

Report these separately for:

1. cluster/control-plane and node layer;
2. `kube-system` and managed/add-on components;
3. shared platform services, including cert-manager, ingress, DNS, storage,
   GitOps, observability, Argo, kagent and agentgateway;
4. application namespaces and every tier-1 application;
5. each cluster/environment.

For the application view, use a denominator of **critical application service
objectives**, not pod count. Pod count makes a platform look covered while a
single payment, identity or customer-facing service remains unobserved.

## Minimum evidence requested from LGTM

Ask for an export or repository link containing, for every current alert rule:

- rule name, expression, `for` duration and severity;
- datasource and evaluation group;
- cluster/namespace/component selectors and explicit exclusions;
- labels identifying service, owner, environment and runbook;
- Alertmanager route/receiver and notification policy;
- current enabled/silenced/muted state and last evaluation result;
- a recent controlled test or incident proving delivery; and
- the target inventory: clusters, namespaces, tier-1 applications and all
  platform components expected to be monitored.

The platform team must provide the target inventory and criticality/ownership;
LGTM cannot infer business criticality from metrics alone.

## Immediate prioritisation

Before expanding generic pod alerts, close the blind spots that can take down
the platform or prevent applications from being reached:

1. Every application: establish the log-and-Kubernetes-event coverage standard
   above, beginning with tier-1 application services and platform applications.
2. WHISKEYAPP: add the per-platform, through-ingress HTTP `200` canary monitor and
   prove its failure path before using it as a platform health gate.
3. `kube-system`: CoreDNS, Cilium agent/operator, CSI, kube-proxy,
   metrics-server and autoscaler.
4. cert-manager: controller/webhook/cainjector health, certificate readiness,
   renewal/issuance failures and expiry.
5. Cilium/Hubble, ingress and DNS: agent/operator/relay health; network-policy
   enforcement; denied/dropped flows; DNS and egress dependency failures;
   ingress availability, latency and errors.
6. Storage: PVC capacity/pending, CSI health and volume attach/mount failures.
7. Flux and the observability/alert-delivery path itself, including all Flux
   controllers and reconciliation/notification failures.
8. Tier-1 application SLO burn alerts and synthetic user journeys, linked to
   the collected logs and events.

For vital components, avoid a cluster-wide ratio as the only signal. A rule
such as "10% of pods pending" must be complemented by an individual objective
for each critical component; one unavailable CoreDNS, cert-manager webhook or
customer-facing application can be a severe outage while the cluster-wide ratio
remains below threshold.

## Relationship to the evidence-first triage pilot

This alert-coverage work is complementary to the worker-to-management
evidence-first triage pilot. Alertmanager/Grafana remains the human paging and
observability plane. The pilot supplies bounded logs and Kubernetes Warning
events to a read-only triage agent; it is not evidence that all alerting
objectives are covered. Any new alert rule should, where appropriate, be paired
with a corresponding evidence class and a controlled proof that the incident
can be investigated as well as paged.
