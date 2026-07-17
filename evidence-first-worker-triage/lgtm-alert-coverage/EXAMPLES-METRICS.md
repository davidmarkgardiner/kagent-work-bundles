# LGTM Metrics Alert Examples

## Purpose

This sheet provides metric-alert candidates for the gaps in [LGTM Alert Coverage Baseline](LGTM-ALERT-COVERAGE-BASELINE.md). It is an implementation handoff, not evidence that a rule is deployed.

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
max by (cluster, namespace, name) (
  certmanager_certificate_ready_status{
    cluster="{{CLUSTER_NAME}}", namespace="{{NAMESPACE}}", condition="False"
  }
) == 1

# Candidate: PersistentVolumeClaimNearCapacity
100 * kubelet_volume_stats_available_bytes{
  cluster="{{CLUSTER_NAME}}", namespace="{{NAMESPACE}}"
} / kubelet_volume_stats_capacity_bytes{
  cluster="{{CLUSTER_NAME}}", namespace="{{NAMESPACE}}"
} < {{PVC_FREE_PERCENT_THRESHOLD}}
~~~

Create individual objectives for CoreDNS, Cilium agent/operator, CSI, cert-manager, ingress, Flux and monitoring. A cluster-wide pod ratio must only be a safety net.

## Delivery and observability self-health

~~~promql
# Candidate: FluxKustomizationNotReady; validate Flux metric labels.
gotk_resource_info{
  cluster="{{CLUSTER_NAME}}", namespace="{{FLUX_NAMESPACE}}",
  kind="Kustomization", ready="False"
} == 1

# Candidate: CriticalTargetDown
up{cluster="{{CLUSTER_NAME}}", job=~"{{CRITICAL_SCRAPE_JOB_REGEX}}"} == 0

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
