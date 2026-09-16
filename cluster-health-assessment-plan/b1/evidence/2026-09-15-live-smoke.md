# B1 live smoke receipt — 2026-09-15

Status: PARTIAL PASS. A useful report-only path is live on one home-lab worker.
Gate G1 is not complete because the required 10 working days, 20 labelled
weekday slots, real weekend, operator acceptance, and remaining fault cases do
not yet exist.

## Scope and topology

- Host: 10 logical CPUs, approximately 24 GiB memory, and 181 GiB free disk at inspection.
- Worker: one Kubernetes v1.32.2 amd64 node.
- Storage: default local-path StorageClass; B1 uses ConfigMaps and needs no PVC.
- Metrics API: unavailable. This is reported as optional unavailable coverage; it is not converted to zero utilisation.
- Prometheus Operator CRDs exist. No in-cluster Grafana deployment was found, so the metrics endpoint and dashboard artifact were proven, not a rendered Grafana view.
- Flux Kustomization CRD was not installed on this worker. The lab apply was direct; workplace delivery remains GitOps-first.

## Existing certification inventory

The live reusable object is `argo-events/cluster-certification`, generation 2,
not `aks-certification`. Its CronWorkflow `dice-daily-cluster-health` is
suspended. The template has no owner reference and uses mutable
`python:3.11-slim`; it includes agent and GitLab branches. Its
`argo-events-sa` can read Secrets and create/delete ConfigMaps in `kagent`.

B1 did not run or change that path. It reused the passive collection ideas in a
new isolated namespace and pinned linux/amd64 Python 3.11 to
`sha256:d1053354624536b044162aaab1e418bd000ea35184fb1ae098ab3166b1072e72`.
The running metrics pod reported the same image digest.

## Static and fixture proof

`b1/verify-b1.sh red` passed:

- Twenty-one unit/policy tests.
- All 1,024 combinations of four statuses across five domains.
- Unknown coverage blocks degraded admission and recovery; critical remains immediate.
- Two complete degraded assessments admit; two complete healthy/watch assessments recover.
- 50 replacement pods collapse to one Deployment/scheduling key.
- Two unresolved standalone pods do not merge.
- Successful Job pods are excluded.
- Fractional `eventTime` and `series.lastObservedTime` shapes parse.
- Restart counter deltas, first observation, and reset behaviour are explicit.
- Kubernetes list pagination is exhaustive or fails the source as partial.
- 1 versus 200 unavailable workloads out of 1,000 remain distinguishable.
- 1,000 containers without limits create one advisory aggregate, not 1,000 findings.
- A 93.6% CPU-commit fixture reaches watch and PolicyViolation is outside the event allowlist.
- Old and new OOM termination timestamps are separated by the recency cutoff.
- Missing/invalid downstream flags and unsafe bounds fail closed.
- Kustomize rendering and server-side dry-run passed.

The source fixture preserves sanitised Kubernetes field/timestamp shapes from
the live worker while replacing names, UIDs, addresses, images, and messages.

## Live report proof

Run identity: `cluster-health-snapshot-event-proof`, immutable snapshot sequence
9, followed by manual report slot `b1-proof-v3-20260915`.

The snapshot completed with required coverage for the five-namespace pilot:
`kube-system`, `cert-manager`, `external-secrets`, `kyverno`, and `kagent`.
It had no API errors, a valid checksum, and serialized to 5,017 bytes under the
256 KiB cap. The report
was read from the saved snapshot; it did not recollect.

Because those five namespaces are not the whole worker, node CPU-commit,
max-pods headroom, and pod-CIDR headroom are explicitly
`unavailable_partial_placement_coverage`. Publishing the earlier pilot-only
percentages would have overstated real node capacity.

Observed outcome:

| Field | Result |
|---|---|
| Display score | 65, non-authoritative |
| Deterministic gate | Active after persistent degraded domains |
| Nodes/scheduling | Degraded: one stable scheduling group |
| Workload availability | Degraded: 1/48 eligible workloads unavailable |
| Shared services | Healthy within declared pilot coverage |
| Resource pressure | Degraded: 10 selected control-plane log error matches; zero restart delta and zero recent OOM |
| Delivery | Healthy: required API collection complete |
| Problem groups | Three stable groups; availability and scheduling collapse to the same Deployment owner but remain separate symptom families |
| Triage mode | `report_only` |

The selected log scanner stores only counts and owner/container identity, never
raw log lines. It scanned only unhealthy/restarting candidates and explicitly
reported selective/truncated coverage. Its control-plane error matches need
operator labelling during calibration; they may be benign recurring messages.

The Prometheus endpoint returned score, coverage, original snapshot age, gate,
all five domain states, group count, API calls, and response bytes. A PodMonitor,
scrape annotations, and `grafana/cluster-health-overview.json` are installed as
a ConfigMap. Datasource ingestion and dashboard rendering are not yet proven.

## Security proof

The dedicated assessor identity produced these live authorisation results:

| Operation | Result |
|---|---|
| Get Secrets in watched `kagent` | Denied |
| Create Pods in watched `kagent` | Denied |
| List Pods in non-allowlisted `default` | Denied |
| List Pods in allowlisted `kagent` | Allowed |

State writes are limited to ConfigMaps in `cluster-health-system`. The metrics
identity can only get ConfigMaps there. Rendered source/manifests contain no
Kafka, GitLab, GitHub, agent URL, webhook URL, or Secret reference.

## Measured cost and B2 sizing decision

Sequence 9 measured 68 Kubernetes API calls, 3,930,327 response bytes, 976 ms
API time, 1,081 ms wall-clock poll time, and 55,288 KiB maximum RSS. The
`kagent` pilot namespace accounted for 21 calls and 3,500,191 bytes, showing
that payload size is driven by namespace contents rather than namespace count.

Decision for the next gate: retain one sequential allowlisted shard per worker,
not one process per namespace. For the workplace pilot, cap an initial shard at
25 namespaces and split earlier if p95 poll time exceeds half the five-minute
interval, responses exceed 50 MiB, API throttling appears, or the 2,000 active
counter-observation limit makes trend coverage partial. These are starting
assumptions, not workplace capacity claims.

## Scheduling and calibration

- Snapshot CronJob: every five minutes, `concurrencyPolicy: Forbid`, 240-second deadline.
- Reports: 07:30 and 16:30 weekdays, `Europe/London`, 30-minute deadline.
- A calibration auditor produced explicit missed rows for the two earlier 2026-09-15 slots and has a DST regression test covering 20 unique slots across the October transition weekend.
- Immutable snapshot retention is 288 runs (about 24 hours at five minutes). Immutable reports are not garbage-collected during the initial calibration.

## Still required before G1

- Ten working days, 20 labelled weekday report slots, and a real weekend.
- SRE labels for the selected log rule and every other false positive.
- Live permission-failure, old/new OOM, counter-reset, 1,000 PolicyViolation,
  and controller-outage/catch-up drills in a dedicated fixture scope.
- Confirmed Grafana datasource ingestion and rendered dashboard.
- Follow-up independent critique of revision 2 and this implementation.
- A reviewed owner/check-family table and workplace-specific coverage scope.

No Kafka topic, database, model route, agent invocation, GitHub/GitLab write, or
ticket was created. B2-B4 remain outside this receipt.
