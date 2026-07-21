# LGTM Metrics Alert Examples

## Purpose

This sheet provides metric-alert candidates for the gaps in [LGTM Alert Coverage Baseline](BASELINE.md). It is an implementation handoff, not evidence that a rule is deployed.

Replace all {{PLACEHOLDER}} values after checking the live Mimir/Prometheus label model. Each candidate needs the baseline gates: defined, scoped, routed and proven.

## WHISKEYAPP ingress canary

~~~promql
# Candidate: WhiskeyappIngressProbeFailed
probe_success{job="{{WHISKEYAPP_PROBE_JOB}}", cluster="{{CLUSTER_NAME}}"} == 0

# Supporting evidence only: the workload is unavailable
kube_deployment_status_replicas_available{
  cluster="{{CLUSTER_NAME}}", namespace="{{WHISKEYAPP_NAMESPACE}}",
  deployment="whiskeyapp"
}
<
kube_deployment_spec_replicas{
  cluster="{{CLUSTER_NAME}}", namespace="{{WHISKEYAPP_NAMESPACE}}",
  deployment="whiskeyapp"
}
~~~

The synthetic HTTP 200 probe is the objective; readiness is supporting evidence. Start with a five-minute sustained failure and include probe location and a safe route identifier.

A canary is trusted more than an ordinary rule, so prove it cannot fail open. If
the blackbox probe target is removed or misconfigured, `probe_success` stops
being reported and `== 0` never fires — the canary reports nothing and silence
reads as health. Pair it with `absent_over_time(probe_success{job="{{WHISKEYAPP_PROBE_JOB}}"}[15m])`
so a missing canary pages as loudly as a failing one, and test that by deleting
the probe target in a lower environment, not only by breaking the app.

## Tier-1 service errors and latency

~~~promql
# Candidate: ServiceHigh5xxRate
100 * (
  sum by (cluster, namespace, service) (rate(http_requests_total{
    cluster="{{CLUSTER_NAME}}", namespace="{{NAMESPACE}}",
    service="{{SERVICE}}", status=~"5.."
  }[5m]))
  /
  clamp_min(sum by (cluster, namespace, service) (rate(http_requests_total{
    cluster="{{CLUSTER_NAME}}", namespace="{{NAMESPACE}}",
    service="{{SERVICE}}"
  }[5m])), 1)
) > {{ERROR_PERCENT_THRESHOLD}}

# Candidate: ServiceP95LatencyHigh
histogram_quantile(0.95, sum by (cluster, namespace, service, le) (
  rate(http_request_duration_seconds_bucket{
    cluster="{{CLUSTER_NAME}}", namespace="{{NAMESPACE}}",
    service="{{SERVICE}}"
  }[5m])
)) > {{P95_SECONDS_THRESHOLD}}
~~~

Map these to the actual OpenTelemetry/framework metric names. Use agreed multi-window SLO-burn alerts when the SLI and error budget are established. Low traffic needs its own synthetic/traffic-expectation objective.

## Critical components, certificates and storage

~~~promql
# Candidate: CriticalDeploymentUnavailable
kube_deployment_status_replicas_available{
  cluster="{{CLUSTER_NAME}}", namespace="{{NAMESPACE}}", deployment="{{WORKLOAD}}"
}
<
kube_deployment_spec_replicas{
  cluster="{{CLUSTER_NAME}}", namespace="{{NAMESPACE}}", deployment="{{WORKLOAD}}"
}

# Candidate: CertificateNotReady
# condition="False" alone misses condition="Unknown". cert-manager emits this
# metric for all three condition values, and a Certificate that has never been
# issued — webhook down, issuer missing, freshly created and stuck — sits at
# Unknown, not False. Those are the cases worth paging on.
max by (cluster, namespace, name) (
  certmanager_certificate_ready_status{
    cluster="{{CLUSTER_NAME}}", namespace="{{NAMESPACE}}", condition!="True"
  }
) == 1

# Candidate: PersistentVolumeClaimNearCapacity
# kubelet_volume_stats_* is reported by the kubelet only for volumes actually
# mounted by a running pod. A PVC stuck Pending, or one whose pod cannot start,
# emits no series at all — so this rule stays silent for exactly the storage
# failures that block a workload. Cover those separately from
# kube_persistentvolumeclaim_status_phase{phase="Pending"} and the FailedMount
# and FailedAttachVolume events in the Kubernetes events sheet.
100 * kubelet_volume_stats_available_bytes{
  cluster="{{CLUSTER_NAME}}", namespace="{{NAMESPACE}}"
} / kubelet_volume_stats_capacity_bytes{
  cluster="{{CLUSTER_NAME}}", namespace="{{NAMESPACE}}"
} < {{PVC_FREE_PERCENT_THRESHOLD}}
~~~

`CriticalDeploymentUnavailable` has no threshold of its own: `available < spec`
is the normal state during any rolling update, scale-up or node drain. It is
only meaningful with a `for:` attached at rule-provisioning time, set longer
than the workload's worst-case rollout. Without it, every deploy pages. The same
applies to the WHISKEYAPP supporting-evidence expression above.

Create individual objectives for CoreDNS, Cilium agent/operator, CSI, cert-manager, ingress, Flux and monitoring. A cluster-wide pod ratio must only be a safety net.

## Delivery and observability self-health

~~~promql
# Candidate: FluxKustomizationNotReady
# Two traps here. (1) The object's namespace arrives as `exported_namespace`:
# Flux's PodMonitor does not set honorLabels, so the scrape target's own
# `namespace` wins the collision. Selecting namespace="flux-system" appears to
# work only because the controllers run there, and silently returns nothing for
# Kustomizations anywhere else. (kube-state-metrics is unaffected — its
# ServiceMonitor sets honorLabels: true.) (2) ready="False" misses
# ready="Unknown", which is what a Kustomization reports while stuck
# reconciling or when its source is unavailable — a common real failure.
gotk_resource_info{
  cluster="{{CLUSTER_NAME}}", exported_namespace="{{FLUX_NAMESPACE}}",
  kind="Kustomization", ready!="True", suspended="false"
} == 1

# Candidate: CriticalTargetDown
# `up == 0` only fires while the target is still discovered but failing to
# scrape. If the target disappears from service discovery entirely — the
# ServiceMonitor is deleted, the namespace is torn down, a label selector stops
# matching — the series stops existing and this rule goes silent. That is the
# outage case, and it is the case this rule cannot see.
up{cluster="{{CLUSTER_NAME}}", job=~"{{CRITICAL_SCRAPE_JOB_REGEX}}"} == 0

# Candidate: CriticalTargetMissing — pair every up==0 rule with this one.
absent_over_time(up{
  cluster="{{CLUSTER_NAME}}", job="{{CRITICAL_SCRAPE_JOB}}"
}[15m])
# absent_over_time needs one fully-qualified job per rule: it reports that a
# named series is missing, so it cannot enumerate targets behind a regex.
# It also fires only when the selector goes *completely* empty — for a
# multi-instance job, losing one of three replicas leaves `up` present and this
# rule silent. Where the replica count is known and stable, add:
count(up{cluster="{{CLUSTER_NAME}}", job="{{CRITICAL_SCRAPE_JOB}}"})
  < {{EXPECTED_TARGETS}}

# Candidate: PrometheusRemoteWriteFailures
# Metric renamed in Prometheus >=2.23: prefer prometheus_remote_storage_samples_failed_total.
# The old prometheus_remote_storage_failed_samples_total returns no series on current builds,
# so a rule written against it never fires. Confirm the exact name in Explore before deploying.
rate(prometheus_remote_storage_samples_failed_total{
  cluster="{{CLUSTER_NAME}}"
}[5m]) > 0
~~~

A scrape target being up does not prove remote write, rule evaluation, Loki ingestion or notification delivery. Pair every metric alert with the relevant event, log or trace evidence sheet.

The HTTP metric name and its status label are exporter-specific. Many instrumentations expose the response class as `code` or `status_code` rather than `status`; validate the real label and the `5..` regex against live series before deploying the error-rate rule. `clamp_min(...,1)` on a per-second rate only guards divide-by-zero — below one request/second it also floors the denominator and understates the error ratio, which can suppress the alert on low-traffic services. Give low-traffic tiers their own synthetic/traffic-expectation objective, as noted above.
